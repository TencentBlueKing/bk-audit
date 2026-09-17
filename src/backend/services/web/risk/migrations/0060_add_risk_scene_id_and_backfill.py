# -*- coding: utf-8 -*-
"""
场景隔离重构：将 Risk 的场景归属改为 Risk.scene_id 字段。

1. 新增 Risk.scene_id 列（若不存在）
2. 分批回填存量 Risk.scene_id=NULL：
   - 使用策略场景绑定 ResourceBinding(STRATEGY) -> scene_id 进行回填。
"""

from django.db import migrations, models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy


def column_exists(schema_editor, table: str, column: str) -> bool:
    """检查列是否存在（使用 information_schema）。"""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
            [table, column],
        )
        return cursor.fetchone()[0] > 0


def index_exists(schema_editor, table: str, index_name: str) -> bool:
    """检查索引是否存在（使用 information_schema）。"""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND INDEX_NAME = %s",
            [table, index_name],
        )
        return cursor.fetchone()[0] > 0


def _expected_field_index_name(schema_editor, table: str, field) -> str:
    """复用 Django 自动命名规则，推导 db_index=True 字段的预期索引名。

    与 schema_editor.add_field() 内部创建索引时使用的命名保持一致，
    避免自行拼名与 Django 后续变更产生分歧。
    """
    return schema_editor._create_index_name(table, [field.column])


class SafeAddField(migrations.AddField):
    """列已存在时跳过（兼容历史版本迁移已部分执行的环境）。"""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.model_name)
        table = model._meta.db_table
        field = model._meta.get_field(self.name)

        if not column_exists(schema_editor, table, field.column):
            super().database_forwards(app_label, schema_editor, from_state, to_state)
            return
        print(f"[SafeAddField] column exists, skip => {table}.{self.name}", flush=True)
        self._ensure_field_index(schema_editor, table, field)

    def _ensure_field_index(self, schema_editor, table: str, field) -> None:
        """列已存在时，补齐 db_index 对应的预期索引（缺失才建，避免重复）。"""
        if not getattr(field, "db_index", False):
            return

        index_name = _expected_field_index_name(schema_editor, table, field)
        if index_exists(schema_editor, table, index_name):
            print(
                f"[SafeAddField] index exists, skip => {table}.{field.column} ({index_name})",
                flush=True,
            )
            return

        print(
            f"[SafeAddField][RECOVER] index missing, create => {table}.{field.column} ({index_name})",
            flush=True,
        )
        # 复用 Django 建索引语句，确保与 AddField 正常路径产出一致
        schema_editor.execute(
            schema_editor._create_index_sql(
                field.model,
                fields=[field],
                name=index_name,
            )
        )


def _build_strategy_scene_map(apps):
    """策略场景绑定 ResourceBinding(STRATEGY) -> scene_id。"""
    ResourceBindingScene = apps.get_model("scene", "ResourceBindingScene")
    result = {}
    for strategy_id, scene_id in ResourceBindingScene.objects.filter(
        scene__is_deleted=False,
        binding__resource_type="strategy",
    ).values_list("binding__resource_id", "scene_id"):
        result.setdefault(str(strategy_id), scene_id)
    return result


def forwards(apps, schema_editor):
    Risk = apps.get_model("risk", "Risk")

    print("[forwards] 开始回填 Risk.scene_id（源自策略绑定）", flush=True)

    strategy_scene_map = _build_strategy_scene_map(apps)

    print(
        f"[forwards] 来源规模：已绑定场景策略={len(strategy_scene_map)}",
        flush=True,
    )

    # keyset 分批：按主键游标推进，避免一次性把整张表物化进内存。
    # 每批最多 2,000 条，每批提交，支持失败重试。
    batch_size = 2000
    last_risk_id = ""
    total_updated, total_skipped, total_no_scene = 0, 0, 0
    failed_batches = []  # 记录失败的批次，用于报告

    while True:
        # 只查询 scene_id IS NULL 的记录（重跑时自动跳过已提交的批次）
        rows = list(
            Risk.objects.filter(
                scene_id__isnull=True,
                strategy_id__isnull=False,
                risk_id__gt=last_risk_id,
            )
            .order_by("risk_id")
            .values_list("risk_id", "strategy_id")[:batch_size]
        )

        if not rows:
            break

        # 构建更新对象
        objs = []
        batch_risk_ids = []
        batch_skipped = 0
        for risk_id, strategy_id in rows:
            scene_id = strategy_scene_map.get(str(strategy_id))
            if scene_id is None:
                # 策略未绑定场景：无法判定归属，保持 scene_id=NULL
                batch_skipped += 1
                continue

            objs.append(Risk(risk_id=risk_id, scene_id=scene_id, updated_at=timezone.now()))
            batch_risk_ids.append(risk_id)

        # 写入并提交当前批次
        if objs:
            try:
                # 写入时再次限制 scene_id IS NULL，不覆盖业务已填写的场景
                Risk.objects.filter(
                    risk_id__in=batch_risk_ids,
                    scene_id__isnull=True,
                ).bulk_update(objs, ["scene_id", "updated_at"], batch_size=batch_size)

                # 显式提交当前批次
                transaction.commit()

                total_updated += len(objs)
                print(
                    f"[forwards] 批次提交成功：本批更新={len(objs)}, "
                    f"累计更新={total_updated}, risk_id 范围=({rows[0][0]}, {rows[-1][0]})",
                    flush=True,
                )
            except Exception as e:
                # 记录失败批次，继续下一批
                failed_batches.append(
                    {
                        "start_risk_id": rows[0][0],
                        "end_risk_id": rows[-1][0],
                        "error": str(e),
                    }
                )
                print(
                    f"[forwards][ERROR] 批次失败：risk_id 范围=({rows[0][0]}, {rows[-1][0]}), " f"错误={e}",
                    flush=True,
                )

        last_risk_id = rows[-1][0]
        total_skipped += batch_skipped
        total_no_scene += batch_skipped

    # 最终报告
    print(
        f"[forwards] 回填完成：更新={total_updated}, 无法判定跳过={total_skipped}",
        flush=True,
    )

    if total_no_scene:
        print(
            f"[forwards][WARN] {total_no_scene} 条风险未能从策略绑定判定场景，保持 scene_id=NULL，"
            "请检查其策略配置或 ResourceBinding(STRATEGY) 是否缺失",
            flush=True,
        )

    # 报告失败批次：如果有失败批次，抛出异常阻止迁移标记为完成
    if failed_batches:
        error_msg = f"[forwards][ERROR] 有 {len(failed_batches)} 个批次失败，迁移中止，请修复后重跑。\n" f"失败批次详情：{failed_batches}"
        print(error_msg, flush=True)
        raise Exception(error_msg)

    # 报告最终仍为 NULL 的记录（包含无法判定 + 失败批次）
    remaining_null_count = Risk.objects.filter(scene_id__isnull=True, strategy_id__isnull=False).count()
    if remaining_null_count:
        print(
            f"[forwards][REPORT] 最终仍有 {remaining_null_count} 条记录 scene_id=NULL，"
            "以下为前 100 条 risk_id: "
            f"{list(Risk.objects.filter(scene_id__isnull=True, strategy_id__isnull=False).values_list('risk_id', flat=True)[:100])}",
            flush=True,
        )


class Migration(migrations.Migration):
    # 禁用整体事务，允许分批提交
    atomic = False

    dependencies = [
        ("risk", "0059_add_multi_rule_fields"),
        ("scene", "0014_scene_permission_application"),
        ("strategy_v2", "0027_migrate_rules_data"),
    ]

    operations = [
        SafeAddField(
            model_name="risk",
            name="scene_id",
            field=models.IntegerField(
                blank=True,
                db_index=True,
                help_text=gettext_lazy("风险归属场景"),
                null=True,
                verbose_name=gettext_lazy("Scene ID"),
            ),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
