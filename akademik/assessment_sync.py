"""Sinkronisasi nilai lama (formatif/sumatif) ke model asesmen generik.

Model lama tetap dipakai oleh layar input. Setiap perubahan pada nilai lama
dicerminkan ke `Assessment`/`AssessmentComponent`/`AssessmentResult` agar
perhitungan baru dan data historis tetap konsisten.
"""

from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist

from .models import (
    Assessment,
    AssessmentComponent,
    AssessmentObjective,
    AssessmentResult,
    FormativeScore,
    SummativeLM,
    SummativeScore,
)


def _get_assessment(subject, semester, kategori, nama, nomor=None):
    assessment, _ = Assessment.objects.get_or_create(
        subject=subject,
        semester=semester,
        kategori=kategori,
        nama=nama,
        defaults={
            'academic_year': subject.academic_year,
            'nomor': nomor,
            'status': 'TERBIT',
        },
    )
    return assessment


def _get_component(assessment, nama, **defaults):
    component, _ = AssessmentComponent.objects.get_or_create(
        assessment=assessment, nama=nama, defaults=defaults,
    )
    return component


def _simpan_result(component, student, nilai, guru=None, catatan=''):
    if nilai is None:
        AssessmentResult.objects.filter(component=component, student=student).delete()
        return None
    result, _ = AssessmentResult.objects.update_or_create(
        component=component,
        student=student,
        defaults={'nilai': Decimal(nilai), 'dinilai_oleh': guru, 'catatan': catatan},
    )
    return result


def _hapus_result(component, student):
    AssessmentResult.objects.filter(component=component, student=student).delete()


def sinkron_formatif(score, hapus=False):
    try:
        objective = score.objective
        subject = objective.subject
    except ObjectDoesNotExist:
        return
    semester = score.semester
    nama = f'Formatif TP {objective.nomor}'
    assessment = Assessment.objects.filter(
        subject=subject, semester=semester, kategori='FORMATIF', nama=nama
    ).first()
    if assessment is None:
        if hapus:
            return
        assessment = _get_assessment(
            subject, semester, 'FORMATIF', nama, nomor=objective.nomor,
        )
        AssessmentObjective.objects.get_or_create(
            assessment=assessment, objective=objective,
        )
    component = _get_component(
        assessment, 'Nilai TP',
        tipe='NILAI', urutan=1, bobot=100, nilai_maksimal=4,
    )
    if hapus:
        _hapus_result(component, score.student)
    else:
        _simpan_result(component, score.student, score.nilai, score.guru)


def sinkron_lm(score, hapus=False):
    nama = f'LM {score.nomor}'
    if hapus:
        assessments = Assessment.objects.filter(
            subject_id=score.subject_id, semester_id=score.semester_id,
            kategori='SUMATIF_LM', nama=nama,
        )
        AssessmentResult.objects.filter(
            student_id=score.student_id,
            component__assessment__in=assessments,
        ).delete()
        return
    assessment = Assessment.objects.filter(
        subject=score.subject, semester=score.semester,
        kategori='SUMATIF_LM', nama=nama,
    ).first()
    if assessment is None:
        assessment = _get_assessment(
            score.subject, score.semester, 'SUMATIF_LM', nama, nomor=score.nomor,
        )
    component = _get_component(
        assessment, 'Nilai LM',
        tipe='NILAI', urutan=1, bobot=100, nilai_maksimal=100,
    )
    _simpan_result(component, score.student, score.nilai, score.guru)


def sinkron_sumatif(score, hapus=False):
    if hapus:
        assessments = Assessment.objects.filter(
            subject_id=score.subject_id, semester_id=score.semester_id,
            kategori__in=('STS', 'SAS'),
        )
        component_names = ('STS', 'SAS Non Tes', 'SAS Tes')
        AssessmentResult.objects.filter(
            student_id=score.student_id,
            component__assessment__in=assessments,
            component__nama__in=component_names,
        ).delete()
        return

    subject = score.subject
    semester = score.semester

    sts_assessment = _get_assessment(subject, semester, 'STS', 'STS')
    sts_component = _get_component(
        sts_assessment, 'STS', tipe='TES', urutan=1, bobot=100, nilai_maksimal=100,
    )
    _simpan_result(sts_component, score.student, score.sts, score.guru)

    sas_assessment = _get_assessment(subject, semester, 'SAS', 'SAS')
    non_tes_component = _get_component(
        sas_assessment, 'SAS Non Tes',
        tipe='NON_TES', urutan=1, bobot=50, nilai_maksimal=100,
    )
    tes_component = _get_component(
        sas_assessment, 'SAS Tes',
        tipe='TES', urutan=2, bobot=50, nilai_maksimal=100,
    )
    _simpan_result(non_tes_component, score.student, score.sas_non_tes, score.guru)
    _simpan_result(tes_component, score.student, score.sas_tes, score.guru)


def sinkron_ulang_legacy():
    """Bangun ulang seluruh data asesmen generik dari tabel nilai lama."""
    for score in FormativeScore.objects.select_related('objective', 'semester', 'guru'):
        sinkron_formatif(score)
    for score in SummativeLM.objects.select_related('subject', 'semester', 'guru'):
        sinkron_lm(score)
    for score in SummativeScore.objects.select_related('subject', 'semester', 'guru'):
        sinkron_sumatif(score)
