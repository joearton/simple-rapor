from decimal import Decimal

from django.db import migrations


def _komponen(apps, assessment, nama, tipe, urutan, maksimal, bobot=100):
    AssessmentComponent = apps.get_model('akademik', 'AssessmentComponent')
    component, _ = AssessmentComponent.objects.get_or_create(
        assessment=assessment,
        nama=nama,
        defaults={
            'tipe': tipe,
            'urutan': urutan,
            'bobot': Decimal(bobot),
            'nilai_maksimal': Decimal(maksimal),
        },
    )
    return component


def _hasil(apps, component, student_id, nilai, guru_id=None):
    AssessmentResult = apps.get_model('akademik', 'AssessmentResult')
    if nilai is None:
        AssessmentResult.objects.filter(
            component=component, student_id=student_id
        ).delete()
        return
    AssessmentResult.objects.update_or_create(
        component=component,
        student_id=student_id,
        defaults={'nilai': Decimal(nilai), 'dinilai_oleh_id': guru_id},
    )


def isi_asesmen(apps, schema_editor):
    Assessment = apps.get_model('akademik', 'Assessment')
    AssessmentObjective = apps.get_model('akademik', 'AssessmentObjective')
    FormativeScore = apps.get_model('akademik', 'FormativeScore')
    SummativeLM = apps.get_model('akademik', 'SummativeLM')
    SummativeScore = apps.get_model('akademik', 'SummativeScore')
    GradeConfiguration = apps.get_model('akademik', 'GradeConfiguration')

    GradeConfiguration.objects.get_or_create(
        subject__isnull=True,
        academic_year__isnull=True,
        defaults={'aktif': True},
    )

    for score in FormativeScore.objects.select_related(
        'objective__subject', 'semester', 'guru'
    ).iterator():
        objective = score.objective
        subject = objective.subject
        assessment, _ = Assessment.objects.get_or_create(
            subject_id=subject.id,
            semester_id=score.semester_id,
            kategori='FORMATIF',
            nama=f'Formatif TP {objective.nomor}',
            defaults={
                'academic_year_id': subject.academic_year_id,
                'nomor': objective.nomor,
                'status': 'TERBIT',
            },
        )
        component = _komponen(
            apps, assessment, 'Nilai TP', 'NILAI', 1, 4,
        )
        AssessmentObjective.objects.get_or_create(
            assessment=assessment, objective=objective,
        )
        _hasil(apps, component, score.student_id, score.nilai, score.guru_id)

    for score in SummativeLM.objects.select_related(
        'subject', 'semester', 'guru'
    ).iterator():
        assessment, _ = Assessment.objects.get_or_create(
            subject_id=score.subject_id,
            semester_id=score.semester_id,
            kategori='SUMATIF_LM',
            nama=f'LM {score.nomor}',
            defaults={
                'academic_year_id': score.subject.academic_year_id,
                'nomor': score.nomor,
                'status': 'TERBIT',
            },
        )
        component = _komponen(
            apps, assessment, 'Nilai LM', 'NILAI', 1, 100,
        )
        _hasil(apps, component, score.student_id, score.nilai, score.guru_id)

    for score in SummativeScore.objects.select_related(
        'subject', 'semester', 'guru'
    ).iterator():
        subject = score.subject
        sts_assessment, _ = Assessment.objects.get_or_create(
            subject_id=subject.id,
            semester_id=score.semester_id,
            kategori='STS',
            nama='STS',
            defaults={
                'academic_year_id': subject.academic_year_id,
                'nomor': 0,
                'status': 'TERBIT',
            },
        )
        sts_component = _komponen(
            apps, sts_assessment, 'STS', 'TES', 1, 100,
        )
        _hasil(apps, sts_component, score.student_id, score.sts, score.guru_id)

        sas_assessment, _ = Assessment.objects.get_or_create(
            subject_id=subject.id,
            semester_id=score.semester_id,
            kategori='SAS',
            nama='SAS',
            defaults={
                'academic_year_id': subject.academic_year_id,
                'nomor': 0,
                'status': 'TERBIT',
            },
        )
        non_tes = _komponen(
            apps, sas_assessment, 'SAS Non Tes', 'NON_TES', 1, 100, 50,
        )
        tes = _komponen(
            apps, sas_assessment, 'SAS Tes', 'TES', 2, 100, 50,
        )
        _hasil(apps, non_tes, score.student_id, score.sas_non_tes, score.guru_id)
        _hasil(apps, tes, score.student_id, score.sas_tes, score.guru_id)


class Migration(migrations.Migration):

    dependencies = [
        ('akademik', '0017_assessment_assessmentcomponent_assessmentobjective_and_more'),
    ]

    operations = [
        migrations.RunPython(isi_asesmen, migrations.RunPython.noop),
    ]
