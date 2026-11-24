from django.db import migrations


TINGKAT_AWAL = [('VII', 'D', 1), ('VIII', 'D', 2), ('IX', 'D', 3)]


def isi_awal(apps, schema_editor):
    Grade = apps.get_model('akademik', 'Grade')
    ClassGroup = apps.get_model('akademik', 'ClassGroup')
    Student = apps.get_model('akademik', 'Student')
    StudentEnrollment = apps.get_model('akademik', 'StudentEnrollment')

    for nama, fase, urutan in TINGKAT_AWAL:
        Grade.objects.get_or_create(
            nama=nama, defaults={'fase': fase, 'urutan': urutan, 'aktif': True}
        )

    for kelas in ClassGroup.objects.all():
        if not kelas.tingkat:
            continue
        grade = Grade.objects.filter(nama=kelas.tingkat).first()
        if grade is None:
            grade = Grade.objects.create(
                nama=kelas.tingkat,
                fase=kelas.fase or 'D',
                urutan=0,
                aktif=True,
            )
        if kelas.grade_id != grade.id:
            ClassGroup.objects.filter(pk=kelas.pk).update(grade=grade)

    for siswa in Student.objects.select_related('class_group').iterator():
        if not siswa.class_group_id:
            continue
        StudentEnrollment.objects.get_or_create(
            student_id=siswa.pk,
            academic_year_id=siswa.class_group.academic_year_id,
            defaults={
                'class_group_id': siswa.class_group_id,
                'status': 'AKTIF',
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('akademik', '0014_grade_studentenrollment_and_more'),
    ]

    operations = [
        migrations.RunPython(isi_awal, migrations.RunPython.noop),
    ]
