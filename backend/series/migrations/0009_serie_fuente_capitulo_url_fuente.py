# Generated manually — agrega campo fuente a Serie, renombra url_jkanime a url_fuente en Capitulo

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('series', '0008_capitulo_ultimo_segundo'),
    ]

    operations = [
        # Agregar campo fuente a Serie (default 'jkanime')
        migrations.AddField(
            model_name='serie',
            name='fuente',
            field=models.CharField(default='jkanime', help_text='Fuente: jkanime, latanime', max_length=50),
        ),
        # Renombrar url_jkanime -> url_fuente en Capitulo
        migrations.RenameField(
            model_name='capitulo',
            old_name='url_jkanime',
            new_name='url_fuente',
        ),
        # Actualizar help_text del campo renombrado
        migrations.AlterField(
            model_name='capitulo',
            name='url_fuente',
            field=models.URLField(help_text='URL del capítulo en la fuente', max_length=500),
        ),
        # Actualizar help_text del campo url en Serie
        migrations.AlterField(
            model_name='serie',
            name='url',
            field=models.URLField(help_text='URL de la serie en la fuente', max_length=500),
        ),
    ]
