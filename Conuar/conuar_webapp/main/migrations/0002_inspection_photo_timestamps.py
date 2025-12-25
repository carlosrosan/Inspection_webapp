# Generated manually for adding photo timestamps to Inspection model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='inspection',
            name='photo_start_timestamp',
            field=models.DateTimeField(blank=True, help_text='Timestamp de la primera foto de la inspección (extraído del nombre del archivo)', null=True),
        ),
        migrations.AddField(
            model_name='inspection',
            name='photo_finish_timestamp',
            field=models.DateTimeField(blank=True, help_text='Timestamp de la última foto de la inspección (extraído del nombre del archivo)', null=True),
        ),
    ]

