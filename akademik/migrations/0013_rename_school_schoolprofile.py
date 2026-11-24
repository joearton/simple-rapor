from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('akademik', '0012_alter_learningobjective_options_and_more'),
    ]

    operations = [
        migrations.RenameModel(old_name='School', new_name='SchoolProfile'),
    ]
