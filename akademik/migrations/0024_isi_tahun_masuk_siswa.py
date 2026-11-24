from django.db import migrations


def isi_tahun_masuk(apps, schema_editor):
    Student = apps.get_model('akademik', 'Student')
    Enrollment = apps.get_model('akademik', 'StudentEnrollment')

    for student in Student.objects.select_related('class_group').iterator():
        awal = (
            Enrollment.objects.filter(student_id=student.pk)
            .select_related('academic_year')
            .order_by('academic_year__tahun')
            .first()
        )
        if awal is not None:
            tahun_id = awal.academic_year_id
        elif student.class_group_id:
            tahun_id = student.class_group.academic_year_id
        else:
            continue
        if student.tahun_masuk_id != tahun_id:
            Student.objects.filter(pk=student.pk).update(tahun_masuk_id=tahun_id)


class Migration(migrations.Migration):

    dependencies = [
        ('akademik', '0023_student_tahun_masuk'),
    ]

    operations = [
        migrations.RunPython(isi_tahun_masuk, migrations.RunPython.noop),
    ]
