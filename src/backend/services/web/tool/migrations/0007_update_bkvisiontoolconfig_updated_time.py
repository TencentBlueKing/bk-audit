from django.db import migrations, models


def copy_updated_at_to_updated_time(apps, _):
    """将 BkVisionToolConfig 中的 updated_at 字段赋值给 updated_time 字段"""
    BkVisionToolConfig = apps.get_model('tool', 'BkVisionToolConfig')
    for config in BkVisionToolConfig.objects.all():
        if config.updated_at:
            config.updated_time = config.updated_at
            config.save(update_fields=['updated_time'])


class Migration(migrations.Migration):

    dependencies = [
        ('tool', '0006_bkvisiontoolconfig_updated_time_tool_is_bkvision'),
    ]

    operations = [
        migrations.RunPython(copy_updated_at_to_updated_time),
    ]
