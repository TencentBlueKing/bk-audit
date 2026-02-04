from bk_resource import BkApiResource
from django.conf import settings


class CommonBkApiResource(BkApiResource):
    def build_header(self, validated_request_data):
        headers = super().build_header(validated_request_data)
        # 多租户头
        if getattr(settings, "ENABLE_MULTI_TENANT_MODE", False):
            headers["X-Bk-Tenant-Id"] = settings.BK_TENANT_ID
        return headers
