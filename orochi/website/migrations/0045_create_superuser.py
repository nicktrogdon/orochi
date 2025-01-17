from django.db import migrations
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress


def generate_superuser(app, schema_editor):
    superusers = get_user_model().objects.filter(is_superuser=True).count()
    if superusers == 0:
        superuser = get_user_model().objects.create_superuser(
            username="admin", email="admin@orochi.local", password="admin"
        )
        superuser.save()
        email, _ = EmailAddress.objects.get_or_create(
            user=superuser, email=superuser.email
        )
        email.verified = True
        email.save()


class Migration(migrations.Migration):
    dependencies = [
        ("website", "0044_plugin_maxmind_check"),
        ("ya", "0005_auto_20210618_0947"),
    ]

    operations = [
        migrations.RunPython(generate_superuser),
    ]
