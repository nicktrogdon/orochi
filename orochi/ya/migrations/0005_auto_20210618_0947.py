# Generated by Django 3.2.4 on 2021-06-18 09:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ya", "0004_rule_compiled"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="rule",
            name="deleted",
        ),
        migrations.RemoveField(
            model_name="ruleset",
            name="deleted",
        ),
        migrations.AddField(
            model_name="ruleset",
            name="cloned",
            field=models.BooleanField(default=False),
        ),
    ]