# 手动创建：将 Tool.status 的数据库列默认值从 'published' 改为 'unpublished'
# 背景：migration 0011 新增 status 字段时 default='published'，目的是让存量工具默认已发布；
# 而 Model 定义中 default=PanelStatus.UNPUBLISHED，新建工具应默认未发布。
# 此 migration 将数据库列默认值同步为 'unpublished'，已有数据不受影响。

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tool', '0012_resource_binding_refactor'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tool',
            name='status',
            field=models.CharField(
                blank=True,
                default='unpublished',
                help_text='published/unpublished',
                max_length=32,
                verbose_name='上架状态',
                # 新建工具默认未发布；存量工具通过 migration 0011 默认设为 published
            ),
        ),
    ]
