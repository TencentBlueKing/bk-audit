# -*- coding: utf-8 -*-
"""
创建系统默认场景，并将存量资源补充关联到该场景。

目标：
1. 新建（或复用）名为 system_default 的场景。
2. 为线上已存在的存量资源补齐 ResourceBinding。
3. 对没有任何场景关联的绑定，补充关联到 system_default。

说明：
- 迁移幂等，可重复执行。
- 仅处理“无场景关联”的存量数据，避免覆盖已有场景归属。
"""

from django.db import migrations

DEFAULT_SCENE_NAME = "system_default"
DEFAULT_SCENE_DESCRIPTION = "系统默认场景（存量资源迁移生成）"

# (resource_type, app_label, model_name, resource_id_field, filter_kwargs)
RESOURCE_CONFIGS = [
    ("panel", "vision", "VisionPanel", "id", {"is_deleted": False}),
    ("tool", "tool", "Tool", "uid", {"is_deleted": False}),
    ("strategy", "strategy_v2", "Strategy", "strategy_id", {"is_deleted": False}),
    ("link_table", "strategy_v2", "LinkTable", "uid", {}),
    ("process_application", "risk", "ProcessApplication", "id", {"is_deleted": False}),
    ("risk_rule", "risk", "RiskRule", "rule_id", {"is_deleted": False}),
    ("notice_group", "notice", "NoticeGroup", "group_id", {"is_deleted": False}),
]
# NOTE:
# - 风险（risk）暂不在本迁移中单独补 Binding。当前风险场景通过策略绑定间接映射，
#   批量为风险逐条建 Binding 会引入不必要的大规模写入。


def _safe_filter(queryset, filter_kwargs):
    """仅在字段存在时应用过滤条件。"""
    model_field_names = {field.name for field in queryset.model._meta.fields}
    valid_kwargs = {k: v for k, v in filter_kwargs.items() if k in model_field_names}
    return queryset.filter(**valid_kwargs)


def _collect_resource_ids(model, resource_id_field, filter_kwargs):
    """收集资源表中的存量资源 ID（统一转为字符串）。"""
    queryset = model._base_manager.all()
    queryset = _safe_filter(queryset, filter_kwargs)

    values = queryset.values_list(resource_id_field, flat=True)
    resource_ids = set()
    for value in values.iterator():
        if value is None:
            continue
        value_str = str(value).strip()
        if not value_str:
            continue
        resource_ids.add(value_str)
    return resource_ids


def _ensure_default_scene(SceneModel):
    """创建或复用 system_default 场景。"""
    scene = SceneModel._base_manager.filter(name=DEFAULT_SCENE_NAME).order_by("scene_id").first()
    if scene:
        # 安全防护：
        # 不复用用户可控的同名场景，避免把历史资源错误绑定到用户场景导致权限扩大。
        if scene.description != DEFAULT_SCENE_DESCRIPTION or list(scene.managers or []) or list(scene.users or []):
            raise RuntimeError(
                "Reserved scene name conflict: existing 'system_default' scene is user-managed. "
                "Please rename it before running migration."
            )
        if scene.status != "enabled":
            scene.status = "enabled"
            scene.save(update_fields=["status"])
        return scene

    return SceneModel._base_manager.create(
        name=DEFAULT_SCENE_NAME,
        description=DEFAULT_SCENE_DESCRIPTION,
        status="enabled",
        managers=[],
        users=[],
    )


def _backfill_resource_bindings(apps):
    Scene = apps.get_model("scene", "Scene")
    ResourceBinding = apps.get_model("scene", "ResourceBinding")
    ResourceBindingScene = apps.get_model("scene", "ResourceBindingScene")

    default_scene = _ensure_default_scene(Scene)

    for resource_type, app_label, model_name, resource_id_field, filter_kwargs in RESOURCE_CONFIGS:
        model = apps.get_model(app_label, model_name)
        resource_ids = _collect_resource_ids(model, resource_id_field, filter_kwargs)

        if not resource_ids:
            continue

        existing_bindings = ResourceBinding._base_manager.filter(
            resource_type=resource_type,
            resource_id__in=resource_ids,
        ).only("id", "resource_id")
        existing_resource_ids = {binding.resource_id for binding in existing_bindings}

        missing_resource_ids = resource_ids - existing_resource_ids
        if missing_resource_ids:
            ResourceBinding._base_manager.bulk_create(
                [
                    ResourceBinding(
                        resource_type=resource_type,
                        resource_id=resource_id,
                        binding_type="scene_binding",
                        visibility_type="specific_scenes",
                    )
                    for resource_id in missing_resource_ids
                ],
                batch_size=500,
            )

        bindings_without_scene = (
            ResourceBinding._base_manager.filter(
                resource_type=resource_type,
                resource_id__in=resource_ids,
                binding_scenes__isnull=True,
            )
            .only("id")
            .distinct()
        )

        ResourceBindingScene._base_manager.bulk_create(
            [
                ResourceBindingScene(
                    binding_id=binding.id,
                    scene_id=default_scene.scene_id,
                )
                for binding in bindings_without_scene
            ],
            batch_size=500,
            ignore_conflicts=True,
        )


def forwards(apps, schema_editor):
    _backfill_resource_bindings(apps)


class Migration(migrations.Migration):

    dependencies = [
        ("scene", "0005_resource_binding_scene_fk"),
        ("tool", "0012_resource_binding_refactor"),
        ("vision", "0010_resource_binding_refactor"),
        ("strategy_v2", "0025_remove_scene_id"),
        ("risk", "0046_remove_scene_id"),
        ("notice", "0009_remove_scene_id"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
