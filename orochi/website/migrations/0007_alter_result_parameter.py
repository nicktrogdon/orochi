# Generated by Django 3.2 on 2020-08-03 08:36

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0006_result_parameter'),
    ]

    operations = [
        migrations.AlterField(
            model_name='result',
            name='parameter',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True),
        ),
    ]
