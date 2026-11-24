import django.db.models.deletion
from django.db import migrations, models


def isi_tahun_tp(apps, schema_editor):
    AcademicYear = apps.get_model('akademik', 'AcademicYear')
    LearningObjective = apps.get_model('akademik', 'LearningObjective')

    tahun = (
        AcademicYear.objects.filter(aktif=True).first()
        or AcademicYear.objects.first()
    )
    if tahun is None:
        return
    LearningObjective.objects.filter(academic_year__isnull=True).update(
        academic_year=tahun, aktif=True
    )


class Migration(migrations.Migration):

    dependencies = [
        ('akademik', '0005_aktifkan_kelas'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='learningobjective',
            unique_together=set(),
        ),
        migrations.AddField(
            model_name='learningobjective',
            name='academic_year',
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='tujuan_list', to='akademik.academicyear',
                verbose_name='Tahun Pelajaran',
            ),
        ),
        migrations.AddField(
            model_name='learningobjective',
            name='aktif',
            field=models.BooleanField(default=True, verbose_name='Aktif'),
        ),
        migrations.RunPython(isi_tahun_tp, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='learningobjective',
            name='academic_year',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='tujuan_list', to='akademik.academicyear',
                verbose_name='Tahun Pelajaran',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='learningobjective',
            unique_together={('subject', 'academic_year', 'nomor')},
        ),
    ]
