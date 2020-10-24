# Generated by Django 3.1.1 on 2020-10-18 11:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('UUID', '0006_20201010_allow_empty_latex_time'),
    ]

    operations = [
        migrations.AddField(
            model_name='uuid_tree_edge',
            name='child_ordering',
            field=models.IntegerField(default=0, verbose_name='used to order the children as in the TeX'),
        ),
        migrations.AlterModelOptions(
            name='uuid_tree_edge',
            options={'ordering': ['coldoc', 'parent', 'child_ordering', 'child']},
        ),
    ]