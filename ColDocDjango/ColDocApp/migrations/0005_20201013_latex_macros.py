# Generated by Django 3.1.1 on 2020-10-13 11:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ColDocApp', '0004_dcoldoc_author_can_add_blob'),
    ]

    operations = [
        migrations.AddField(
            model_name='dcoldoc',
            name='latex_macros_private',
            field=models.TextField(blank=True, default='\\newif\\ifColDocPublic\\ColDocPublicfalse\n\\newif\\ifColDocOneUUID\\ColDocOneUUIDfalse\n', max_length=1000),
        ),
        migrations.AddField(
            model_name='dcoldoc',
            name='latex_macros_public',
            field=models.TextField(blank=True, default='\\newif\\ifColDocPublic\\ColDocPublictrue \n\\newif\\ifColDocOneUUID\\ColDocOneUUIDfalse\n', max_length=1000),
        ),
        migrations.AddField(
            model_name='dcoldoc',
            name='latex_macros_uuid',
            field=models.TextField(blank=True, default='\\newif\\ifColDocPublic\\ColDocPublicfalse\n\\newif\\ifColDocOneUUID\\ColDocOneUUIDtrue\n', max_length=1000),
        ),
    ]
