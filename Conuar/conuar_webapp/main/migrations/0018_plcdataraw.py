# Generated migration for PlcDataRaw model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0017_add_plc_message_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlcDataRaw',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(help_text='Timestamp del dato PLC')),
                ('json_data', models.TextField(help_text='Datos JSON sin procesar del PLC')),
                ('processed', models.BooleanField(default=False, help_text='Indica si el registro ya fue procesado')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'PLC Data Raw',
                'verbose_name_plural': 'PLC Data Raw',
                'db_table': 'plc_data_raw',
                'ordering': ['-timestamp'],
                'indexes': [
                    models.Index(fields=['timestamp'], name='plc_data_ra_timesta_idx'),
                    models.Index(fields=['processed'], name='plc_data_ra_process_idx'),
                ],
            },
        ),
    ]

