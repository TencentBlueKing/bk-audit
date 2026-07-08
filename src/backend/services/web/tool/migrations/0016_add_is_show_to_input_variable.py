from django.db import migrations


def add_is_show_to_input_variable(apps, _):
    """
    为数据查询类型(data_search)工具的 config.input_variable 补全 is_show 字段
    （默认 True，用户可见）。兼容 is_show 特性上线前的存量数据。
    """
    Tool = apps.get_model('tool', 'Tool')

    for tool in Tool.objects.filter(tool_type='data_search'):
        config = tool.config or {}
        input_variable = config.get('input_variable', [])
        changed = False
        for var in input_variable:
            if isinstance(var, dict) and 'is_show' not in var:
                var['is_show'] = True
                changed = True
        if changed:
            tool.save()


class Migration(migrations.Migration):

    dependencies = [
        ('tool', '0015_restore_tool_uid_version_unique'),
    ]

    operations = [
        migrations.RunPython(add_is_show_to_input_variable, migrations.RunPython.noop),
    ]
