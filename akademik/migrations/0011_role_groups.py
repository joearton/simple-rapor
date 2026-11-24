from django.db import migrations

ROLE_GROUPS = [
    'Super Admin',
    'Kepala Sekolah',
    'Operator/Tata Usaha',
    'Guru Mata Pelajaran',
    'Wali Kelas',
    'Siswa/Orang Tua',
]


def siapkan_role(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')
    Teacher = apps.get_model('akademik', 'Teacher')

    for name in ROLE_GROUPS:
        Group.objects.get_or_create(name=name)

    super_group = Group.objects.get(name='Super Admin')
    guru_group = Group.objects.get(name='Guru Mata Pelajaran')
    operator_group = Group.objects.get(name='Operator/Tata Usaha')

    for user in User.objects.all():
        is_teacher = Teacher.objects.filter(user=user).exists()
        if user.is_superuser:
            user.groups.add(super_group)
        elif is_teacher:
            user.groups.add(guru_group)
        elif user.is_staff:
            user.groups.add(operator_group)


class Migration(migrations.Migration):

    dependencies = [
        ('akademik', '0010_auditlog'),
    ]

    operations = [
        migrations.RunPython(siapkan_role, migrations.RunPython.noop),
    ]
