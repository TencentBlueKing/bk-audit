from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("risk", "0060_add_risk_scene_id_and_backfill"),
    ]

    operations = [
        migrations.AddField(
            model_name="nl2riskfilterlog",
            name="risk_view_type",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                max_length=32,
                verbose_name="风险视图类型",
            ),
        ),
    ]
