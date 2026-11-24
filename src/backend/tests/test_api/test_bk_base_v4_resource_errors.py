"""用脱敏合成响应验证实际网关错误分类，不访问真实接口。"""
from unittest import mock

import requests
from bk_resource.exceptions import APIRequestError
from django.test import SimpleTestCase

from api.bk_base_v4.default import (
    CleanGet,
    DataSourceGet,
    DataSourceList,
    DataStorageGet,
    FlowGet,
    StorageAssetCreate,
    StorageAssetGet,
)
from services.web.bkbase.common import get_resource_or_none


class ResourceErrorTests(SimpleTestCase):
    def response(self, payload):
        response = mock.Mock()
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.json.return_value = payload
        response.request.url = "https://gateway.test/resource"
        return response

    def request_list(self, payload):
        """经过真实request校验链，仅替换HTTP响应和鉴权头构造。"""
        resource = DataSourceList()
        with mock.patch.object(resource, "build_header", return_value={}), mock.patch.object(
            resource.session, "get", return_value=self.response(payload)
        ):
            return resource.request(tenant="tenant_a", namespace="audit")

    def test_successful_empty_list_and_native_payloads_remain_usable(self):
        self.assertEqual(self.request_list({"result": True, "code": "00", "data": []}), [])
        for native in ([], [{"metadata": {"name": "source_a"}}], {"metadata": {}, "spec": {}}):
            with self.subTest(native=native):
                self.assertEqual(self.request_list(native), native)

    def test_malformed_or_contradictory_envelopes_cannot_become_empty_lists(self):
        for payload in (
            {"result": 0, "code": "1500111", "data": []},
            {"result": 1, "code": "00", "data": []},
            {"result": "true", "code": "00", "data": []},
            {"code": "1500111", "data": []},
            {"result": True, "code": "1500111", "data": []},
            {"result": True, "data": []},
            {"result": True, "code": "00"},
            {"result": False, "code": "00", "data": []},
            {"code": "1500111"},
        ):
            with self.subTest(payload=payload), self.assertRaises(APIRequestError):
                self.request_list(payload)

    def test_malformed_not_found_never_allows_resource_creation(self):
        for result in (0, None, "false", True, "absent"):
            for code, data in (("1558025", {}), ("1500102", {"err": "resource not exists"})):
                payload = {"code": code, "data": data}
                if result != "absent":
                    payload["result"] = result
                resource = FlowGet()
                with mock.patch.object(resource, "build_header", return_value={}), mock.patch.object(
                    resource.session, "get", return_value=self.response(payload)
                ), self.subTest(result=result, code=code), self.assertRaises(APIRequestError) as caught:
                    get_resource_or_none(resource.request, tenant="tenant_a", namespace="audit", name="missing")
                self.assertFalse(getattr(caught.exception, "resource_not_found", False))

    def test_incomplete_explicit_failure_is_not_authoritative_not_found(self):
        resource = FlowGet()
        with mock.patch.object(resource, "build_header", return_value={}), mock.patch.object(
            resource.session, "get", return_value=self.response({"result": False, "code": "1558025"})
        ), self.assertRaises(APIRequestError) as caught:
            get_resource_or_none(resource.request, tenant="tenant_a", namespace="audit", name="missing")
        self.assertFalse(getattr(caught.exception, "resource_not_found", False))

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

    def test_non_200_gateway_error_preserves_structured_code_without_parsing_message(self):
        resource = StorageAssetCreate()
        response = self.response({"code": 1640401, "message": "synthetic route rejection"})
        response.status_code = 404
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
        with mock.patch.object(resource, "build_header", return_value={}), mock.patch.object(
            requests.sessions.Session, "request", return_value=response
        ), self.assertRaises(APIRequestError) as caught:
            resource.request(
                tenant="tenant_a",
                project_name="audit",
                asset_name="redis_a",
                asset_alias="Redis A",
                sub_type="Redis",
                belong_type="project_private",
                connection={"kind": "Redis", "config": {"host": "redis.synthetic.test", "port": 6379}},
            )
        self.assertEqual(caught.exception.http_status, 404)
        self.assertEqual(caught.exception.gateway_error_code, "1640401")
        self.assertFalse(getattr(caught.exception, "resource_not_found", False))

    def test_asset_absence_requires_exact_documented_business_failure(self):
        cases = [
            ({"result": False, "code": "1553002", "data": None}, True),
            ({"result": False, "code": "1553002"}, False),
            ({"result": False, "code": "1553002", "data": {}}, False),
            ({"result": True, "code": "1553002", "data": None}, False),
            ({"result": False, "code": "1553001", "data": None}, False),
            ({"result": False, "code": "1553005", "data": None}, False),
            ({"result": False, "code": 1640401, "data": None}, False),
        ]
        for payload, missing in cases:
            resource = StorageAssetGet()
            with self.subTest(payload=payload), mock.patch.object(
                resource, "build_header", return_value={}
            ), mock.patch.object(resource.session, "get", return_value=self.response(payload)), self.assertRaises(
                APIRequestError
            ) as caught:
                resource.request(tenant="tenant_a", project_name="audit", sub_type="Redis", asset_name="redis_a")
            self.assertEqual(getattr(caught.exception, "asset_not_found", False), missing)
