# -*- coding: utf-8 -*-
from django.db import migrations, models


def init_is_formal_from_whitelist(apps, schema_editor):
    """
    初始化历史策略的 is_formal：
    若配置了 PROCESS_RISK_WHITELIST，则将不在白名单内的策略标记为 False。
    若白名单为空，则不做变更，避免误将全部置为 False。
    """
    from django.conf import settings

    Strategy = apps.get_model('strategy_v2', 'Strategy')
    whitelist = getattr(settings, 'PROCESS_RISK_WHITELIST', []) or []
    # 仅当白名单非空时，按白名单初始化，避免误伤
    if whitelist:
        Strategy.objects.exclude(strategy_id__in=whitelist).update(is_formal=False)


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
