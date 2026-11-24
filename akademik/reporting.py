"""Penyusunan, pemeriksaan, dan alur status rapor."""

from django.db import transaction
from django.utils import timezone

from .audit import catat_audit
from .models import (
    Extracurricular,
    ExtracurricularEnrollment,
    HomeroomNote,
    ReportCard,
    ReportCompetencyDescription,
    ReportExtracurricular,
    ReportSubjectGrade,
    School,
)
from .services import daftar_mapel, data_rapor, deskripsi_capaian, hitung_nilai


class ReportError(Exception):
    pass


class ReportLocked(ReportError):
    pass


class ReportIncomplete(ReportError):
    def __init__(self, issues):
        self.issues = issues
        super().__init__('; '.join(issues))


def kelas_siswa(student, semester):
    enrollment = (
        student.enrollments.select_related('class_group')
        .filter(academic_year=semester.academic_year_id)
        .first()
    )
    return enrollment.class_group if enrollment else student.class_group


def rapor_terkunci(student, semester):
    return ReportCard.objects.filter(
        student=student, semester=semester, status='PUBLISHED'
    ).exists()


def _predikat(nilai):
    if nilai is None:
        return ''
    if nilai >= 90:
        return 'A'
    if nilai >= 80:
        return 'B'
    if nilai >= 70:
        return 'C'
    return 'D'


@transaction.atomic
def susun_report_card(student, semester, user=None):
    """Buat/perbarui snapshot rapor. Rapor terbit tidak boleh diubah."""
    card = ReportCard.objects.select_for_update().filter(
        student=student, semester=semester
    ).first()
    if card is not None and card.terkunci:
        raise ReportLocked(
            'Rapor sudah diterbitkan. Buka kunci terlebih dahulu sebelum menyusun ulang.'
        )
    if card is not None and card.status in ('REVIEW', 'APPROVED'):
        raise ReportLocked(
            'Rapor sedang diajukan/disetujui. Kembalikan ke draf terlebih dahulu.'
        )
    kelas = kelas_siswa(student, semester)
    if card is None:
        card = ReportCard(
            student=student, semester=semester, class_group=kelas,
            nomor_urut=student.no_urut, created_by=user,
        )
    else:
        card.class_group = kelas
        card.nomor_urut = student.no_urut
        card.status = 'DRAF'
        card.approved_by = None
        card.approved_at = None
        card.published_at = None
        card.locked_at = None
    card.save()

    subject_ids = []
    for urutan, subject in enumerate(daftar_mapel(semester.academic_year), start=1):
        subject_ids.append(subject.id)
        hitung = hitung_nilai(student, subject, semester)
        capaian = deskripsi_capaian(student, subject, semester)
        grade, _ = ReportSubjectGrade.objects.update_or_create(
            report_card=card,
            subject=subject,
            defaults={
                'nilai_lm': hitung['rata_lm'],
                'nilai_sts': hitung['sts'],
                'nilai_sas': hitung['rata_sas'],
                'nilai_akhir': hitung['nilai'],
                'predikat': _predikat(hitung['nilai']),
                'deskripsi_otomatis': capaian['teks'],
                'urutan': urutan,
            },
        )
        grade.kompetensi.all().delete()
        if capaian['unggul'] is not None:
            ReportCompetencyDescription.objects.create(
                subject_grade=grade,
                objective=capaian['unggul'],
                tipe='UNGGUL',
                teks=(
                    f"Ananda sangat menguasai dalam "
                    f"{capaian['unggul'].deskripsi}."
                ),
                urutan=1,
            )
        if capaian['perlu'] is not None:
            teks_perlu = (
                f"Ananda perlu bimbingan dalam {capaian['perlu'].deskripsi}."
            )
            ReportCompetencyDescription.objects.create(
                subject_grade=grade,
                objective=capaian['perlu'],
                tipe='PERLU',
                teks=teks_perlu,
                urutan=2,
            )

    card.nilai_mapel.exclude(subject_id__in=subject_ids).delete()

    note = HomeroomNote.objects.filter(student=student, semester=semester).first()
    card.catatan_wali = note.catatan if note else ''
    card.sakit = note.sakit if note else 0
    card.izin = note.izin if note else 0
    card.alpa = note.alpa if note else 0

    card.ekskul.all().delete()
    enrollments = ExtracurricularEnrollment.objects.filter(
        student=student, semester=semester
    ).select_related('activity')
    if enrollments.exists():
        for index, eks in enumerate(
            enrollments.order_by('activity__urutan', 'activity__nama'), start=1
        ):
            ReportExtracurricular.objects.create(
                report_card=card,
                urutan=index,
                nama=eks.activity.nama,
                predikat=eks.predikat_efektif,
                deskripsi=eks.deskripsi or eks.activity.deskripsi,
            )
    else:
        for index, eks in enumerate(
            Extracurricular.objects.filter(
                student=student, semester=semester
            ).order_by('urutan'), start=1
        ):
            ReportExtracurricular.objects.create(
                report_card=card,
                urutan=index,
                nama=eks.nama,
                predikat=eks.predikat,
                deskripsi=eks.deskripsi,
            )
    card.save()
    catat_audit(
        user, 'UPDATE', card,
        deskripsi=f'Snapshots rapor {student.nama} {semester}',
    )
    return card


def periksa_kelengkapan(card):
    issues = []
    if not card.nilai_mapel.exists():
        issues.append('Belum ada nilai mata pelajaran.')
    for subject in daftar_mapel(card.semester.academic_year):
        nilai = card.nilai_mapel.filter(subject=subject).first()
        if nilai is None or nilai.nilai_akhir is None:
            issues.append(f'Nilai {subject.nama} belum lengkap.')
    if not card.catatan_wali.strip():
        issues.append('Catatan wali kelas belum diisi.')
    return issues


def ajukan(card, user):
    if card.status not in ('DRAF', 'REVISI'):
        raise ReportError('Rapor tidak berada pada status draf/revisi.')
    issues = periksa_kelengkapan(card)
    if issues:
        raise ReportIncomplete(issues)
    card.status = 'REVIEW'
    card.save(update_fields=['status', 'updated_at'])
    catat_audit(user, 'UPDATE', card, deskripsi='Ajukan rapor untuk review')
    return card


def setujui(card, user):
    if card.status != 'REVIEW':
        raise ReportError('Rapor belum diajukan untuk review.')
    card.status = 'APPROVED'
    card.approved_by = user
    card.approved_at = timezone.now()
    card.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])
    catat_audit(user, 'UPDATE', card, deskripsi='Setujui rapor')
    return card


def terbitkan(card, user):
    if card.status != 'APPROVED':
        raise ReportError('Rapor belum disetujui.')
    issues = periksa_kelengkapan(card)
    if issues:
        raise ReportIncomplete(issues)
    card.status = 'PUBLISHED'
    card.published_at = timezone.now()
    card.locked_at = timezone.now()
    card.save(update_fields=['status', 'published_at', 'locked_at', 'updated_at'])
    catat_audit(user, 'PUBLISH', card, deskripsi='Terbitkan rapor')
    return card


def buka_kunci(card, user, alasan=''):
    if card.status != 'PUBLISHED':
        raise ReportError('Rapor belum diterbitkan.')
    card.status = 'REVISI'
    card.published_at = None
    card.locked_at = None
    card.save(update_fields=['status', 'published_at', 'locked_at', 'updated_at'])
    catat_audit(
        user, 'UNLOCK', card,
        deskripsi=f'Buka kunci rapor. {alasan}'.strip(),
    )
    return card


def kembalikan(card, user, alasan=''):
    """Kembalikan rapor review/approval ke status revisi."""
    if card.status not in ('REVIEW', 'APPROVED'):
        raise ReportError('Rapor tidak sedang dalam review/persetujuan.')
    card.status = 'REVISI'
    card.approved_by = None
    card.approved_at = None
    card.save(update_fields=[
        'status', 'approved_by', 'approved_at', 'updated_at',
    ])
    catat_audit(
        user, 'UPDATE', card,
        deskripsi=f'Kembalikan rapor ke revisi. {alasan}'.strip(),
    )
    return card


def konteks_rapor(card):
    return {
        'report_card': card,
        'student': card.student,
        'class_group': card.class_group,
        'semester': card.semester,
        'school': School.get_solo(),
        'mapel_rows': card.nilai_mapel.select_related('subject').all(),
        'ekskul_rows': card.ekskul.all(),
        'catatan': card,
    }


def konteks_rapor_siswa(student, semester):
    card = ReportCard.objects.filter(student=student, semester=semester).first()
    if card is not None:
        return konteks_rapor(card)
    data = data_rapor(student, semester)
    data['class_group'] = kelas_siswa(student, semester)
    data['report_card'] = None
    return data
