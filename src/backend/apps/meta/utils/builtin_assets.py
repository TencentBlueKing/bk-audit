"""审计内置资产的本地身份与共享回调路由，不影响 IAM 注册和鉴权身份。"""

from django.conf import settings

from apps.permission.handlers.resource_types import ResourceEnum
from core.tenant import TENANT_ID_HEADER, get_bk_tenant_id, use_multi_tenant_mode

BUILTIN_ASSET_RESOURCE_TYPES = (
    ResourceEnum.RISK,
    ResourceEnum.STRATEGY,
    ResourceEnum.STRATEGY_TAG,
    ResourceEnum.TICKET_PERMISSION,
    ResourceEnum.TICKET_NODE,
    ResourceEnum.MANUAL_EVENT,
)


def get_builtin_asset_system_id() -> str:
    """显式配置只定位本地资产；未配置或空值保持原 IAM 系统 ID。"""
    return (getattr(settings, "BUILTIN_ASSET_SYSTEM_ID", "") or "").strip() or settings.BK_IAM_SYSTEM_ID


def builtin_asset_callback_headers(system_id: str, resource_type_id: str) -> dict:
    """仅向审计自身六类内置资产的共享回调传当前实例租户。"""
    if (
        use_multi_tenant_mode()
        and system_id == get_builtin_asset_system_id()
        and resource_type_id in {resource.id for resource in BUILTIN_ASSET_RESOURCE_TYPES}
    ):
        return {TENANT_ID_HEADER: get_bk_tenant_id()}
    return {}
