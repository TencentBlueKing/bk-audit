"""用脱敏合成响应验证实际网关错误分类，不访问真实接口。"""
from unittest import mock

from bk_resource.exceptions import APIRequestError
from django.test import SimpleTestCase

from api.bk_base_v4.default import CleanGet, DataSourceGet, DataStorageGet, FlowGet
from services.web.bkbase.common import get_resource_or_none


class ResourceErrorTests(SimpleTestCase):
    def response(self, payload):
        response = mock.Mock()
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.json.return_value = payload
        response.request.url = "https://gateway.test/resource"
        return response

    def test_gateway_not_found_allows_first_create(self):
        for cls in (CleanGet, DataSourceGet, DataStorageGet, FlowGet):
            with self.subTest(resource=cls.__name__):
                resource = cls()
                resource.build_header = mock.Mock(return_value={})
                resource.session.get = mock.Mock(
                    return_value=self.response(
                        {"result": False, "code": "1558025", "data": "Resource not found.", "message": "资源不存在."}
                    )
                )
                self.assertIsNone(
                    get_resource_or_none(resource.request, tenant="tenant_a", namespace="audit", name="missing")
                )

    def test_other_business_errors_never_trigger_create(self):
        for code in ("1500203", "1532502", "1500102"):
            with self.subTest(code=code):
                resource = FlowGet()
                resource.build_header = mock.Mock(return_value={})
                resource.session.get = mock.Mock(
                    return_value=self.response(
                        {"result": False, "code": code, "data": "unrelated error", "message": "failed"}
                    )
                )
                with self.assertRaises(APIRequestError):
                    get_resource_or_none(resource.request, tenant="tenant_a", namespace="audit", name="missing")
