# Generated by Django 5.0.6 on 2024-08-07 20:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('servicios', '0002_comentario_calificacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='comentario',
            name='fecha',
            field=models.DateField(default='2024-01-01'),
            preserve_default=False,
        ),
    ]
