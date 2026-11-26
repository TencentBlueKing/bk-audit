"""严格新装的 ITSM V4 默认套餐；不处理历史迁移或远端流程发布。"""
from uuid import UUID

from django.db import transaction

from apps.itsm.utils import is_itsm_v4_enabled
from core.kms import get_secret_json
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.risk.models import ProcessApplication
from services.web.scene.constants import (
    DEFAULT_SCENE_NAME,
    BindingType,
    ResourceVisibilityType,
    SceneStatus,
)
from services.web.scene.filters import BindingMetadataHelper
from services.web.scene.models import ResourceBinding, Scene

ENV_KEY = "BKAPP_INIT_ITSM_APPROVAL_CONFIG"


def invalid(field):
    """错误只给字段位置，不输出配置值。"""
    return BKBaseResourceMappingError(message=f"Invalid {ENV_KEY}: field={field}")


def validate_itsm_approval():
    """纯配置检查；关闭 ITSM V4 时既不读取也不处理新输入。"""
    if not is_itsm_v4_enabled():
        return None
    config = get_secret_json(ENV_KEY, {})
    if not isinstance(config, dict) or set(config) != {"default_package"}:
        raise invalid("default_package")
    package = config["default_package"]
    if not isinstance(package, dict) or set(package) != {"uuid", "name", "sops_template_id", "workflow_key"}:
        raise invalid("default_package.fields")
    for key in ("uuid", "name", "workflow_key"):
        value = package[key]
        if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > 64:
            raise invalid(f"default_package.{key}")
    try:
        uuid = UUID(package["uuid"]).hex
    except ValueError:
        raise invalid("default_package.uuid") from None
    if type(package["sops_template_id"]) is not int or package["sops_template_id"] <= 0:
        raise invalid("default_package.sops_template_id")
    return {**package, "uuid": uuid}


@transaction.atomic
def init_itsm_approval(package):
    """只补新套餐及其场景关联；已有 UUID 的配置和归属必须一致。"""
    if package is None:
        return
    if (
        not Scene.objects.select_for_update()
        .filter(scene_id=1, name=DEFAULT_SCENE_NAME, status=SceneStatus.ENABLED)
        .exists()
    ):
        raise invalid("scene_id=1 must be enabled system_default")
    existing = ProcessApplication._objects.select_for_update().filter(uniq_id=package["uuid"]).first()
    expected = {
        "name": package["name"],
        "sops_template_id": package["sops_template_id"],
        "approve_service_id": package["workflow_key"],
    }
    if existing is not None:
        if (
            existing.is_deleted
            or not existing.is_enabled
            or not existing.need_approve
            or any(getattr(existing, key) != value for key, value in expected.items())
        ):
            raise invalid("default_package conflicts with registered UUID")
        binding = ResourceBinding.objects.filter(
            resource_id=str(existing.id), resource_type=ResourceVisibilityType.PROCESS_APPLICATION
        ).first()
        if (
            not binding
            or binding.binding_type != BindingType.SCENE_BINDING
            or list(binding.binding_scenes.values_list("scene_id", flat=True)) != [1]
        ):
            raise invalid("default_package scene binding")
        return
    if ProcessApplication.objects.filter(name=package["name"]).exists():
        raise invalid("default_package name belongs to another UUID")
    created = ProcessApplication.objects.create(
        uniq_id=package["uuid"], approve_config={}, need_approve=True, **expected
    )
    BindingMetadataHelper.create_resource_binding(created.id, ResourceVisibilityType.PROCESS_APPLICATION, 1)
