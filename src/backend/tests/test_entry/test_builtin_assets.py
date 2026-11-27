"""内置资产本地身份与共享回调路由的兼容回归。"""

from unittest import mock

from django.test import override_settings

from apps.exceptions import ParamsNotValid
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig, ResourceType, System
from apps.meta.resources import ResourceTypeSchema
from apps.permission.handlers.resource_types import ResourceEnum
from services.web.databus.collector.resources import ToggleJoinDataResource
from services.web.databus.collector.snapshot.join.http_pull import HttpPullHandler
from services.web.databus.constants import (
    ASSET_RISK_BKBASE_RT_ID_KEY,
    JoinDataType,
    SnapshotRunningStatus,
)
from services.web.databus.models import Snapshot
from services.web.databus.tasks import sync_asset_bkbase_rt_ids
from services.web.entry.constants import INIT_ASSET_FINISHED_KEY
from services.web.entry.init.base import SystemInitHandler
from tests.base import TestCase

ASSET_IDS = ("risk", "strategy", "strategy_tag", "ticket_permission", "ticket_node", "manual_event")
V4_SYSTEM_ID = "iam_v4_bk-audit"


@override_settings(BKAPP_INIT_SYSTEM="True")
class BuiltinAssetInitTests(TestCase):
    """本地资产 ID 与 IAM 后端、存量资源绑定相互独立。"""

    def _metadata(self, system_id=V4_SYSTEM_ID, resource_ids=ASSET_IDS):
        """准备已同步的本地元数据，不触发 IAM 同步。"""
        system = System.objects.create(
            system_id=system_id,
            instance_id="bk-audit",
            source_type="iam_v4",
            namespace=self.namespace,
            callback_url="https://audit.example.test/api/v1/iam/resources/",
            auth_token="synthetic-asset-token",
        )
        for resource_id in resource_ids:
            ResourceType.objects.create(
                system_id=system_id,
                resource_type_id=resource_id,
                name=resource_id,
                unique_id=f"{system_id}:{resource_id}",
            )
        return system

    @override_settings(BUILTIN_ASSET_SYSTEM_ID="")
    def test_backend_switch_without_asset_id_keeps_legacy_identity_and_markers(self):
        """仅切 IAM 后端不会补建另一套资产或丢失旧状态键。"""
        for backend in ("v3", "v4"):
            with self.subTest(backend=backend), override_settings(IAM_PERMISSION_BACKEND=backend):
                GlobalMetaConfig.set(INIT_ASSET_FINISHED_KEY, {"bk-audit-risk": True})
                with mock.patch("services.web.entry.init.base.resource.databus.collector.toggle_join_data") as toggle:
                    SystemInitHandler().init_asset()
                self.assertEqual({call.args[0]["system_id"] for call in toggle.call_args_list}, {"bk-audit"})
                self.assertEqual(
                    {call.args[0]["resource_type_id"] for call in toggle.call_args_list}, set(ASSET_IDS) - {"risk"}
                )
                self.assertTrue(GlobalMetaConfig.get(INIT_ASSET_FINISHED_KEY)["bk-audit-risk"])

    @override_settings(BUILTIN_ASSET_SYSTEM_ID=V4_SYSTEM_ID, IAM_PERMISSION_BACKEND="v4")
    def test_explicit_v4_fresh_install_uses_local_identity_without_changing_iam_resources(self):
        self._metadata()
        with mock.patch("services.web.entry.init.base.resource.databus.collector.toggle_join_data") as toggle:
            SystemInitHandler().init_asset()
        self.assertEqual(toggle.call_count, 6)
        self.assertEqual({call.args[0]["system_id"] for call in toggle.call_args_list}, {V4_SYSTEM_ID})
        self.assertEqual({call.args[0]["resource_type_id"] for call in toggle.call_args_list}, set(ASSET_IDS))
        self.assertEqual(
            GlobalMetaConfig.get(INIT_ASSET_FINISHED_KEY),
            {f"{V4_SYSTEM_ID}-{asset_id}": True for asset_id in ASSET_IDS},
        )
        self.assertEqual(ResourceEnum.MANUAL_EVENT.create_simple_instance("1").system, "bk-audit")

    @override_settings(BUILTIN_ASSET_SYSTEM_ID=V4_SYSTEM_ID)
    def test_each_registered_legacy_asset_blocks_new_identity_even_without_ready_rt(self):
        """六类旧登记任一存在即阻止另建，不以状态或 DataId/RT 是否存在筛选。"""
        self._metadata()
        for asset_id in ASSET_IDS:
            with self.subTest(asset_id=asset_id):
                snapshot = Snapshot.objects.create(
                    system_id="bk-audit", resource_type_id=asset_id, status=SnapshotRunningStatus.CLOSED
                )
                old_status = {f"bk-audit-{asset_id}": False, "historical-marker": True}
                GlobalMetaConfig.set(INIT_ASSET_FINISHED_KEY, old_status)
                with mock.patch("services.web.entry.init.base.resource.databus.collector.toggle_join_data") as toggle:
                    with self.assertRaisesRegex(ParamsNotValid, "bk-audit.*" + asset_id):
                        SystemInitHandler().init_asset()
                toggle.assert_not_called()
                snapshot.refresh_from_db()
                self.assertEqual(
                    (snapshot.system_id, snapshot.bkbase_data_id, snapshot.bkbase_table_id), ("bk-audit", None, None)
                )
                self.assertEqual(GlobalMetaConfig.get(INIT_ASSET_FINISHED_KEY), old_status)
                snapshot.delete()

    @override_settings(BUILTIN_ASSET_SYSTEM_ID=V4_SYSTEM_ID)
    def test_missing_local_system_fails_before_any_asset_write_or_marker_change(self):
        old_status = {"bk-audit-risk": True}
        GlobalMetaConfig.set(INIT_ASSET_FINISHED_KEY, old_status)
        with mock.patch("services.web.entry.init.base.resource.databus.collector.toggle_join_data") as toggle:
            with self.assertRaisesRegex(ParamsNotValid, V4_SYSTEM_ID):
                SystemInitHandler().init_asset()
        toggle.assert_not_called()
        self.assertEqual(GlobalMetaConfig.get(INIT_ASSET_FINISHED_KEY), old_status)

    @override_settings(BUILTIN_ASSET_SYSTEM_ID=V4_SYSTEM_ID)
    def test_missing_resource_metadata_lists_gaps_before_any_asset_write(self):
        self._metadata(resource_ids=("risk", "strategy"))
        GlobalMetaConfig.set(INIT_ASSET_FINISHED_KEY, {"bk-audit-risk": True})
        with mock.patch("services.web.entry.init.base.resource.databus.collector.toggle_join_data") as toggle:
            with self.assertRaises(ParamsNotValid) as caught:
                SystemInitHandler().init_asset()
        for asset_id in ("strategy_tag", "ticket_permission", "ticket_node", "manual_event"):
            self.assertIn(asset_id, str(caught.exception))
        toggle.assert_not_called()
        self.assertEqual(GlobalMetaConfig.get(INIT_ASSET_FINISHED_KEY), {"bk-audit-risk": True})

    @override_settings(BUILTIN_ASSET_SYSTEM_ID=V4_SYSTEM_ID)
    def test_explicit_id_ignores_third_party_and_non_asset_legacy_snapshots(self):
        self._metadata()
        Snapshot.objects.create(system_id="external", resource_type_id="risk")
        Snapshot.objects.create(system_id="bk-audit", resource_type_id="host")
        Snapshot.objects.create(system_id="bk-audit", resource_type_id="strategy", join_data_type=JoinDataType.BASIC)
        with mock.patch("services.web.entry.init.base.resource.databus.collector.toggle_join_data") as toggle:
            SystemInitHandler().init_asset()
        self.assertEqual({call.args[0]["system_id"] for call in toggle.call_args_list}, {V4_SYSTEM_ID})

    @override_settings(BUILTIN_ASSET_SYSTEM_ID=V4_SYSTEM_ID)
    def test_rt_sync_reads_new_identity_but_never_replaces_existing_rt(self):
        Snapshot.objects.create(
            system_id=V4_SYSTEM_ID,
            resource_type_id="risk",
            bkbase_data_id=123,
            bkbase_table_id="new_asset_risk_rt",
            status=SnapshotRunningStatus.RUNNING,
        )
        sync_asset_bkbase_rt_ids()
        self.assertEqual(
            GlobalMetaConfig.get(
                ASSET_RISK_BKBASE_RT_ID_KEY,
                config_level=ConfigLevelChoices.NAMESPACE,
                instance_key=self.namespace,
                default="",
            ),
            "new_asset_risk_rt",
        )
        GlobalMetaConfig.set(
            ASSET_RISK_BKBASE_RT_ID_KEY,
            "historical_risk_rt",
            config_level=ConfigLevelChoices.NAMESPACE,
            instance_key=self.namespace,
        )
        sync_asset_bkbase_rt_ids()
        self.assertEqual(
            GlobalMetaConfig.get(
                ASSET_RISK_BKBASE_RT_ID_KEY, config_level=ConfigLevelChoices.NAMESPACE, instance_key=self.namespace
            ),
            "historical_risk_rt",
        )

    @override_settings(BUILTIN_ASSET_SYSTEM_ID=V4_SYSTEM_ID)
    def test_default_strategy_reads_manual_event_from_new_identity(self):
        Snapshot.objects.create(
            system_id=V4_SYSTEM_ID,
            resource_type_id="manual_event",
            bkbase_table_id="new_manual_event_rt",
            status=SnapshotRunningStatus.RUNNING,
        )
        with mock.patch.object(SystemInitHandler, "_build_system_rule_audit_params", return_value={}) as build:
            SystemInitHandler().init_system_rule_audit()
        build.assert_called_once_with("new_manual_event_rt")


@override_settings(BUILTIN_ASSET_SYSTEM_ID=V4_SYSTEM_ID, BKPAAS_MULTI_TENANT_MODE=True, BK_TENANT_ID="runtime-tenant")
class BuiltinAssetCallbackTests(TestCase):
    """只给审计自身内置资产的三路回调传部署租户，不读取请求用户。"""

    def _metadata(self, system_id=V4_SYSTEM_ID, resource_id="manual_event"):
        system, _ = System.objects.get_or_create(
            system_id=system_id,
            defaults={
                "instance_id": system_id,
                "source_type": "iam_v4",
                "namespace": self.namespace,
                "callback_url": "https://shared.example.test/api/v1/iam/resources/",
                "auth_token": "synthetic-callback-token",
            },
        )
        resource_type = ResourceType.objects.create(
            system_id=system_id,
            resource_type_id=resource_id,
            name=resource_id,
            unique_id=f"{system_id}:{resource_id}",
        )
        return system, resource_type

    def _assert_three_routes(self, system_id, resource_id, expected_headers, join_data_type=JoinDataType.ASSET):
        """观察真实预检/Schema/PULL 产物，只隔离外部 HTTP 和缓存。"""
        system, resource_type = self._metadata(system_id, resource_id)
        response = mock.Mock(status_code=200)
        response.json.return_value = {"result": True, "data": {"properties": {"id": {"type": "string"}}}}
        with mock.patch("services.web.databus.collector.resources.requests.session") as session:
            session.return_value.post.return_value = response
            ToggleJoinDataResource().pre_check(system_id, resource_id, join_data_type)
            self.assertEqual(
                session.return_value.post.call_args.kwargs["headers"],
                {"Authorization": system.base64_token, **expected_headers},
            )
            if expected_headers:
                self.assertIs(session.return_value.post.call_args.kwargs.get("allow_redirects", True), False)
            else:
                self.assertNotIn("allow_redirects", session.return_value.post.call_args.kwargs)
        schema_resource = ResourceTypeSchema()
        schema_expected = (
            expected_headers if join_data_type == JoinDataType.ASSET else {"X-Bk-Tenant-Id": "runtime-tenant"}
        )
        with mock.patch.object(schema_resource, "get_cache", return_value=None), mock.patch.object(
            schema_resource, "set_cache"
        ), mock.patch("apps.meta.resources.requests.session") as session:
            session.return_value.post.return_value = response
            self.assertEqual(schema_resource.get_schema(system, resource_type)[0]["id"], "id")
            self.assertEqual(
                session.return_value.post.call_args.kwargs["headers"],
                {"Authorization": system.base64_token, **schema_expected},
            )
        handler = HttpPullHandler(system, resource_type, Snapshot(), join_data_type)
        headers = handler.config["access_conf_info"]["resource"]["scope"][0]["headers"]
        self.assertEqual(
            headers, {"Content-type": "application/json", "Authorization": system.base64_token, **expected_headers}
        )

    def test_builtin_asset_three_routes_use_runtime_tenant(self):
        for asset_id in ASSET_IDS:
            with self.subTest(asset_id=asset_id):
                self._assert_three_routes(V4_SYSTEM_ID, asset_id, {"X-Bk-Tenant-Id": "runtime-tenant"})

    @override_settings(BUILTIN_ASSET_SYSTEM_ID="")
    def test_retained_legacy_asset_also_uses_runtime_tenant_after_backend_switch(self):
        self._assert_three_routes("bk-audit", "risk", {"X-Bk-Tenant-Id": "runtime-tenant"})

    def test_third_party_system_does_not_receive_tenant_header(self):
        self._assert_three_routes("iam_v4_external", "risk", {})

    def test_non_builtin_resource_does_not_receive_tenant_header(self):
        self._assert_three_routes(V4_SYSTEM_ID, "host", {})

    @override_settings(BKPAAS_MULTI_TENANT_MODE=False)
    def test_single_tenant_callbacks_keep_original_headers(self):
        self._assert_three_routes(V4_SYSTEM_ID, "manual_event", {})

    def test_non_asset_precheck_and_pull_keep_original_headers(self):
        self._assert_three_routes(V4_SYSTEM_ID, "manual_event", {}, join_data_type=JoinDataType.BASIC)
