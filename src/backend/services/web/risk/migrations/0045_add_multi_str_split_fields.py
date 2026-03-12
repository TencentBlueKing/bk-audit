import blueapps.utils.db
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("risk", "0044_backfill_display_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="risk",
            name="operator_str",
            field=blueapps.utils.db.MultiStrSplitCharField(
                verbose_name="Operator (Str)", max_length=512, default="", blank=True
            ),
        ),
        migrations.AddField(
            model_name="risk",
            name="current_operator_str",
            field=blueapps.utils.db.MultiStrSplitCharField(
                verbose_name="Current Operator (Str)", max_length=512, default="", blank=True
            ),
        ),
        migrations.AddField(
            model_name="risk",
            name="notice_users_str",
            field=blueapps.utils.db.MultiStrSplitCharField(
                verbose_name="Notice Users (Str)", max_length=512, default="", blank=True
            ),
        ),
    ]
