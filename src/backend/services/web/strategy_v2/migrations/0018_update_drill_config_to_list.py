from django.db import migrations, models


def migrate_drill_config_to_list(apps, _):
    """
    将 Strategy 表中 config 字段中的 drill_config 从单个字典变为字典列表
    """
    Strategy = apps.get_model('strategy_v2', 'Strategy')

    strategy_data = Strategy.objects.all()

    for strategy in strategy_data:
        if strategy.event_basic_field_configs:
            for field in strategy.event_basic_field_configs:
                if isinstance(field.get('drill_config'), dict):
                    field['drill_config'] = [field['drill_config']]
        if strategy.event_data_field_configs:
            for field in strategy.event_data_field_configs:
                if isinstance(field.get('drill_config'), dict):
                    field['drill_config'] = [field['drill_config']]
        if strategy.event_evidence_field_configs:
            for field in strategy.event_evidence_field_configs:
                if isinstance(field.get('drill_config'), dict):
                    field['drill_config'] = [field['drill_config']]

        strategy.save(
            update_fields=['event_basic_field_configs', 'event_data_field_configs', 'event_evidence_field_configs']
        )


class Migration(migrations.Migration):

    dependencies = [
        ('strategy_v2', '0017_strategy_risk_field_config'),
    ]

    operations = [
        migrations.RunPython(migrate_drill_config_to_list),
    ]
