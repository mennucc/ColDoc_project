# Generated by Django 3.1.1 on 2021-02-25 17:13

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ColDocApp', '0005_20201013_latex_macros'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='dcoldoc',
            name='editor',
        ),
    ]