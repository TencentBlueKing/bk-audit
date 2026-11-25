# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from contextlib import redirect_stdout
from io import StringIO
from typing import Dict
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase
from django.test.utils import override_settings

from apps.meta.models import GlobalMetaConfig
from apps.permission.handlers.resource_types import ResourceEnum
from services.web.bkbase.exceptions import (
    BKBaseFlowOperationPending,
    BKBaseResourceMappingError,
)
from services.web.databus.constants import (
    CLEAN_CONFIG_JSON_CONF_KEY,
    JoinDataType,
    SnapshotRunningStatus,
    SnapShotStorageChoices,
)
from services.web.databus.models import RedisConfig, Snapshot
from services.web.entry.constants import (
    AGENT_AUTH_KEY,
    AUDIT_DOC_CONFIG_KEY,
    INIT_AGENT_CONFIG_FINISHED_KEY,
    INIT_ASSET_FINISHED_KEY,
    INIT_DOC_CONFIG_FINISHED_KEY,
    INIT_SDK_CONFIG_FINISHED_KEY,
    INIT_SYSTEM_RULE_AUDIT_FINISHED_KEY,
    SDK_CONFIG_KEY,
)
from services.web.entry.init.base import SystemInitHandler
from services.web.entry.init.v4_wait import BKBaseV4InitTimeout, V4InitWait
from services.web.scene.constants import DEFAULT_SCENE_NAME, BindingType
from services.web.scene.models import Scene
from services.web.strategy_v2.constants import (
    StrategySource,
    StrategyStatusChoices,
    StrategyType,
)
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase


class SystemSnapshotInitGateTests(SimpleTestCase):
    @override_settings(BKBASE_API_VERSION="v4", SNAPSHOT_USERINFO_RESOURCE_URL="")
    def test_v4_snapshots_progress_to_ready_in_one_init(self):
        handler = SystemInitHandler()
        with mock.patch(
            "services.web.entry.init.base.create_iam_data_link", side_effect=["DataConn", None, "Clean", None]
        ) as advance, mock.patch("services.web.entry.init.v4_wait.sleep") as wait:
            self.assertTrue(handler.init_snapshot(v4_wait=V4InitWait(300)))
        self.assertEqual(
            [entry.args[0] for entry in advance.call_args_list], ["action", "resource_type", "action", "action"]
        )
        self.assertEqual(wait.call_args_list, [mock.call(5), mock.call(5)])

    @override_settings(BKBASE_API_VERSION="v4", SNAPSHOT_USERINFO_RESOURCE_URL="")
    def test_v4_snapshot_timeout_keeps_pending_phase(self):
        clock = [0]
        with mock.patch("services.web.entry.init.v4_wait.monotonic", side_effect=lambda: clock[0]), mock.patch(
            "services.web.entry.init.v4_wait.sleep", side_effect=lambda seconds: clock.__setitem__(0, seconds)
        ), mock.patch(
            "services.web.entry.init.base.create_iam_data_link", side_effect=["DataConn", None]
        ) as advance, self.assertRaisesRegex(
            BKBaseV4InitTimeout, "action=DataConn"
        ):
            SystemInitHandler().init_snapshot(v4_wait=V4InitWait(2))
        self.assertEqual(advance.call_count, 2)

    @override_settings(BKBASE_API_VERSION="v4", SNAPSHOT_USERINFO_RESOURCE_URL="")
    def test_v4_snapshot_missing_migration_binding_does_not_wait(self):
        with mock.patch(
            "services.web.entry.init.base.create_iam_data_link", return_value="migration binding"
        ), mock.patch("services.web.entry.init.v4_wait.sleep") as wait, self.assertRaisesRegex(
            BKBaseResourceMappingError, "migration binding"
        ):
            SystemInitHandler().init_snapshot(v4_wait=V4InitWait(300))
        wait.assert_not_called()

    def test_init_snapshot_only_v4_passes_redis_fallback(self):
        handler = SystemInitHandler()
        for version in ("v3", "v4"):
            with self.subTest(version=version), override_settings(
                BKBASE_API_VERSION=version, SNAPSHOT_USERINFO_RESOURCE_URL=""
            ), mock.patch(
                "services.web.entry.init.base.create_iam_data_link", return_value=None
            ) as create, mock.patch.object(
                handler, "pre_check", return_value=False
            ), mock.patch.object(
                handler, "post_init"
            ):
                handler.init_snapshot()
                expected = {"init_redis_fallback": handler._resolve_snapshot_redis} if version == "v4" else {}
                self.assertEqual(
                    create.call_args_list, [mock.call("action", **expected), mock.call("resource_type", **expected)]
                )

    @override_settings(BKBASE_API_VERSION="v3", BKBASE_V4_INIT_TIMEOUT_SECONDS="0")
    def test_v3_init_preserves_strategy_storage_order_without_v4_budget(self):
        calls = []
        methods = (
            "pre_init",
            "init_standard_fields",
            "init_es",
            "init_doris",
            "init_redis",
            "init_snapshot",
            "init_event",
            "create_or_update_plugin_etl",
            "init_system",
            "init_asset",
            "init_system_rule_audit",
            "init_global_meta_config",
            "init_itsm_v4",
        )
        with mock.patch.multiple(SystemInitHandler, **{name: mock.DEFAULT for name in methods}) as patched:
            for name, method in patched.items():
                method.side_effect = lambda *args, step=name: calls.append(step) or True
            with mock.patch(
                "services.web.entry.init.base.init_strategy_storage",
                create=True,
                side_effect=lambda: calls.append("strategy_storage"),
            ):
                self.assertTrue(SystemInitHandler().init())
        self.assertEqual(calls[3:6], ["init_doris", "strategy_storage", "init_redis"])
        self.assertLess(calls.index("strategy_storage"), calls.index("init_system_rule_audit"))

    def test_init_command_times_out_before_event_when_v4_snapshot_is_pending(self):
        for multi_tenant in (False, True):
            with self.subTest(multi_tenant=multi_tenant), override_settings(
                BKBASE_API_VERSION="v4",
                BKBASE_V4_INIT_TIMEOUT_SECONDS="300",
                BKPAAS_MULTI_TENANT_MODE=multi_tenant,
                SNAPSHOT_USERINFO_RESOURCE_URL="",
            ), mock.patch.multiple(
                SystemInitHandler,
                pre_init=mock.DEFAULT,
                init_standard_fields=mock.DEFAULT,
                init_es=mock.DEFAULT,
                init_doris=mock.DEFAULT,
                init_redis=mock.DEFAULT,
            ), mock.patch(
                "services.web.entry.init.base.create_iam_data_link", return_value="DataSource"
            ), mock.patch(
                "services.web.entry.init.v4_wait.monotonic", side_effect=[0, 0, 300, 300]
            ), mock.patch.object(
                SystemInitHandler, "init_event"
            ) as init_event, self.assertRaisesRegex(
                CommandError, "IAM system snapshot.*action=DataSource"
            ):
                call_command("init_system")
            init_event.assert_not_called()

    @override_settings(BKBASE_API_VERSION="v4", SNAPSHOT_USERINFO_RESOURCE_URL="")
    def test_init_stops_before_event_when_snapshot_raises(self):
        failure = RuntimeError("synthetic snapshot activation failure")
        with mock.patch.multiple(
            SystemInitHandler,
            pre_init=mock.DEFAULT,
            init_standard_fields=mock.DEFAULT,
            init_es=mock.DEFAULT,
            init_doris=mock.DEFAULT,
            init_redis=mock.DEFAULT,
        ), mock.patch("services.web.entry.init.base.create_iam_data_link", side_effect=failure), mock.patch.object(
            SystemInitHandler, "init_event"
        ) as init_event, self.assertRaises(
            RuntimeError
        ) as caught:
            SystemInitHandler().init()
        self.assertIs(caught.exception, failure)
        init_event.assert_not_called()


@override_settings(DEFAULT_NAMESPACE="default")
class InitSnapshotRedisSelectionTests(TestCase):
    def setUp(self):
        self.enterContext(
            mock.patch("requests.sessions.Session.request", side_effect=AssertionError("Unexpected HTTP"))
        )

    def test_init_fallback_rejects_malformed_declared_candidate_before_query(self):
        declarations = [
            {"namespace": "default", "redis_name_en": "registered"},
            {"namespace": "default", "redis_name_en": ""},
        ]
        with mock.patch("services.web.entry.init.base.get_secret_json", return_value=declarations), mock.patch.object(
            RedisConfig.objects, "filter"
        ) as query:
            with self.assertRaises(BKBaseResourceMappingError):
                SystemInitHandler()._resolve_snapshot_redis({"tenant": "default", "namespace": "audit"})
            query.assert_not_called()

    def test_init_fallback_rejects_ambiguous_or_unbound_redis(self):
        context = {"tenant": "default", "namespace": "audit"}
        ref = {"kind": "Redis", "tenant": "default", "namespace": "audit", "name": "registered"}
        row = RedisConfig.objects.create(
            namespace="default",
            redis_name_en="registered",
            redis_name="fixture",
            connection_info={},
            version="6",
            extra={"bkbase_v4": {"registration_state": "bound", "resource_ref": ref}},
        )
        declaration = {"namespace": "default", "redis_name_en": "registered"}
        handler = SystemInitHandler()
        for declarations in ([], [declaration, {**declaration, "redis_name_en": "unbound"}]):
            with self.subTest(declarations=declarations), mock.patch(
                "services.web.entry.init.base.get_secret_json", return_value=declarations
            ), mock.patch.object(RedisConfig.objects, "filter") as query:
                with self.assertRaises(BKBaseResourceMappingError) as caught:
                    handler._resolve_snapshot_redis(context)
                query.assert_not_called()
                self.assertIn("BKAPP_BKBASE_V4_SYSTEM_SNAPSHOT_CREATE", str(caught.exception))
        with mock.patch("services.web.entry.init.base.get_secret_json", return_value=[declaration]):
            self.assertEqual(handler._resolve_snapshot_redis(context), ref)
            for binding in (
                {},
                {"registration_state": "registering", "resource_ref": ref},
                {"registration_state": "bound", "resource_ref": {**ref, "tenant": "other"}},
                {"registration_state": "bound", "resource_ref": {**ref, "namespace": "other"}},
                {"registration_state": "bound", "resource_ref": {**ref, "kind": "Kafka"}},
            ):
                row.extra = {"bkbase_v4": binding}
                row.save(update_fields=["extra"])
                with self.subTest(binding=binding), self.assertRaises(BKBaseResourceMappingError):
                    handler._resolve_snapshot_redis(context)


@override_settings(BKAPP_INIT_SYSTEM="True")
class SystemInitAssetTests(TestCase):
    def setUp(self):
        super().setUp()
        self.handler = SystemInitHandler()

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get")
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    @mock.patch("services.web.entry.init.base.resource.databus.collector.toggle_join_data")
    def test_init_asset_enable_new_assets(self, mock_toggle, mock_set, mock_get):
        mock_get.return_value = {}

        self.handler.init_asset()

        expected_calls = []
        for resource_cls in [
            ResourceEnum.RISK,
            ResourceEnum.STRATEGY,
            ResourceEnum.STRATEGY_TAG,
            ResourceEnum.TICKET_NODE,
        ]:
            expected_calls.append(
                mock.call(
                    {
                        "system_id": resource_cls.system_id,
                        "resource_type_id": resource_cls.id,
                        "is_enabled": True,
                        "join_data_type": JoinDataType.ASSET.value,
                        "storage_type": [
                            SnapShotStorageChoices.HDFS.value,
                            SnapShotStorageChoices.DORIS.value,
                        ],
                    }
                )
            )

        mock_toggle.assert_has_calls(expected_calls, any_order=True)

        saved_status: Dict[str, bool] = mock_set.call_args.args[1]
        self.assertEqual(mock_set.call_args.args[0], INIT_ASSET_FINISHED_KEY)
        for resource_cls in [
            ResourceEnum.RISK,
            ResourceEnum.STRATEGY,
            ResourceEnum.STRATEGY_TAG,
            ResourceEnum.TICKET_NODE,
        ]:
            key = f"{resource_cls.system_id}-{resource_cls.id}"
            self.assertTrue(saved_status.get(key))

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get")
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    @mock.patch("services.web.entry.init.base.resource.databus.collector.toggle_join_data")
    def test_init_asset_manual_event_with_custom_conf(self, mock_toggle, mock_set, mock_get):
        mock_get.return_value = {}

        self.handler.init_asset()

        manual_call = mock.call(
            {
                "system_id": ResourceEnum.MANUAL_EVENT.system_id,
                "resource_type_id": ResourceEnum.MANUAL_EVENT.id,
                "is_enabled": True,
                "join_data_type": JoinDataType.ASSET.value,
                "storage_type": [
                    SnapShotStorageChoices.HDFS.value,
                    SnapShotStorageChoices.DORIS.value,
                ],
                "custom_config": {
                    CLEAN_CONFIG_JSON_CONF_KEY: {
                        "time_format": "Unix Time Stamp(milliseconds)",
                        "timestamp_len": 13,
                        "timezone": 0,
                        "time_field_name": "event_time_timestamp",
                    }
                },
            }
        )
        self.assertIn(manual_call, mock_toggle.call_args_list)

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get")
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    @mock.patch("services.web.entry.init.base.resource.databus.collector.toggle_join_data")
    def test_init_asset_skip_existing(self, mock_toggle, mock_set, mock_get):
        key = f"{settings.BK_IAM_SYSTEM_ID}-{ResourceEnum.RISK.id}"
        mock_get.return_value = {key: True}

        self.handler.init_asset()

        mock_toggle.assert_any_call(
            {
                "system_id": ResourceEnum.STRATEGY.system_id,
                "resource_type_id": ResourceEnum.STRATEGY.id,
                "is_enabled": True,
                "join_data_type": JoinDataType.ASSET.value,
                "storage_type": [
                    SnapShotStorageChoices.HDFS.value,
                    SnapShotStorageChoices.DORIS.value,
                ],
            }
        )
        mock_toggle.assert_any_call(
            {
                "system_id": ResourceEnum.STRATEGY_TAG.system_id,
                "resource_type_id": ResourceEnum.STRATEGY_TAG.id,
                "is_enabled": True,
                "join_data_type": JoinDataType.ASSET.value,
                "storage_type": [
                    SnapShotStorageChoices.HDFS.value,
                    SnapShotStorageChoices.DORIS.value,
                ],
            }
        )
        # ensure risk was skipped
        skipped_call = mock.call(
            {
                "system_id": ResourceEnum.RISK.system_id,
                "resource_type_id": ResourceEnum.RISK.id,
                "is_enabled": True,
                "join_data_type": JoinDataType.ASSET.value,
                "storage_type": [
                    SnapShotStorageChoices.HDFS.value,
                    SnapShotStorageChoices.DORIS.value,
                ],
            }
        )
        self.assertNotIn(skipped_call, mock_toggle.call_args_list)

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get")
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    @mock.patch("services.web.entry.init.base.resource.databus.collector.toggle_join_data")
    def test_init_asset_failure_recorded(self, mock_toggle, mock_set, mock_get):
        error = RuntimeError("mock failure")
        mock_get.return_value = {}
        mock_toggle.side_effect = error

        self.handler.init_asset()

        saved_status = mock_set.call_args.args[1]
        for resource_cls in [
            ResourceEnum.RISK,
            ResourceEnum.STRATEGY,
            ResourceEnum.STRATEGY_TAG,
            ResourceEnum.TICKET_NODE,
        ]:
            key = f"{resource_cls.system_id}-{resource_cls.id}"
            self.assertFalse(saved_status.get(key))


@override_settings(BKAPP_INIT_SYSTEM="True")
class SystemInitRuleAuditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """显式准备默认场景，不依赖复用测试库残留的数据迁移结果。"""
        super().setUpTestData()
        Scene.objects.get_or_create(name=DEFAULT_SCENE_NAME)

    def setUp(self):
        super().setUp()
        self.handler = SystemInitHandler()
        Scene.objects.get_or_create(name='系统默认场景', defaults={"description": "测试场景"})

    def _snapshot(self, *, status=SnapshotRunningStatus.RUNNING.value, table="test_rt_id"):
        return Snapshot.objects.create(
            system_id=ResourceEnum.MANUAL_EVENT.system_id,
            resource_type_id=ResourceEnum.MANUAL_EVENT.id,
            bkbase_table_id=table,
            status=status,
            join_data_type=JoinDataType.ASSET.value,
        )

    def _registered_strategy(self, status=StrategyStatusChoices.START_FAILED):
        strategy = Strategy.objects.create(
            namespace=settings.DEFAULT_NAMESPACE,
            strategy_name="手动新建风险",
            strategy_type=StrategyType.RULE,
            source=StrategySource.SYSTEM,
            status=status,
            backend_data={"flow_id": 91},
            configs={"data_source": {"rt_id": "test_rt_id"}},
        )
        GlobalMetaConfig.set("init_system_rule_audit_strategy_id", strategy.strategy_id)
        return strategy

    def test_init_default_rule_retries_existing_failed_id(self):
        self._snapshot()
        strategy = self._registered_strategy()
        with mock.patch(
            "services.web.strategy_v2.resources.RetryStrategy.retry_existing", create=True
        ) as retry, mock.patch(
            "services.web.strategy_v2.resources.CreateStrategy.request_for_init", create=True
        ) as create:
            self.handler.init_system_rule_audit()
        retry.assert_called_once_with(strategy, allow_create=False)
        create.assert_not_called()
        self.assertFalse(GlobalMetaConfig.get(INIT_SYSTEM_RULE_AUDIT_FINISHED_KEY, default=False))

    def test_unmanaged_same_name_never_counts_as_finished(self):
        self._snapshot()
        Strategy.objects.create(
            namespace=settings.DEFAULT_NAMESPACE,
            strategy_name="手动新建风险",
            strategy_type=StrategyType.RULE,
            source=StrategySource.USER,
            status=StrategyStatusChoices.RUNNING,
        )
        with mock.patch(
            "services.web.strategy_v2.resources.RetryStrategy.retry_existing", create=True
        ) as retry, mock.patch(
            "services.web.strategy_v2.resources.CreateStrategy.request_for_init", create=True
        ) as create:
            self.handler.init_system_rule_audit()
        retry.assert_not_called()
        create.assert_not_called()
        self.assertFalse(GlobalMetaConfig.get(INIT_SYSTEM_RULE_AUDIT_FINISHED_KEY, default=False))
        self.assertIsNone(GlobalMetaConfig.get("init_system_rule_audit_strategy_id", default=None))

    def test_registered_running_strategy_is_the_only_new_completion(self):
        self._snapshot()
        self._registered_strategy(StrategyStatusChoices.RUNNING)
        self.handler.init_system_rule_audit()
        self.assertIs(GlobalMetaConfig.get(INIT_SYSTEM_RULE_AUDIT_FINISHED_KEY, default=False), True)

    def test_default_rule_create_keeps_scene_and_manual_event_table_parameters(self):
        snapshot = self._snapshot()

        def create(params):
            strategy = self._registered_strategy(StrategyStatusChoices.STARTING)
            # 模拟另一轮 init 在控制器调度前读取到已持久化的归属，不得再次创建。
            self.handler.init_system_rule_audit()
            return {"strategy_id": strategy.strategy_id}

        with mock.patch(
            "services.web.strategy_v2.resources.CreateStrategy.request_for_init", create=True, side_effect=create
        ) as request, mock.patch("services.web.entry.init.base.resource.strategy_v2.create_strategy") as public_create:
            self.handler.init_system_rule_audit()
        request.assert_called_once()
        params = request.call_args.args[0]
        self.assertEqual(params["binding_type"], BindingType.SCENE_BINDING)
        scene = Scene.objects.get(scene_id=params["scene_id"])
        self.assertEqual(scene.name, DEFAULT_SCENE_NAME)
        self.assertEqual(params["configs"]["data_source"]["rt_id"], snapshot.bkbase_table_id)
        self.assertEqual(params["source"], StrategySource.SYSTEM)
        public_create.assert_not_called()
        self.assertFalse(GlobalMetaConfig.get(INIT_SYSTEM_RULE_AUDIT_FINISHED_KEY, default=False))

    def test_pending_default_rule_keeps_original_id_without_retry(self):
        self._snapshot()
        strategy = self._registered_strategy(StrategyStatusChoices.STARTING)
        for status in (StrategyStatusChoices.STARTING, StrategyStatusChoices.UPDATING):
            strategy.status = status
            strategy.save(update_fields=["status"])
            with mock.patch("services.web.strategy_v2.resources.RetryStrategy.retry_existing", create=True) as retry:
                self.handler.init_system_rule_audit()
            retry.assert_not_called()
            self.assertFalse(GlobalMetaConfig.get(INIT_SYSTEM_RULE_AUDIT_FINISHED_KEY, default=False))
        self.assertEqual(GlobalMetaConfig.get("init_system_rule_audit_strategy_id"), strategy.strategy_id)

    def test_default_rule_starting_without_flow_reports_how_to_check_dispatch(self):
        self._snapshot()
        # 模拟 ID 已落库，但进程在投递前退出后的持久状态。
        strategy = self._registered_strategy(StrategyStatusChoices.STARTING)
        strategy.backend_data = {}
        strategy.save(update_fields=["backend_data"])
        output = StringIO()
        with redirect_stdout(output), mock.patch("services.web.strategy_v2.resources.call_controller") as dispatch:
            self.handler.init_system_rule_audit()
        self.assertIn(str(strategy.strategy_id), output.getvalue())
        self.assertIn("核对队列任务和原 Flow", output.getvalue())
        dispatch.assert_not_called()
        self.assertEqual(Strategy.objects.filter(strategy_name=strategy.strategy_name).count(), 1)
        self.assertFalse(GlobalMetaConfig.get(INIT_SYSTEM_RULE_AUDIT_FINISHED_KEY, default=False))

    def test_unready_asset_snapshot_does_not_create_or_retry_default_rule(self):
        self._registered_strategy()
        snapshot = self._snapshot(table="")
        with mock.patch(
            "services.web.strategy_v2.resources.RetryStrategy.retry_existing", create=True
        ) as retry, mock.patch(
            "services.web.strategy_v2.resources.CreateStrategy.request_for_init", create=True
        ) as create:
            self.handler.init_system_rule_audit()
            snapshot.bkbase_table_id = "test_rt_id"
            snapshot.status = SnapshotRunningStatus.PREPARING
            snapshot.save(update_fields=["bkbase_table_id", "status"])
            self.handler.init_system_rule_audit()
        create.assert_not_called()
        retry.assert_not_called()
        self.assertFalse(GlobalMetaConfig.get(INIT_SYSTEM_RULE_AUDIT_FINISHED_KEY, default=False))

    def test_default_rule_retry_hard_error_is_not_silenced(self):
        self._snapshot()
        self._registered_strategy()
        failure = RuntimeError("synthetic controller rejection")
        with mock.patch(
            "services.web.strategy_v2.resources.RetryStrategy.retry_existing", create=True, side_effect=failure
        ):
            with self.assertRaises(RuntimeError) as caught:
                self.handler.init_system_rule_audit()
        self.assertIs(caught.exception, failure)
        self.assertFalse(GlobalMetaConfig.get(INIT_SYSTEM_RULE_AUDIT_FINISHED_KEY, default=False))

    def test_default_rule_missing_flow_is_a_hard_block(self):
        self._snapshot()
        strategy = self._registered_strategy()
        strategy.backend_data = {}
        strategy.save(update_fields=["backend_data"])
        for version in ("v3", "v4"):
            with self.subTest(version=version), override_settings(BKBASE_API_VERSION=version):
                with self.assertRaises(BKBaseResourceMappingError):
                    self.handler.init_system_rule_audit()
        self.assertFalse(GlobalMetaConfig.get(INIT_SYSTEM_RULE_AUDIT_FINISHED_KEY, default=False))
        self.assertEqual(GlobalMetaConfig.get("init_system_rule_audit_strategy_id"), strategy.strategy_id)

    def test_default_rule_genuinely_pending_recovery_is_only_observed(self):
        self._snapshot()
        strategy = self._registered_strategy()
        with mock.patch(
            "services.web.strategy_v2.resources.RetryStrategy.retry_existing",
            side_effect=BKBaseFlowOperationPending(message="synthetic operation in progress"),
        ):
            self.handler.init_system_rule_audit()
        self.assertFalse(GlobalMetaConfig.get(INIT_SYSTEM_RULE_AUDIT_FINISHED_KEY, default=False))
        self.assertEqual(GlobalMetaConfig.get("init_system_rule_audit_strategy_id"), strategy.strategy_id)

    def test_renamed_registered_default_rule_keeps_original_ownership(self):
        self._snapshot()
        strategy = self._registered_strategy()
        strategy.strategy_name = "renamed builtin rule"
        strategy.save(update_fields=["strategy_name"])
        with mock.patch("services.web.strategy_v2.resources.RetryStrategy.retry_existing") as retry:
            self.handler.init_system_rule_audit()
        retry.assert_called_once_with(strategy, allow_create=False)
        self.assertFalse(GlobalMetaConfig.get(INIT_SYSTEM_RULE_AUDIT_FINISHED_KEY, default=False))

    def test_default_rule_changed_input_table_is_not_automatically_retried(self):
        self._snapshot()
        strategy = self._registered_strategy()
        strategy.configs = {"data_source": {"rt_id": "another_table"}}
        strategy.save(update_fields=["configs"])
        with mock.patch("services.web.strategy_v2.resources.RetryStrategy.retry_existing") as retry:
            self.handler.init_system_rule_audit()
        retry.assert_not_called()
        strategy.refresh_from_db()
        self.assertEqual(strategy.status, StrategyStatusChoices.START_FAILED)
        self.assertEqual(strategy.configs["data_source"]["rt_id"], "another_table")
        self.assertFalse(GlobalMetaConfig.get(INIT_SYSTEM_RULE_AUDIT_FINISHED_KEY, default=False))

    def test_old_finished_marker_does_not_backfill_strategy_ownership(self):
        GlobalMetaConfig.set(INIT_SYSTEM_RULE_AUDIT_FINISHED_KEY, True)
        self.handler.init_system_rule_audit()
        self.assertIsNone(GlobalMetaConfig.get("init_system_rule_audit_strategy_id", default=None))

    def test_registered_strategy_scope_mismatch_never_operates_or_finishes(self):
        self._snapshot()
        strategy = self._registered_strategy(StrategyStatusChoices.RUNNING)
        for field, value in (
            ("namespace", "another_namespace"),
            ("source", StrategySource.USER),
            ("strategy_type", StrategyType.MODEL),
        ):
            original = getattr(strategy, field)
            setattr(strategy, field, value)
            strategy.save(update_fields=[field])
            with mock.patch("services.web.strategy_v2.resources.RetryStrategy.retry_existing") as retry:
                self.handler.init_system_rule_audit()
            retry.assert_not_called()
            self.assertFalse(GlobalMetaConfig.get(INIT_SYSTEM_RULE_AUDIT_FINISHED_KEY, default=False))
            setattr(strategy, field, original)
            strategy.save(update_fields=[field])


@override_settings(BKAPP_INIT_SYSTEM="True")
class SystemInitSdkConfigTests(TestCase):
    """测试 init_sdk_config 方法"""

    def setUp(self):
        super().setUp()
        self.handler = SystemInitHandler()

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get", return_value=False)
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    @override_settings(
        BKAPP_GO_SDK_CONFIG='{"doc": "go_sdk_doc"}',
        BKAPP_JAVA_SDK_CONFIG='{"doc": "java_sdk_doc"}',
        BKAPP_PYTHON_SDK_CONFIG='{"doc": "python_sdk_doc"}',
    )
    def test_init_sdk_config_with_env(self, mock_set, _mock_get):
        """测试从 settings 读取 SDK 配置"""
        self.handler.init_sdk_config()

        self.assertEqual(mock_set.call_args_list[0].args[0], SDK_CONFIG_KEY)
        sdk_config = mock_set.call_args_list[0].args[1]
        self.assertEqual(sdk_config["go_sdk"], '{"doc": "go_sdk_doc"}')
        self.assertEqual(sdk_config["java_sdk"], '{"doc": "java_sdk_doc"}')
        self.assertEqual(sdk_config["python_sdk"], '{"doc": "python_sdk_doc"}')
        self.assertEqual(
            mock_set.call_args_list,
            [
                mock.call(SDK_CONFIG_KEY, sdk_config),
                mock.call(INIT_SDK_CONFIG_FINISHED_KEY, True),
            ],
        )

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get", return_value=True)
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    def test_init_sdk_config_skips_completed_initialization(self, mock_set, _mock_get):
        self.handler.init_sdk_config()

        mock_set.assert_not_called()


@override_settings(BKAPP_INIT_SYSTEM="True")
class SystemInitDocConfigTests(TestCase):
    """测试 init_doc_config 方法"""

    def setUp(self):
        super().setUp()
        self.handler = SystemInitHandler()

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get", return_value=False)
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    @override_settings(
        BKAPP_AUDIT_ACCESS_GUIDE="https://example.com/guide",
        BKAPP_AUDIT_OPERATION_LOG_RECORD_STANDARDS="https://example.com/standards",
    )
    def test_init_doc_config_with_env(self, mock_set, _mock_get):
        """测试从 settings 读取文档配置"""
        self.handler.init_doc_config()

        self.assertEqual(mock_set.call_args_list[0].args[0], AUDIT_DOC_CONFIG_KEY)
        doc_config = mock_set.call_args_list[0].args[1]
        self.assertEqual(doc_config["audit_access_guide"], "https://example.com/guide")
        self.assertEqual(doc_config["audit_operation_log_record_standards"], "https://example.com/standards")
        self.assertEqual(
            mock_set.call_args_list,
            [
                mock.call(AUDIT_DOC_CONFIG_KEY, doc_config),
                mock.call(INIT_DOC_CONFIG_FINISHED_KEY, True),
            ],
        )

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get", return_value=True)
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    def test_init_doc_config_skips_completed_initialization(self, mock_set, _mock_get):
        self.handler.init_doc_config()

        mock_set.assert_not_called()


@override_settings(BKAPP_INIT_SYSTEM="True")
class SystemInitAgentConfigTests(TestCase):
    def setUp(self):
        super().setUp()
        self.handler = SystemInitHandler()

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get", return_value=False)
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    @override_settings(
        BKAPP_AGENT_AUTH_CONFIG=(
            '{"agents": [{"code": "bp-ai-aud-rsk-srch", "ping_url": "https://agent.example.com/ping/"}]}'
        )
    )
    def test_init_agent_config_writes_validated_config(self, mock_set, _mock_get):
        self.handler.init_agent_config()

        self.assertEqual(
            mock_set.call_args_list,
            [
                mock.call(
                    AGENT_AUTH_KEY,
                    {
                        "agents": [
                            {
                                "code": "bp-ai-aud-rsk-srch",
                                "enabled": True,
                                "ping_url": "https://agent.example.com/ping/",
                            }
                        ]
                    },
                ),
                mock.call(INIT_AGENT_CONFIG_FINISHED_KEY, True),
            ],
        )

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get", return_value=True)
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    def test_init_agent_config_skips_completed_initialization(self, mock_set, _mock_get):
        self.handler.init_agent_config()

        mock_set.assert_not_called()

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get", return_value=False)
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    @override_settings(BKAPP_AGENT_AUTH_CONFIG="{}")
    def test_init_agent_config_skips_empty_default(self, mock_set, _mock_get):
        self.handler.init_agent_config()

        mock_set.assert_not_called()

    def test_init_global_meta_config_runs_agent_config(self):
        with (
            mock.patch.object(self.handler, "init_doc_config"),
            mock.patch.object(self.handler, "init_sdk_config"),
            mock.patch.object(self.handler, "init_agent_config") as mock_init_agent_config,
        ):
            self.handler.init_global_meta_config()

        mock_init_agent_config.assert_called_once_with()
