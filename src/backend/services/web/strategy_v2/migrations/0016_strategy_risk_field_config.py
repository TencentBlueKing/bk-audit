from django.db import migrations, models
from django.utils.translation import gettext_lazy


class Migration(migrations.Migration):
    dependencies = [
        ("strategy_v2", "0015_strategytag_strategy_strategytag_tag_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name='strategy',
            name='risk_meta_field_config',
            field=models.JSONField(blank=True, default=list, null=True, verbose_name='Risk Meta Field Config'),
        ),
        migrations.AlterField(
            model_name='strategytool',
            name='field_source',
            field=models.CharField(
                choices=[('basic', '基本字段'), ('data', '数据字段'), ('evidence', '证据字段'), ('risk_meta', '风险元字段')],
                max_length=16,
                verbose_name='字段来源',
            ),
        ),
    ]
