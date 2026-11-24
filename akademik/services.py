from decimal import Decimal, ROUND_HALF_UP

from .models import (
    ClassGroup,
    Extracurricular,
    FormativeScore,
    HomeroomNote,
    School,
    Semester,
    Student,
    Subject,
    SummativeLM,
    SummativeScore,
)

MAX_LM = 10


def q2(value):
    """Bulatkan ke 2 desimal."""
    if value is None:
        return None
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def angka(value):
    """Format angka gaya Indonesia (koma desimal, tanpa nol berekor)."""
    if value in (None, ''):
        return '-'
    d = q2(value)
    teks = f'{d:.2f}'.rstrip('0').rstrip('.')
    return teks.replace('.', ',')


def tanggal_indonesia(value, dengan_hari=False):
    if not value:
        return '-'
    bulan = [
        'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
        'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
    ]
    hari = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']
    teks = f'{value.day} {bulan[value.month - 1]} {value.year}'
    if dengan_hari:
        teks = f'{hari[value.weekday()]}, {teks}'
    return teks


def semester_aktif():
    return Semester.get_aktif()


def kelas_aktif():
    aktif = (
        ClassGroup.objects.filter(academic_year__aktif=True, aktif=True).first()
        or ClassGroup.objects.filter(academic_year__aktif=True).first()
    )
    return aktif or ClassGroup.objects.first()


def daftar_siswa(class_group):
    if class_group is None:
        return Student.objects.none()
    return Student.objects.filter(class_group=class_group, aktif=True).order_by('no_urut')


def daftar_mapel(tahun=None):
    if tahun is None:
        semester = Semester.get_aktif()
        tahun = semester.academic_year if semester else None
    if tahun is None:
        return Subject.objects.none()
    return Subject.objects.filter(academic_year=tahun)


def nilai_formatif_map(student, subject, semester):
    data = FormativeScore.objects.filter(
        student=student,
        objective__subject=subject,
        objective__academic_year=semester.academic_year,
        semester=semester,
    ).values_list('objective_id', 'nilai')
    return dict(data)


def tujuan_aktif(subject, semester):
    return subject.tujuan_list.filter(
        academic_year=semester.academic_year, aktif=True
    ).order_by('nomor')


def deskripsi_capaian(student, subject, semester, objectives=None):
    """Meniru formula Excel: TP dengan nilai tertinggi (>=3) dan terendah (<=2)."""
    if objectives is None:
        objectives = list(
            subject.tujuan_list.filter(academic_year=semester.academic_year).order_by('nomor')
        )
    scores = FormativeScore.objects.filter(
        student=student,
        objective__subject=subject,
        objective__academic_year=semester.academic_year,
        semester=semester,
    ).select_related('objective')
    skor = {}
    teks_tp = {}
    for score in scores:
        skor[score.objective_id] = score.nilai
        teks_tp[score.objective_id] = score.deskripsi_tp or score.objective.deskripsi

    unggul = perlu = None
    if skor:
        tertinggi = max(skor.values())
        if tertinggi >= 3:
            for o in objectives:
                if skor.get(o.id) == tertinggi:
                    unggul = o
                    break
        positif = {oid: v for oid, v in skor.items() if v > 0}
        if positif:
            terendah = min(positif.values())
            if terendah <= 2:
                for o in objectives:
                    if skor.get(o.id) == terendah:
                        perlu = o
                        break

    parts = []
    if unggul:
        parts.append(
            f'Ananda sangat menguasai dalam {teks_tp.get(unggul.id, unggul.deskripsi)}.'
        )
    if perlu:
        parts.append(
            f'Ananda perlu bimbingan dalam {teks_tp.get(perlu.id, perlu.deskripsi)}.'
        )
    return {
        'unggul': unggul,
        'perlu': perlu,
        'teks': ' '.join(parts),
    }


def nilai_lm_map(students, subject, semester):
    qs = SummativeLM.objects.filter(
        student__in=students, subject=subject, semester=semester
    ).values_list('student_id', 'nomor', 'nilai')
    hasil = {}
    for student_id, nomor, nilai in qs:
        hasil.setdefault(student_id, {})[nomor] = nilai
    return hasil


def ringkasan_sumatif(students, subject, semester):
    """Data siap tampil untuk halaman input sumatif (gaya spreadsheet)."""
    students = list(students)
    lm_map = nilai_lm_map(students, subject, semester)
    sumatif = {
        s.student_id: s
        for s in SummativeScore.objects.filter(
            student__in=students, subject=subject, semester=semester
        )
    }
    rows = []
    for siswa in students:
        lm = lm_map.get(siswa.id, {})
        nilai_lm = [lm.get(i) for i in range(1, MAX_LM + 1)]
        terisi = [n for n in nilai_lm if n is not None]
        rata_lm = sum(terisi) / Decimal(len(terisi)) if terisi else None
        obj = sumatif.get(siswa.id)
        sts = obj.sts if obj else None
        non_tes = obj.sas_non_tes if obj else None
        tes = obj.sas_tes if obj else None
        sas = [n for n in (non_tes, tes) if n is not None]
        rata_sas = sum(sas) / Decimal(len(sas)) if sas else None
        bagian = [n for n in (rata_lm, sts, rata_sas) if n is not None]
        nilai_rapor = sum(Decimal(n) for n in bagian) / Decimal(len(bagian)) if bagian else None
        rows.append({
            'siswa': siswa,
            'lm': nilai_lm,
            'rata_lm': rata_lm,
            'sts': sts,
            'sas_non_tes': non_tes,
            'sas_tes': tes,
            'rata_sas': rata_sas,
            'nilai_rapor': nilai_rapor,
        })
    return rows


def nilai_akhir_siswa(student, semester):
    """Nilai akhir per mata pelajaran untuk satu siswa."""
    hasil = {}
    for nilai in SummativeScore.objects.filter(student=student, semester=semester).select_related(
        'subject'
    ):
        hasil[nilai.subject_id] = {
            'nilai': nilai.nilai_rapor,
            'sts': nilai.sts,
            'rata_lm': nilai.rata_lm,
            'rata_sas': nilai.rata_sas,
        }
    return hasil


def data_leger(class_group, semester, students=None):
    if students is None:
        students = list(daftar_siswa(class_group))
    else:
        students = list(students)
    subjects = list(daftar_mapel(semester.academic_year))
    nilai = {}
    for obj in SummativeScore.objects.filter(
        student__in=students, semester=semester
    ).select_related('subject'):
        nilai[(obj.student_id, obj.subject_id)] = obj.nilai_rapor

    rows = []
    for siswa in students:
        row = []
        total = Decimal('0')
        jumlah = 0
        for mapel in subjects:
            n = nilai.get((siswa.id, mapel.id))
            row.append(n)
            if n is not None:
                total += Decimal(n)
                jumlah += 1
        rata = total / jumlah if jumlah else None
        rows.append({'siswa': siswa, 'nilai': row, 'rata': rata})
    return {'subjects': subjects, 'rows': rows}


def data_rapor(student, semester):
    subjects = list(daftar_mapel(semester.academic_year))
    nilai = nilai_akhir_siswa(student, semester)
    mapel_rows = []
    for mapel in subjects:
        info = nilai.get(mapel.id, {})
        capaian = deskripsi_capaian(student, mapel, semester)
        mapel_rows.append({
            'subject': mapel,
            'nilai': info.get('nilai'),
            'capaian': capaian['teks'],
        })

    ekskul = list(
        Extracurricular.objects.filter(student=student, semester=semester).order_by('urutan')
    )
    ekskul_rows = (ekskul + [None] * 5)[:5]
    catatan = HomeroomNote.objects.filter(student=student, semester=semester).first()
    return {
        'student': student,
        'semester': semester,
        'mapel_rows': mapel_rows,
        'ekskul': ekskul,
        'ekskul_rows': ekskul_rows,
        'catatan': catatan,
        'school': School.get_solo(),
    }
