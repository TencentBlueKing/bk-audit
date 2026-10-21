# -*- coding: utf-8 -*-
"""audit-meta MCP 工具集测试：路由契约、服务口径、安全裁剪与用户态集成。"""

from unittest import mock

from bk_resource import resource
from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.meta.constants import SystemAuditStatusEnum
from apps.meta.mcp_tools.errors import SystemNotAccessible
from apps.meta.mcp_tools.schemas import (
    ExploreSystemFieldsRequest,
    GetAuditSystemDetailRequest,
    ListAuditSystemsRequest,
    ListSystemActionsRequest,
    ListSystemResourceTypesRequest,
)
from apps.meta.mcp_tools.services import MetaToolService
from apps.meta.models import Action, ResourceType, ResourceTypeActionRelation, System
from apps.meta.views.mcp_views import MCPMetaAutoSchema, MCPUserMetaViewSet
from core.exceptions import PermissionException
from tests.base import TestCase

SERVICE_MODULE = "apps.meta.mcp_tools.services"
RESOURCES_MODULE = "apps.meta.resources"
LOG_FIELD_METADATA_SERVICE = "services.web.query.ai_assistant.log_tools.field_metadata.LogFieldMetadataService"

NAMESPACE = "default"
USERNAME = "meta-user"

META_PATHS = {
    "systems": "/api/v1/meta/namespaces/default/mcp_user/meta/systems/",
    "system_detail": "/api/v1/meta/namespaces/default/mcp_user/meta/system_detail/",
    "actions": "/api/v1/meta/namespaces/default/mcp_user/meta/actions/",
    "resource_types": "/api/v1/meta/namespaces/default/mcp_user/meta/resource_types/",
    "fields": "/api/v1/meta/namespaces/default/mcp_user/meta/fields/",
}

META_OPERATION_IDS = {
    "systems": "mcp_list_audit_systems",
    "system_detail": "mcp_get_audit_system_detail",
    "actions": "mcp_list_system_actions",
    "resource_types": "mcp_list_system_resource_types",
    "fields": "mcp_explore_system_fields",
}

# 系统详情允许暴露的字段白名单；任何新增字段都应在此显式评审。
SYSTEM_DETAIL_SAFE_FIELDS = {
    "system_id",
    "name",
    "name_en",
    "description",
    "audit_status",
    "source_type",
    "system_url",
    "action_count",
    "resource_type_count",
}

SYSTEM_DETAIL_FORBIDDEN_FIELDS = {
    "auth_token",
    "clients",
    "provider_config",
    "callback_url",
    "managers",
    "instance_id",
    "namespace",
    "permission_type",
}


def make_system(system_id: str, *, namespace: str = NAMESPACE, audit_status: str = None, **kwargs) -> System:
    return System.objects.create(
        system_id=system_id,
        instance_id=system_id,
        source_type="iam_v3",
        namespace=namespace,
        audit_status=audit_status or SystemAuditStatusEnum.ACCESSED.value,
        **kwargs,
    )


def permission_denied(*args, **kwargs):
    raise PermissionException(action_name="view_system", permission={})


class TestMCPMetaRouting(SimpleTestCase):
    def test_all_meta_endpoints_resolve_to_user_viewset(self):
        for endpoint, path in META_PATHS.items():
            with self.subTest(endpoint=endpoint):
                match = resolve(path)
                self.assertIs(match.func.cls, MCPUserMetaViewSet)
                self.assertEqual(match.kwargs, {"namespace": NAMESPACE})

    def test_all_routes_are_post_with_body_namespace_guard(self):
        from apps.meta.views.mcp_views import reject_body_namespace

        for route in MCPUserMetaViewSet.resource_routes:
            with self.subTest(endpoint=route.endpoint):
                self.assertEqual(route.method, "POST")
                self.assertIn(reject_body_namespace, route.decorators)

    def test_meta_resources_registered_with_stable_names(self):
        resource_classes = [route.resource_class.__name__ for route in MCPUserMetaViewSet.resource_routes]
        self.assertEqual(
            resource_classes,
            [
                "MCPListAuditSystems",
                "MCPGetAuditSystemDetail",
                "MCPListSystemActions",
                "MCPListSystemResourceTypes",
                "MCPExploreSystemFields",
            ],
        )
        # resource.meta.* 命名空间可通过注册名访问（definition.yaml resource_names 同名）
        self.assertIsNotNone(resource.meta.mcp_list_audit_systems)
        self.assertIsNotNone(resource.meta.mcp_get_audit_system_detail)
        self.assertIsNotNone(resource.meta.mcp_list_system_actions)
        self.assertIsNotNone(resource.meta.mcp_list_system_resource_types)
        self.assertIsNotNone(resource.meta.mcp_explore_system_fields)


class TestMCPMetaSchemaContract(SimpleTestCase):
    def test_operation_ids_are_pinned(self):
        self.assertEqual(MCPMetaAutoSchema._OPERATION_IDS, META_OPERATION_IDS)

    def test_pydantic_models_cover_all_endpoints(self):
        models = MCPMetaAutoSchema._PYDANTIC_MODELS
        self.assertEqual(set(models), set(META_OPERATION_IDS))
        self.assertEqual(models["systems"][0], ListAuditSystemsRequest)
        self.assertEqual(models["system_detail"][0], GetAuditSystemDetailRequest)
        self.assertEqual(models["actions"][0], ListSystemActionsRequest)
        self.assertEqual(models["resource_types"][0], ListSystemResourceTypesRequest)
        # fields 的请求契约是简化的 system_id 入口，而非日志工具的 condition 入口
        self.assertEqual(models["fields"][0], ExploreSystemFieldsRequest)
        # 响应契约与 mcp_get_log_field_metadata 同源复用
        self.assertEqual(models["fields"][1].__name__, "GetLogFieldMetadataResponse")

    def test_error_code_description_covers_meta_domain_codes(self):
        description = MCPMetaAutoSchema._ERROR_CODE_DESCRIPTION
        self.assertIn("2927001", description)
        self.assertIn("2927002", description)


class TestMetaListSystems(TestCase):
    def setUp(self):
        super().setUp()
        make_system("bk_job", name="作业平台", description="快速执行作业任务")
        make_system("bk_cmdb", name="配置平台", description="主机与业务配置")
        # 不应出现的系统：未接入 / 其他命名空间 / 未授权
        make_system("bk_pending", name="待接入系统", audit_status=SystemAuditStatusEnum.PENDING.value)
        make_system("bk_other_ns", name="其他命名空间", namespace="other")
        # 线上实证回归：description 为空的系统（2026-10-20 bkop 500 复现），必须能正常返回
        make_system("bk_blank", name="无描述系统")

    def _list(self, authorized, **params):
        with mock.patch(
            f"{SERVICE_MODULE}.SearchLogPermission.get_auth_systems_by_username",
            return_value=([], authorized),
        ):
            return MetaToolService.list_systems(
                username=USERNAME,
                namespace=NAMESPACE,
                request=ListAuditSystemsRequest(**params),
            )

    def test_only_authorized_accessed_systems_in_namespace_are_listed(self):
        output = self._list(["bk_job", "bk_cmdb", "bk_blank", "bk_pending", "bk_other_ns", "bk_unknown"])

        listed = {item.system_id for item in output.systems}
        self.assertEqual(listed, {"bk_job", "bk_cmdb", "bk_blank"})
        self.assertEqual(output.total, 3)
        self.assertTrue(all(item.audit_status == "accessed" for item in output.systems))
        # 空 description 兜底为空串（2026-10-20 bkop 线上 500 回归）
        blank = next(item for item in output.systems if item.system_id == "bk_blank")
        self.assertEqual(blank.description, "")

    def test_blank_description_system_passes_response_serializer(self):
        """线上实证：description 为空的系统过 bk_resource 响应校验（曾报 500 该字段不能为空）。"""
        from apps.meta.mcp_tools.serializers import ListAuditSystemsResponseSerializer

        output = self._list(["bk_blank"])
        serializer = ListAuditSystemsResponseSerializer(data=output.model_dump(mode="json"))
        self.assertTrue(
            serializer.is_valid(),
            f"空 description 系统未通过响应序列化: {serializer.errors}",
        )

    def test_keyword_matches_id_name_and_description(self):
        for keyword, expected in (("job", {"bk_job"}), ("配置", {"bk_cmdb"}), ("作业任务", {"bk_job"})):
            with self.subTest(keyword=keyword):
                output = self._list(["bk_job", "bk_cmdb"], keyword=keyword)
                self.assertEqual({item.system_id for item in output.systems}, expected)

    def test_pagination_slices_and_reports_has_more(self):
        output = self._list(["bk_job", "bk_cmdb"], page=1, page_size=1)
        self.assertEqual(output.total, 2)
        self.assertEqual(len(output.systems), 1)
        self.assertTrue(output.has_more)

        output = self._list(["bk_job", "bk_cmdb"], page=2, page_size=1)
        self.assertEqual(len(output.systems), 1)
        self.assertFalse(output.has_more)

    def test_no_permission_returns_empty_list_without_exception(self):
        output = self._list([])
        self.assertEqual(output.systems, [])
        self.assertEqual(output.total, 0)
        self.assertFalse(output.has_more)


class TestMetaSystemDetail(TestCase):
    def setUp(self):
        super().setUp()
        self.system = make_system(
            "bk_job",
            name="作业平台",
            name_en="Job",
            description="快速执行作业",
            system_url="https://job.example.com",
            auth_token="secret-token",
            clients=["app_code"],
            provider_config={"host": "https://internal.example.com"},
            callback_url="https://job.example.com/callback",
            managers=["admin"],
        )
        Action.objects.create(system_id="bk_job", action_id="execute_script", name="执行脚本")
        Action.objects.create(system_id="bk_job", action_id="view_job", name="查看作业")
        ResourceType.objects.create(system_id="bk_job", resource_type_id="script", name="脚本")

    def _detail(self, system_id: str = "bk_job"):
        with mock.patch(f"{SERVICE_MODULE}.SearchLogPermission.has_system_search_permission", return_value=True):
            return MetaToolService.get_system_detail(
                username=USERNAME,
                namespace=NAMESPACE,
                request=GetAuditSystemDetailRequest(system_id=system_id),
            )

    def test_detail_exposes_whitelisted_fields_only(self):
        detail = self._detail().system.model_dump(mode="json")

        self.assertEqual(set(detail), SYSTEM_DETAIL_SAFE_FIELDS)
        self.assertEqual(detail["system_id"], "bk_job")
        self.assertEqual(detail["name"], "作业平台")
        self.assertEqual(detail["action_count"], 2)
        self.assertEqual(detail["resource_type_count"], 1)
        for forbidden in SYSTEM_DETAIL_FORBIDDEN_FIELDS:
            self.assertNotIn(forbidden, detail)

    def test_missing_system_raises_domain_error(self):
        with self.assertRaises(SystemNotAccessible):
            self._detail(system_id="bk_missing")

    def test_system_in_other_namespace_raises_domain_error(self):
        make_system("bk_other_ns", namespace="other")
        with self.assertRaises(SystemNotAccessible):
            self._detail(system_id="bk_other_ns")

    def test_user_without_permission_is_rejected_before_namespace_check(self):
        with (
            mock.patch(f"{SERVICE_MODULE}.SearchLogPermission.has_system_search_permission", return_value=False),
            mock.patch(
                f"{SERVICE_MODULE}.SearchLogPermission.raise_system_view_permission_exception", permission_denied
            ),
        ):
            with self.assertRaises(PermissionException):
                MetaToolService.get_system_detail(
                    username=USERNAME,
                    namespace=NAMESPACE,
                    request=GetAuditSystemDetailRequest(system_id="bk_job"),
                )


class TestMetaListActions(TestCase):
    def setUp(self):
        super().setUp()
        make_system("bk_job")
        make_system("bk_cmdb")
        Action.objects.create(system_id="bk_job", action_id="execute_script", name="执行脚本", name_en="Execute")
        Action.objects.create(system_id="bk_job", action_id="view_job", name="查看作业")
        Action.objects.create(system_id="bk_job", action_id="delete_job", name="删除作业")
        # 线上实证回归：type 存在 null 与空串两种形态（模型 blank+null 双开）
        Action.objects.create(system_id="bk_job", action_id="blank_type", name="空类型操作", type="")
        ResourceTypeActionRelation.objects.create(
            system_id="bk_job", action_id="execute_script", resource_type_id="script"
        )

    def _list(self, system_id: str = "bk_job", **params):
        with mock.patch(f"{SERVICE_MODULE}.SearchLogPermission.has_system_search_permission", return_value=True):
            return MetaToolService.list_actions(
                username=USERNAME,
                namespace=NAMESPACE,
                request=ListSystemActionsRequest(system_id=system_id, **params),
            )

    def test_actions_listed_with_resource_type_relations(self):
        output = self._list()
        by_id = {item.action_id: item for item in output.actions}

        self.assertEqual(set(by_id), {"execute_script", "view_job", "delete_job", "blank_type"})
        self.assertEqual(by_id["execute_script"].resource_type_ids, ["script"])
        self.assertEqual(by_id["view_job"].resource_type_ids, [])
        # 空串 type 归一为 None（2026-10-20 bkop 线上 500 回归：空串曾触发该字段不能为空）
        self.assertIsNone(by_id["blank_type"].type)
        self.assertEqual(output.total, 4)
        self.assertFalse(output.has_more)

    def test_blank_type_action_passes_response_serializer(self):
        """线上实证：type 为空串的操作归一 None 后过 bk_resource 响应校验。"""
        from apps.meta.mcp_tools.serializers import ListSystemActionsResponseSerializer

        output = self._list(page_size=100)
        serializer = ListSystemActionsResponseSerializer(data=output.model_dump(mode="json"))
        self.assertTrue(
            serializer.is_valid(),
            f"空 type 操作未通过响应序列化: {serializer.errors}",
        )

    def test_keyword_matches_action_id_and_name(self):
        output = self._list(keyword="execute")
        self.assertEqual({item.action_id for item in output.actions}, {"execute_script"})
        output = self._list(keyword="删除")
        self.assertEqual({item.action_id for item in output.actions}, {"delete_job"})

    def test_keyword_matches_action_type(self):
        """类型化表述经操作类型字段命中："管理工具"是操作的 type 值而非动作名称。"""
        Action.objects.create(system_id="bk_cmdb", action_id="manage_panel", name="管理面板", type="管理工具")
        output = self._list(system_id="bk_cmdb", keyword="管理工具")
        self.assertEqual({item.action_id for item in output.actions}, {"manage_panel"})

    def test_resource_type_filter_keeps_only_related_actions(self):
        output = self._list(resource_type_id="script")
        self.assertEqual({item.action_id for item in output.actions}, {"execute_script"})

    def test_pagination_reports_has_more(self):
        output = self._list(page=1, page_size=2)
        self.assertEqual(len(output.actions), 2)
        self.assertTrue(output.has_more)
        output = self._list(page=2, page_size=2)
        self.assertEqual(len(output.actions), 2)
        self.assertFalse(output.has_more)

    def test_missing_system_raises_domain_error(self):
        with self.assertRaises(SystemNotAccessible):
            self._list(system_id="bk_missing")

    def test_user_without_permission_is_rejected(self):
        with (
            mock.patch(f"{SERVICE_MODULE}.SearchLogPermission.has_system_search_permission", return_value=False),
            mock.patch(
                f"{SERVICE_MODULE}.SearchLogPermission.raise_system_view_permission_exception", permission_denied
            ),
        ):
            with self.assertRaises(PermissionException):
                MetaToolService.list_actions(
                    username=USERNAME,
                    namespace=NAMESPACE,
                    request=ListSystemActionsRequest(system_id="bk_job"),
                )


class TestMetaListResourceTypes(TestCase):
    def setUp(self):
        super().setUp()
        make_system("bk_job")
        # 树同步要求父类型先存在，创建顺序不可颠倒
        ResourceType.objects.create(system_id="bk_job", resource_type_id="biz", name="业务")
        ResourceType.objects.create(system_id="bk_job", resource_type_id="script", name="脚本", ancestor=["biz"])
        ResourceType.objects.create(system_id="bk_cmdb", resource_type_id="host", name="主机")

    def _list(self, system_id: str = "bk_job", **params):
        with mock.patch(f"{SERVICE_MODULE}.SearchLogPermission.has_system_search_permission", return_value=True):
            return MetaToolService.list_resource_types(
                username=USERNAME,
                namespace=NAMESPACE,
                request=ListSystemResourceTypesRequest(system_id=system_id, **params),
            )

    def test_resource_types_listed_with_ancestor(self):
        output = self._list()
        by_id = {item.resource_type_id: item for item in output.resource_types}

        self.assertEqual(set(by_id), {"script", "biz"})
        self.assertEqual(by_id["script"].ancestor, ["biz"])
        self.assertEqual(by_id["biz"].ancestor, [])
        self.assertEqual(output.total, 2)

    def test_keyword_matches_id_and_name(self):
        output = self._list(keyword="主机")
        self.assertEqual(output.resource_types, [])
        output = self._list(keyword="script")
        self.assertEqual({item.resource_type_id for item in output.resource_types}, {"script"})

    def test_missing_system_raises_domain_error(self):
        with self.assertRaises(SystemNotAccessible):
            self._list(system_id="bk_missing")


class TestMetaExploreSystemFields(SimpleTestCase):
    """字段探索：复用日志工具的字段目录服务，权限与脱敏由其内部链路承担。"""

    def test_explore_reuses_log_field_metadata_service_with_system_scope(self):
        sentinel = object()
        with mock.patch(f"{LOG_FIELD_METADATA_SERVICE}.get_metadata", return_value=sentinel) as get_metadata:
            result = MetaToolService.explore_system_fields(
                username=USERNAME,
                namespace=NAMESPACE,
                system_id="bk_job",
            )

        self.assertIs(result, sentinel)
        get_metadata.assert_called_once()
        _, kwargs = get_metadata.call_args
        self.assertEqual(kwargs["username"], USERNAME)
        self.assertEqual(kwargs["namespace"], NAMESPACE)
        request = kwargs["request"]
        self.assertEqual(request.condition.scope_type, "system")
        self.assertEqual(request.condition.scope_id, "bk_job")
        self.assertEqual(request.condition.conditions, [])


class MCPMetaUser:
    username = USERNAME
    is_authenticated = True


class TestMCPUserMetaViewSetIntegration(TestCase):
    """用户态 APIGW 集成：认证、协议校验与资源执行端到端。"""

    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.system = make_system("bk_job", name="作业平台", description="执行作业任务")

    def _post(self, endpoint: str, body, *, namespace: str = NAMESPACE):
        view = MCPUserMetaViewSet.as_view({"post": endpoint})
        request = self.factory.post(META_PATHS[endpoint], body, format="json")
        force_authenticate(request, user=MCPMetaUser())
        with (
            mock.patch("core.permissions.get_app_info"),
            mock.patch(f"{RESOURCES_MODULE}.get_request_username", return_value=USERNAME),
        ):
            return view(request, namespace=namespace)

    def test_list_systems_returns_paginated_data(self):
        with mock.patch(
            f"{SERVICE_MODULE}.SearchLogPermission.get_auth_systems_by_username",
            return_value=([], ["bk_job"]),
        ):
            response = self._post("systems", {"keyword": "作业", "page": 1, "page_size": 10})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["systems"][0]["system_id"], "bk_job")
        self.assertTrue(response.data["has_more"] is False)

    def test_body_namespace_is_rejected(self):
        response = self._post("systems", {"namespace": NAMESPACE})
        self.assertEqual(response.status_code, 400)
        self.assertIn("namespace", response.data)

    def test_non_object_body_is_rejected(self):
        view = MCPUserMetaViewSet.as_view({"post": "systems"})
        request = self.factory.post(META_PATHS["systems"], ["not", "an", "object"], format="json")
        force_authenticate(request, user=MCPMetaUser())
        with (
            mock.patch("core.permissions.get_app_info"),
            mock.patch(f"{RESOURCES_MODULE}.get_request_username", return_value=USERNAME),
        ):
            response = view(request, namespace=NAMESPACE)
        self.assertEqual(response.status_code, 400)

    def test_unknown_request_field_is_rejected(self):
        response = self._post("systems", {"foo": "bar"})
        self.assertEqual(response.status_code, 400)

    def test_explore_fields_passes_system_id_through_request_contract(self):
        from services.web.query.ai_assistant.log_tools.schemas import (
            GetLogFieldMetadataResponse,
        )

        field_metadata = GetLogFieldMetadataResponse.model_validate(
            {
                "fields": [
                    {
                        "field": {"raw_name": "system_id", "keys": []},
                        "category": "BASIC",
                        "display_name": "系统ID",
                        "description": "业务系统标识",
                        "type_source": "DECLARED",
                        "observed_types": ["string"],
                        "allow_operators": ["eq"],
                        "options": None,
                        "is_expandable": False,
                        "statistics_supported": True,
                        "statistics_kind": "CATEGORICAL",
                        "unsupported_reason": None,
                        "allowed_metrics": ["COUNT"],
                        "sample_values": [],
                        "sampled_non_null_count": 0,
                        "coverage": 0.0,
                    }
                ],
                "sample_summary": {
                    "sampling_performed": False,
                    "sampled_count": 0,
                    "returned_field_count": 1,
                    "truncated": False,
                },
            }
        )
        with mock.patch(f"{LOG_FIELD_METADATA_SERVICE}.get_metadata", return_value=field_metadata):
            response = self._post("fields", {"system_id": "bk_job"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["fields"][0]["field"]["raw_name"], "system_id")
        self.assertFalse(response.data["sample_summary"]["sampling_performed"])
