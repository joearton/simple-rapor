from django.db import migrations


def tautkan_wali(apps, schema_editor):
    ClassGroup = apps.get_model('akademik', 'ClassGroup')
    Teacher = apps.get_model('akademik', 'Teacher')
    Extracurricular = apps.get_model('akademik', 'Extracurricular')

    for kelas in ClassGroup.objects.all():
        if kelas.wali_kelas and not kelas.wali_kelas_guru_id:
            guru = Teacher.objects.filter(nama__iexact=kelas.wali_kelas).first()
            if guru is None:
                guru = Teacher.objects.create(
                    nama=kelas.wali_kelas,
                    nktam=kelas.nktam_wali or '',
                    aktif=True,
                )
            kelas.wali_kelas_guru = guru
            kelas.save(update_fields=['wali_kelas_guru'])

    for eks in Extracurricular.objects.filter(guru__isnull=True).select_related('student'):
        wali = eks.student.class_group.wali_kelas_guru
        if wali:
            eks.guru = wali
            eks.save(update_fields=['guru'])


class Migration(migrations.Migration):

    dependencies = [
        ('akademik', '0002_alter_classgroup_wali_kelas_teacher_and_more'),
    ]

    operations = [
        migrations.RunPython(tautkan_wali, migrations.RunPython.noop),
    ]
