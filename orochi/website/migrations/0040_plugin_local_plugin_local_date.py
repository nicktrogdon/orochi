# Generated by Django 4.0.1 on 2022-01-22 13:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("website", "0039_auto_20211119_1654"),
    ]

    operations = [
        migrations.AddField(
            model_name="plugin",
            name="local",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="plugin",
            name="local_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]