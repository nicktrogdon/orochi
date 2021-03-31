# Generated by Django 3.1.6 on 2021-02-12 13:19

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("website", "0030_auto_20210211_1657"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bookmark",
            name="icon",
            field=models.CharField(
                choices=[
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
                ],
                default="ss-ori",
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="dump",
            name="name",
            field=models.CharField(max_length=250),
        ),
        migrations.AlterUniqueTogether(
            name="bookmark",
            unique_together={("name", "user")},
        ),
        migrations.AlterUniqueTogether(
            name="dump",
            unique_together={("name", "author")},
        ),
    ]