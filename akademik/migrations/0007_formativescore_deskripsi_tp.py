from django.db import migrations, models


def isi_snapshot(apps, schema_editor):
    FormativeScore = apps.get_model('akademik', 'FormativeScore')
    for score in FormativeScore.objects.select_related('objective'):
        if not score.deskripsi_tp:
            score.deskripsi_tp = score.objective.deskripsi
            score.save(update_fields=['deskripsi_tp'])


class Migration(migrations.Migration):

    dependencies = [
        ('akademik', '0006_alter_learningobjective_unique_together_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='formativescore',
            name='deskripsi_tp',
            field=models.TextField(blank=True, verbose_name='Deskripsi TP saat dinilai'),
        ),
        migrations.RunPython(isi_snapshot, migrations.RunPython.noop),
    ]
