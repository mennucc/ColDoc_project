# Generated by Django 4.1.2 on 2022-11-08 09:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('UUID', '0008_alter_dmetadata_access'),
    ]

    operations = [
        migrations.AddField(
            model_name='extrametadata',
            name='second_value',
            field=models.CharField(blank=True, max_length=250, null=True),
        ),
    ]
