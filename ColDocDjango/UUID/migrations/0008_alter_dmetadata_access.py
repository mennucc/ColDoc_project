# Generated by Django 4.1.2 on 2022-10-13 07:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('UUID', '0007_uuid_tree_edge_child_ordering'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dmetadata',
            name='access',
            field=models.CharField(choices=[('open', 'view and LaTeX visible to everybody'), ('public', 'view visible to everybody, LaTeX restricted'), ('private', 'visible only to editors, and authors of this blob')], default='public', max_length=15, verbose_name='access policy'),
        ),
    ]
