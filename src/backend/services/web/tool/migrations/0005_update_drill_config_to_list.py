from django.db import migrations


def migrate_drill_config_to_list(apps, _):
    """
    将 tool 表中 config 字段中的 output_fields 列表中的 drill_config 从单个字典变为字典列表
    """
    Tool = apps.get_model('tool', 'Tool')

    tools = Tool.objects.all()
    for tool in tools:
        output_fields = tool.config.get('output_fields', [])
        for field in output_fields:
            if isinstance(field.get('drill_config'), dict):
                field['drill_config'] = [field['drill_config']]
        tool.save()


class Migration(migrations.Migration):

    dependencies = [
        ('tool', '0004_merge_20250821_1323'),
    ]

    operations = [
        migrations.RunPython(migrate_drill_config_to_list),
    ]
