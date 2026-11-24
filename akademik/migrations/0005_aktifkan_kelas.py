from django.db import migrations


def aktifkan_kelas(apps, schema_editor):
    ClassGroup = apps.get_model('akademik', 'ClassGroup')
    ClassGroup.objects.update(aktif=False)
    kelas = (
        ClassGroup.objects.filter(academic_year__aktif=True).first()
        or ClassGroup.objects.first()
    )
    if kelas:
        kelas.aktif = True
        kelas.save(update_fields=['aktif'])


class Migration(migrations.Migration):

    dependencies = [
        ('akademik', '0004_classgroup_aktif_school_font_rapor_and_more'),
    ]

    operations = [
        migrations.RunPython(aktifkan_kelas, migrations.RunPython.noop),
    ]
