"""Resolve the BKBase V4 scope from the trusted deployment configuration."""
from bk_resource.settings import bk_resource_settings
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from core.tenant import get_admin_username, get_bk_tenant_id, use_multi_tenant_mode


def get_bkbase_v4_tenant() -> str:
    """Keep the configured V4 scope in single-tenant mode and bind it to the instance otherwise."""
    tenant = getattr(settings, "BKBASE_V4_TENANT", "")
    if not use_multi_tenant_mode():
        return tenant
    instance_tenant = get_bk_tenant_id()
    if not instance_tenant or tenant != instance_tenant:
        raise ImproperlyConfigured("BKBase V4 tenant must match the bound Audit instance tenant")
    return instance_tenant


def get_bkbase_v4_platform_username() -> str:
    """Use the same platform actor for resource ownership and outbound authentication."""
    if use_multi_tenant_mode():
        return get_admin_username(get_bkbase_v4_tenant())
    return bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME
