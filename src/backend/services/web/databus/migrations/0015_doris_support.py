import django.db.models.deletion
from django.db import migrations, models


def migrate_hdfs_fields(apps, schema_editor):
    Snapshot = apps.get_model('databus', 'Snapshot')

    # 迁移 hdfs_xx 字段到新的字段
    snapshots_to_migrate = Snapshot.objects.filter(hdfs_status__isnull=False)

    for snapshot in snapshots_to_migrate:
        # 迁移 hdfs_status 到 status 字段
        snapshot.status = snapshot.hdfs_status
        # 迁移 bkbase_hdfs_processing_id 到 bkbase_processing_id
        snapshot.bkbase_processing_id = snapshot.bkbase_hdfs_processing_id
        # 迁移 bkbase_hdfs_table_id 到 bkbase_table_id
        snapshot.bkbase_table_id = snapshot.bkbase_hdfs_table_id

        snapshot.save()


def migrate_storage_type(apps, schema_editor):
    Snapshot = apps.get_model('databus', 'Snapshot')
    SnapshotStorage = apps.get_model('databus', 'SnapshotStorage')

    # 迁移 storage_type 到 SnapshotStorage
    snapshots_to_migrate = Snapshot.objects.filter(storage_type__isnull=False)

    for snapshot in snapshots_to_migrate:
        # 创建 SnapshotStorage 记录
        if snapshot.storage_type in ['hdfs', 'redis', 'doris']:  # 验证存储类型是否有效
            SnapshotStorage.objects.create(
                snapshot=snapshot,
                storage_type=snapshot.storage_type,
            )
        else:
            # 处理无效的存储类型，如果需要
            pass


class Migration(migrations.Migration):
    dependencies = [
        ('databus', '0014_snapshot_status_msg'),
    ]

    operations = [
        # 创建 SnapshotStorage 模型
        migrations.CreateModel(
            name='SnapshotStorage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'storage_type',
                    models.CharField(
                        choices=[('hdfs', 'HDFS'), ('redis', 'Redis'), ('doris', 'Doris')],
                        db_index=True,
                        max_length=32,
                        verbose_name='存储类型',
                    ),
                ),
                (
                    'snapshot',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='storages',
                        to='databus.snapshot',
                        verbose_name='快照',
                    ),
                ),
            ],
            options={
                'verbose_name': '快照存储关联',
                'verbose_name_plural': '快照存储关联',
                'unique_together': {('snapshot', 'storage_type')},
            },
        ),
        # 先迁移 hdfs_xx 字段的数据
        migrations.RunPython(migrate_hdfs_fields),
        # 迁移 storage_type 数据到 SnapshotStorage
        migrations.RunPython(migrate_storage_type),
        # 删除 storage_type 字段
        migrations.RemoveField(
            model_name='snapshot',
            name='storage_type',
        ),
        # 删除与 HDFS 相关的字段
        migrations.RemoveField(
            model_name='snapshot',
            name='bkbase_hdfs_processing_id',
        ),
        migrations.RemoveField(
            model_name='snapshot',
            name='bkbase_hdfs_table_id',
        ),
        migrations.RemoveField(
            model_name='snapshot',
            name='hdfs_status',
        ),
        # 添加新的字段 join_data_type
        migrations.AddField(
            model_name='snapshot',
            name='join_data_type',
            field=models.CharField(
                choices=[('basic', '通用关联数据'), ('asset', '资产')], default='asset', max_length=32, verbose_name='关联数据类型'
            ),
        ),
    ]
