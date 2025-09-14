# Generated migration to rename inspection_type to tipo_combustible

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0008_alter_inspectionphoto_photo_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='inspection',
            old_name='inspection_type',
            new_name='tipo_combustible',
        ),
        migrations.AlterField(
            model_name='inspection',
            name='tipo_combustible',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('quality', 'Control de Calidad'),
                    ('safety', 'Inspección de Seguridad'),
                    ('compliance', 'Verificación de Cumplimiento'),
                    ('performance', 'Prueba de Rendimiento'),
                    ('visual', 'Inspección Visual'),
                ],
                default='quality',
                help_text="Tipo de combustible que se está inspeccionando"
            ),
        ),
    ]
