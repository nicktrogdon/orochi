import os

from colorfield.fields import ColorField
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from guardian.shortcuts import assign_perm

from orochi.ya.models import Ruleset

OPERATING_SYSTEM = (
    ("Linux", "Linux"),
    ("Windows", "Windows"),
    ("Mac", "Mac"),
    ("Other", "Other"),
)

SERVICE_VIRUSTOTAL = 1
SERVICE_MISP = 2
SERVICE_MAXMIND = 3
SERVICES = (
    (SERVICE_VIRUSTOTAL, "VirusTotal"),
    (SERVICE_MISP, "MISP"),
    (SERVICE_MAXMIND, "MAXMIND"),
)

DUMP_STATUS_CREATED = 1
DUMP_STATUS_COMPLETED = 2
DUMP_STATUS_DELETED = 3
DUMP_STATUS_ERROR = 4
STATUS = (
    (DUMP_STATUS_CREATED, "Created"),
    (DUMP_STATUS_COMPLETED, "Completed"),
    (DUMP_STATUS_DELETED, "Deleted"),
    (DUMP_STATUS_ERROR, "Error"),
)

RESULT_STATUS_RUNNING = 0
RESULT_STATUS_EMPTY = 1
RESULT_STATUS_SUCCESS = 2
RESULT_STATUS_UNSATISFIED = 3
RESULT_STATUS_ERROR = 4
RESULT_STATUS_DISABLED = 5
RESULT = (
    (RESULT_STATUS_RUNNING, "Running"),
    (RESULT_STATUS_EMPTY, "Empty"),
    (RESULT_STATUS_SUCCESS, "Success"),
    (RESULT_STATUS_UNSATISFIED, "Unsatisfied"),
    (RESULT_STATUS_ERROR, "Error"),
    (RESULT_STATUS_DISABLED, "Disabled"),
)
ICONS = (
    ("ss-arn", "Arabian Nights"),
    ("ss-atq", "Antiquities"),
    ("ss-leg", "Legends"),
    ("ss-drk", "The Dark"),
    ("ss-fem", "Fallen Empires"),
    ("ss-hml", "Homelands"),
    ("ss-ice", "Ice Age"),
    ("ss-ice2", "Ice Age (Original)"),
    ("ss-all", "Alliances"),
    ("ss-csp", "Coldsnap"),
    ("ss-mir", "Mirage"),
    ("ss-vis", "Visions"),
    ("ss-wth", "Weatherlight"),
    ("ss-tmp", "Tempest"),
    ("ss-sth", "Stronghold"),
    ("ss-exo", "Exodus"),
    ("ss-usg", "Urza's Saga"),
    ("ss-ulg", "Urza's Legacy"),
    ("ss-uds", "Urza's Destiny"),
    ("ss-mmq", "Mercadian Masques"),
    ("ss-nem", "Nemesis"),
    ("ss-pcy", "Prophecy"),
    ("ss-inv", "Invasion"),
    ("ss-pls", "Planeshift"),
    ("ss-apc", "Apocalypse"),
    ("ss-ody", "Odyssey"),
    ("ss-tor", "Torment"),
    ("ss-jud", "Judgement"),
    ("ss-ons", "Onslaught"),
    ("ss-lgn", "Legions"),
    ("ss-scg", "Scourge"),
    ("ss-mrd", "Mirrodin"),
    ("ss-dst", "Darksteel"),
    ("ss-5dn", "Fifth Dawn"),
    ("ss-chk", "Champions of Kamigawa"),
    ("ss-bok", "Betrayers of Kamigawa"),
    ("ss-sok", "Saviors of Kamigawa"),
    ("ss-rav", "Ravnica"),
    ("ss-gpt", "Guildpact"),
    ("ss-dis", "Dissension"),
    ("ss-tsp", "Time Spiral"),
    ("ss-plc", "Planar Chaos"),
    ("ss-fut", "Future Sight"),
    ("ss-lrw", "Lorwyn"),
    ("ss-mor", "Morningtide"),
    ("ss-shm", "Shadowmoor"),
    ("ss-eve", "Eventide"),
    ("ss-ala", "Shards of Alara"),
    ("ss-con", "Conflux"),
    ("ss-arb", "Alara Reborn"),
    ("ss-zen", "Zendikar"),
    ("ss-wwk", "Worldwake"),
    ("ss-roe", "Rise of the Eldrazi"),
    ("ss-som", "Scars of Mirrodin"),
    ("ss-mbs", "Mirrodin Besieged"),
    ("ss-nph", "New Phyrexia"),
    ("ss-isd", "Innistrad"),
    ("ss-dka", "Dark Ascension"),
    ("ss-avr", "Avacyn Restored"),
    ("ss-rtr", "Return to Ravnica"),
    ("ss-gtc", "Gatecrash"),
    ("ss-dgm", "Dragon's Maze"),
    ("ss-ths", "Theros"),
    ("ss-bng", "Born of the Gods"),
    ("ss-jou", "Journey into Nyx"),
    ("ss-ktk", "Khans of Tarkir"),
    ("ss-frf", "Fate Reforged"),
    ("ss-dtk", "Dragons of Tarkir"),
    ("ss-bfz", "Battle for Zendikar"),
    ("ss-ogw", "Oath of the Gatewatch"),
    ("ss-soi", "Shadows Over Innistrad"),
    ("ss-emn", "Eldritch Moon"),
    ("ss-kld", "Kaladesh"),
    ("ss-aer", "Aether Revolt"),
    ("ss-akh", "Amonkhet"),
    ("ss-hou", "Hour of Devastation"),
    ("ss-xln", "Ixalan"),
    ("ss-rix", "Rivals of Ixalan"),
    ("ss-dom", "Dominaria"),
    ("ss-grn", "Guilds of Ravnica"),
    ("ss-rna", "Ravnica Allegiance"),
    ("ss-war", "War of the Spark"),
    ("ss-eld", "Throne of Eldraine"),
    ("ss-thb", "Theros: Beyond Death"),
    ("ss-iko", "koria: Lair of Behemoths"),
    ("ss-znr", "Zendikar Rising"),
    ("ss-khm", "Kaldheim"),
    ("ss-stx", "Strixhaven: School of Mages"),
    ("ss-mid", "Innistrad: Midnight Hunt"),
    ("ss-vow", "Innistrad: Crimson Vow"),
    ("ss-neo", "Kamigawa: Neon Dynasty"),
    ("ss-snc", "Streets of New Capenna"),
    ("ss-dmu", "Dominaria United"),
    ("ss-bro", "The Brothers' War"),
    ("ss-one", "Phyrexia: All Will Be One"),
    ("ss-mom", "March of the Machine"),
    ("ss-mat", "March of the Machine: The Aftermath"),
    ("ss-woe", "Wilds of Eldraine"),
)

DEFAULT_YARA_PATH = "/yara/default.yara"


class Service(models.Model):
    name = models.PositiveIntegerField(choices=SERVICES, unique=True)
    url = models.CharField(max_length=250)
    key = models.CharField(max_length=250)
    proxy = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.get_name_display()}"


class Plugin(models.Model):
    name = models.CharField(max_length=250, unique=True)
    operating_system = models.CharField(
        choices=OPERATING_SYSTEM, default="Linux", max_length=10
    )
    disabled = models.BooleanField(default=False)
    local_dump = models.BooleanField(default=False)
    vt_check = models.BooleanField(default=False)
    clamav_check = models.BooleanField(default=False)
    regipy_check = models.BooleanField(default=False)
    yara_check = models.BooleanField(default=False)
    maxmind_check = models.BooleanField(default=False)
    local = models.BooleanField(default=False)
    local_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return self.name


class UserPlugin(models.Model):
    plugin = models.ForeignKey(Plugin, on_delete=models.CASCADE)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="plugins"
    )
    automatic = models.BooleanField(default=False)

    class Meta:
        ordering = ("plugin__name",)

    def __str__(self):
        return self.plugin.name


class Dump(models.Model):
    operating_system = models.CharField(
        choices=OPERATING_SYSTEM, default="Linux", max_length=10
    )
    banner = models.CharField(max_length=500, blank=True, null=True)
    upload = models.FileField(upload_to="uploads")
    name = models.CharField(max_length=250)
    index = models.CharField(max_length=250, unique=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    color = ColorField(default="#FF0000")
    status = models.PositiveSmallIntegerField(choices=STATUS, default=1)
    plugins = models.ManyToManyField(Plugin, through="Result")
    missing_symbols = models.BooleanField(default=False)
    md5 = models.CharField(max_length=32, blank=True, null=True)
    sha256 = models.CharField(max_length=64, blank=True, null=True)
    size = models.BigIntegerField(null=True)
    suggested_symbols_path = ArrayField(
        models.CharField(max_length=1000, blank=True, null=True), blank=True, null=True
    )

    def __str__(self):
        return self.name

    class Meta:
        permissions = (("can_see", "Can See"),)
        verbose_name_plural = "Dumps"
        unique_together = ["name", "author"]


class Result(models.Model):
    dump = models.ForeignKey(Dump, on_delete=models.CASCADE)
    plugin = models.ForeignKey(Plugin, on_delete=models.CASCADE)
    result = models.PositiveSmallIntegerField(choices=RESULT, default=0)
    description = models.TextField(blank=True, null=True)
    parameter = models.JSONField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (
            "dump",
            "plugin",
        )

    def __str__(self):
        return f"{self.dump.name} [{self.plugin.name}]"


class ExtractedDump(models.Model):
    path = models.CharField(max_length=250, unique=True)
    result = models.ForeignKey(Result, on_delete=models.CASCADE)
    md5 = models.CharField(max_length=32, blank=True, null=True)
    sha256 = models.CharField(max_length=64, blank=True, null=True)
    clamav = models.CharField(max_length=250, blank=True, null=True)
    vt_report = models.JSONField(blank=True, null=True)
    reg_array = models.JSONField(blank=True, null=True)


class Bookmark(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookmarks"
    )
    indexes = models.ManyToManyField(Dump)
    plugin = models.ForeignKey(Plugin, on_delete=models.CASCADE)
    name = models.CharField(max_length=250)
    icon = models.CharField(choices=ICONS, default="ss-ori", max_length=50)
    star = models.BooleanField(default=False)
    query = models.CharField(max_length=500, blank=True, null=True)

    class Meta:
        unique_together = ["name", "user"]

    @property
    def indexes_list(self):
        return ",".join([p.index for p in self.indexes.all()])

    @property
    def indexes_names_list(self):
        return ", ".join([p.name for p in self.indexes.all()])

    def __str__(self):
        return f"{self.name}"


def user_directory_path(instance, filename):
    return "user_{0}/{1}"


class CustomRule(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rules"
    )
    name = models.CharField(max_length=250)
    public = models.BooleanField(default=False)
    path = models.CharField(max_length=255)
    default = models.BooleanField(default=False)


@receiver(post_save, sender=Dump)
def set_permission(sender, instance, created, **kwargs):
    """Add object specific permission to the author"""
    if created:
        assign_perm(
            "website.can_see",
            instance.author,
            instance,
        )


@receiver(post_save, sender=get_user_model())
def get_plugins(sender, instance, created, **kwargs):
    if created:
        UserPlugin.objects.bulk_create(
            [
                UserPlugin(user=instance, plugin=plugin)
                for plugin in Plugin.objects.all()
            ]
        )
        Ruleset.objects.create(
            name=f"{instance.username}-Ruleset",
            user=instance,
            description="Your crafted ruleset",
        )
        if os.path.exists(DEFAULT_YARA_PATH):
            CustomRule.objects.create(
                user=instance,
                path=DEFAULT_YARA_PATH,
                default=True,
                name="DEFAULT",
            )


@receiver(post_save, sender=Plugin)
def new_plugin(sender, instance, created, **kwargs):
    if created:
        # Add new plugin in old dump
        for dump in Dump.objects.all():
            if instance.operating_system in [dump.operating_system, "Other"]:
                up, created = Result.objects.get_or_create(dump=dump, plugin=instance)
                up.result = RESULT_STATUS_DISABLED
                up.save()

        # Add new plugin to user
        for user in get_user_model().objects.all():
            up, created = UserPlugin.objects.get_or_create(user=user, plugin=instance)
