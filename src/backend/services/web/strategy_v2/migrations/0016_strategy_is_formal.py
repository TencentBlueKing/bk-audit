# -*- coding: utf-8 -*-
import os

from django.db import migrations, models

from core.utils.distutils import strtobool


def init_is_formal_from_whitelist(apps, schema_editor):
    """
    初始化历史策略的 is_formal：
    若配置了 PROCESS_RISK_WHITELIST，则将不在白名单内的策略标记为 False。
    若白名单为空，则不做变更，避免误将全部置为 False。
    """

    strategy = apps.get_model('strategy_v2', 'Strategy')
    enable_process_risk_whitelist = strtobool(os.getenv("BKAPP_ENABLE_PROCESS_RISK_WHITELIST", "False"))
    if not enable_process_risk_whitelist:
        return
    process_risk_whitelist = [int(i) for i in os.getenv("BKAPP_PROCESS_RISK_WHITELIST", "").split(",") if i]
    # 按白名单初始化 is_formal 为 False
    if process_risk_whitelist:
        strategy.objects.exclude(strategy_id__in=process_risk_whitelist).update(is_formal=False)


def revert_init_is_formal_noop(apps, schema_editor):
    """
    回滚迁移时会移除字段，本步骤无需做数据还原，保持 NOOP。
    """
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('strategy_v2', '0015_strategytag_strategy_strategytag_tag_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='strategy',
            name='is_formal',
            field=models.BooleanField(default=True, verbose_name='Is Formal'),
        ),
        migrations.RunPython(init_is_formal_from_whitelist, revert_init_is_formal_noop),
    ]
