from django.db import migrations
from django.utils.text import slugify

NILAI_PREDIKAT = {
    'A': 90,
    'B': 80,
    'C': 70,
    'D': 60,
}


def _slug_unik(Activity, nama):
    dasar = slugify(nama) or 'ekskul'
    slug = dasar
    nomor = 2
    while Activity.objects.filter(slug=slug).exists():
        slug = f'{dasar}-{nomor}'
        nomor += 1
    return slug


def isi_ekskul(apps, schema_editor):
    Activity = apps.get_model('akademik', 'ExtracurricularActivity')
    Enrollment = apps.get_model('akademik', 'ExtracurricularEnrollment')
    Predicate = apps.get_model('akademik', 'ExtracurricularPredicate')
    Extracurricular = apps.get_model('akademik', 'Extracurricular')

    for label, batas, urutan in (
        ('A', 85, 1), ('B', 75, 2), ('C', 65, 3), ('D', 0, 4),
    ):
        Predicate.objects.get_or_create(
            label=label,
            defaults={
                'batas_min': batas,
                'urutan': urutan,
                'aktif': True,
                'deskripsi': f'Predikat {label}',
            },
        )

    cache = {}
    for lama in Extracurricular.objects.exclude(nama='').iterator():
        nama = lama.nama.strip()
        if not nama:
            continue
        if nama.lower() not in cache:
            activity, _ = Activity.objects.get_or_create(
                nama=nama,
                defaults={
                    'slug': _slug_unik(Activity, nama),
                    'pembina_id': lama.guru_id,
                    'deskripsi': lama.deskripsi,
                    'urutan': lama.urutan,
                    'aktif': True,
                },
            )
            cache[nama.lower()] = activity
        activity = cache[nama.lower()]
        nilai = NILAI_PREDIKAT.get((lama.predikat or '').strip().upper())
        Enrollment.objects.update_or_create(
            activity=activity,
            student_id=lama.student_id,
            semester_id=lama.semester_id,
            defaults={
                'academic_year_id': lama.academic_year_id,
                'nilai': nilai,
                'predikat': lama.predikat,
                'deskripsi': lama.deskripsi,
                'guru_id': lama.guru_id,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('akademik', '0021_extracurricularpredicate_extracurricularactivity_and_more'),
    ]

    operations = [
        migrations.RunPython(isi_ekskul, migrations.RunPython.noop),
    ]
