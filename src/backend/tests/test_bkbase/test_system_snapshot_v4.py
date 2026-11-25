"""覆盖 IAM 系统快照的发布入口、迁移校验与真实 ETL 消费。"""
import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from bk_resource.exceptions import APIRequestError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from api.bk_base_v4.default import BkBaseV4Resource, ResultTableInfo
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.collector.etl.etl_config_handler.base import BkBaseConfig
from services.web.databus.collector.snapshot.system import v4
from services.web.databus.constants import ACTION_DATA_CONFIG_KEY
from services.web.entry.init.base import SystemInitHandler

SYSTEM_PATH = "services.web.databus.collector.snapshot.system.v4"
ENTRY_PATH = "services.web.entry.init.base"
COMMAND_PATH = "services.web.databus.management.commands.iam_data_pull"


def ref(kind, name, namespace="audit"):
    return {"kind": kind, "tenant": "default", "namespace": namespace, "name": name}


def observed(ref_data, spec, phase="Ok"):
    return {
        "kind": ref_data["kind"],
        "metadata": {key: value for key, value in ref_data.items() if key != "kind"},
        "spec": spec,
        "status": {"phase": phase},
    }


@override_settings(
    BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="default", BKBASE_V4_NAMESPACE="audit", SNAPSHOT_USERINFO_RESOURCE_URL=""
)
class SystemSnapshotTests(SimpleTestCase):
    def setUp(self):
        self.binding = {
            "snapshot_type": "action",
            "data_source": ref("DataSource", "iam_source"),
            "data_id": ref("DataId", "iam_dataid"),
            "source_raw_data_id": 73,
            "clean": ref("Clean", "iam_clean"),
            "result_table_id": "47_iam_actions",
            "result_table": ref("ResultTable", "iam-actions"),
            "storages": {"redis": ref("DataStorage", "iam_storage")},
            "redis": ref("Redis", "iam_redis", "cluster-project"),
        }
        self.row = mock.Mock(config_value={"config_name": "legacy", "bkbase_data_id": 12})
        sdk = mock.Mock()
        self.enterContext(mock.patch(f"{SYSTEM_PATH}.api", new=sdk))
        self.remote = sdk.bk_base_v4
        self.source = observed(
            self.binding["data_source"],
            {
                "data_id": self.binding["data_id"],
                "report_config": {"type": "rest_api", "http_mode": "PULL"},
                "current_status": "Running",
            },
        )
        self.source["metadata"]["labels"] = {"raw_data_id": "73"}
        self.remote.data_source_get.return_value = self.source
        self.remote.clean_get.return_value = observed(
            self.binding["clean"],
            {
                "data_id": self.binding["data_id"],
                "raw_data_id": 73,
                "result_table_id": "47_iam_actions",
                "result_table_source": "new",
                "current_status": "Running",
            },
        )
        self.remote.data_storage_get.return_value = observed(
            self.binding["storages"]["redis"],
            {
                "tableInfo": {
                    "source": {k: v for k, v in self.binding["result_table"].items() if k != "tenant"},
                    "storage": self.binding["redis"],
                    "storage_type": "join",
                },
                "taskFieldSetting": {"key_fields": ["id", "system_id"]},
            },
        )
        self.redis_binding = observed(
            ref("RedisBinding", "iam_redis_binding"),
            {"data": self.binding["result_table"], "storage": self.binding["redis"]},
        )
        self.redis_binding["status"]["related"] = [observed(self.binding["redis"], {})]
        self.table = observed(
            self.binding["result_table"],
            {"predefiendResultTableId": "47_iam_actions"},
        )
        self.table.pop("kind")
        self.table["status"]["related"] = [self.redis_binding]
        self.remote.result_table_info.return_value = self.table
        self.meta = self.enterContext(mock.patch(f"{SYSTEM_PATH}.GlobalMetaConfig"))
        self.meta.get.side_effect = lambda key, **kw: deepcopy(self.row.config_value)
        self.meta.objects.select_for_update.return_value.get_or_create.return_value = (self.row, False)
        self.meta.objects.select_for_update.return_value.filter.return_value.first.return_value = self.row
        self.enterContext(mock.patch(f"{SYSTEM_PATH}.transaction.atomic", return_value=mock.MagicMock()))

    def test_migrated_binding_advances_after_source_ready_without_resource_writes(self):
        self.source["status"]["phase"] = "Pending"
        self.assertEqual(v4.ensure_system_snapshot("action", self.binding), "DataSource")
        self.assertEqual(self.row.config_value["config_name"], "legacy")
        with self.assertRaises(BKBaseResourceMappingError):
            v4.system_snapshot_table("action")
        self.remote.clean_get.assert_not_called()
        self.source["status"]["phase"] = "Ok"
        self.assertIsNone(v4.ensure_system_snapshot("action"))
        self.assertEqual(v4.system_snapshot_table("action"), ("47_iam_actions", ["id", "system_id"]))
        self.remote.result_table_info.assert_called_once_with(tenant="default", result_table_id="47_iam_actions")
        self.assertEqual(
            [call[0] for call in self.remote.mock_calls],
            ["data_source_get", "data_source_get", "clean_get", "result_table_info", "data_storage_get"],
        )
        self.remote.reset_mock()
        self.assertIsNone(v4.ensure_system_snapshot("action"))
        self.remote.result_table_info.assert_called_once()

    def test_missing_or_other_project_cannot_inherit_v3_readiness(self):
        self.assertEqual(v4.ensure_system_snapshot("action"), "migration binding")
        self.assertIsNone(v4.system_snapshot_table("user"))
        with self.assertRaises(BKBaseResourceMappingError):
            v4.system_snapshot_table("action")
        self.assertIsNone(v4.ensure_system_snapshot("action", self.binding))
        self.remote.reset_mock()
        with override_settings(BKBASE_V4_NAMESPACE="another"):
            self.assertEqual(v4.ensure_system_snapshot("action"), "migration binding")
            with self.assertRaises(BKBaseResourceMappingError):
                v4.ensure_system_snapshot("action", self.binding)
        self.assertEqual(self.remote.mock_calls, [])

    def test_rejects_conflicting_links_and_wrong_redis_schema(self):
        clean = self.remote.clean_get.return_value
        clean["spec"]["data_id"] = ref("DataId", "another")
        with self.assertRaises(BKBaseResourceMappingError):
            v4.ensure_system_snapshot("action", self.binding)
        self.remote.data_storage_get.assert_not_called()
        clean["spec"]["data_id"] = self.binding["data_id"]
        storage = self.remote.data_storage_get.return_value
        storage["spec"]["taskFieldSetting"]["key_fields"] = ["id"]
        with self.assertRaises(BKBaseResourceMappingError):
            v4.ensure_system_snapshot("action", self.binding)
        self.row.save.assert_not_called()
        self.meta.objects.select_for_update.return_value.get_or_create.assert_not_called()

    def test_wrong_snapshot_type_cannot_bind_a_different_system_chain(self):
        with self.assertRaisesMessage(BKBaseResourceMappingError, "snapshot_type=resource_type"):
            v4.ensure_system_snapshot("resource_type", self.binding)
        self.assertEqual(self.remote.mock_calls, [])

    def test_storage_ok_requires_exact_ready_redis_binding(self):
        for case in ("missing", "pending", "wrong_rt", "wrong_redis", "wrong_related", "redis_pending", "duplicate"):
            with self.subTest(case=case):
                row = deepcopy(self.redis_binding)
                related = [row]
                if case == "missing":
                    related = []
                elif case == "pending":
                    row["status"]["phase"] = "Pending"
                elif case == "wrong_rt":
                    row["spec"]["data"]["name"] = "another-table"
                elif case == "wrong_redis":
                    row["spec"]["storage"]["name"] = "another_redis"
                elif case == "wrong_related":
                    row["status"]["related"][0]["metadata"]["namespace"] = "another-project"
                elif case == "redis_pending":
                    row["status"]["related"][0]["status"]["phase"] = "Pending"
                else:
                    related.append({**row, "metadata": {**row["metadata"], "name": "duplicate"}})
                self.table["status"]["related"] = related
                self.assertEqual(v4.ensure_system_snapshot("action", self.binding), "RedisBinding")
                with self.assertRaises(BKBaseResourceMappingError):
                    v4.system_snapshot_table("action")

    def test_refresh_replaces_verified_key_order_and_revokes_deleted_or_stopped_join(self):
        self.assertIsNone(v4.ensure_system_snapshot("action", self.binding))
        storage = self.remote.data_storage_get.return_value
        storage["spec"]["taskFieldSetting"]["key_fields"].reverse()
        self.assertEqual(v4.system_snapshot_table("action"), ("47_iam_actions", ["id", "system_id"]))
        self.assertIsNone(v4.ensure_system_snapshot("action"))
        self.assertEqual(v4.system_snapshot_table("action"), ("47_iam_actions", ["system_id", "id"]))
        missing = APIRequestError(result={"message": "resource missing"})
        missing.http_status = 404
        self.remote.data_storage_get.side_effect = missing
        self.assertEqual(v4.ensure_system_snapshot("action"), "DataStorage")
        with self.assertRaises(BKBaseResourceMappingError):
            v4.system_snapshot_table("action")
        self.remote.data_storage_get.side_effect = None
        self.assertIsNone(v4.ensure_system_snapshot("action"))
        self.source["spec"]["current_status"] = "Stopped"
        with self.assertRaisesMessage(BKBaseResourceMappingError, "DataSource is stopped"):
            v4.ensure_system_snapshot("action")
        with self.assertRaises(BKBaseResourceMappingError):
            v4.system_snapshot_table("action")

    def test_transient_error_or_interruption_keeps_the_last_ready_join(self):
        self.assertIsNone(v4.ensure_system_snapshot("action", self.binding))
        unavailable = APIRequestError(result={"message": "unavailable"})
        unavailable.http_status = 503
        for failure in (unavailable, KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__):
                self.remote.data_source_get.side_effect = failure
                with self.assertRaises(type(failure)) as raised:
                    v4.ensure_system_snapshot("action")
                self.assertIs(raised.exception, failure)
                self.remote.reset_mock()
                self.assertEqual(v4.system_snapshot_table("action"), ("47_iam_actions", ["id", "system_id"]))
                self.assertEqual(self.remote.mock_calls, [])
        self.remote.data_source_get.side_effect = None
        self.assertIsNone(v4.ensure_system_snapshot("action"))

    def test_healthy_join_remains_readable_during_remote_verification(self):
        self.assertIsNone(v4.ensure_system_snapshot("action", self.binding))

        def while_verifying(**_):
            self.assertEqual(v4.system_snapshot_table("action"), ("47_iam_actions", ["id", "system_id"]))
            return self.source

        self.remote.data_source_get.side_effect = while_verifying
        self.assertIsNone(v4.ensure_system_snapshot("action"))

    def test_older_probe_cannot_publish_over_newer_unready_observation(self):
        self.assertIsNone(v4.ensure_system_snapshot("action", self.binding))

        def interleave(**_):
            self.remote.data_source_get.side_effect = None
            self.table["status"]["related"] = []
            self.assertEqual(v4.ensure_system_snapshot("action"), "RedisBinding")
            self.table["status"]["related"] = [self.redis_binding]
            return self.source

        self.remote.data_source_get.side_effect = interleave
        with self.assertRaisesMessage(BKBaseResourceMappingError, "observation was superseded"):
            v4.ensure_system_snapshot("action")
        with self.assertRaises(BKBaseResourceMappingError):
            v4.system_snapshot_table("action")

    def test_older_stopped_observation_applies_after_newer_probe_gets_503(self):
        self.assertIsNone(v4.ensure_system_snapshot("action", self.binding))
        unavailable = APIRequestError(result={"message": "unavailable"})
        unavailable.http_status = 503

        def interleave(**_):
            self.remote.data_source_get.side_effect = unavailable
            with self.assertRaises(APIRequestError):
                v4.ensure_system_snapshot("action")
            self.assertEqual(v4.system_snapshot_table("action"), ("47_iam_actions", ["id", "system_id"]))
            return {**self.source, "spec": {**self.source["spec"], "current_status": "Stopped"}}

        self.remote.data_source_get.side_effect = interleave
        with self.assertRaisesMessage(BKBaseResourceMappingError, "DataSource is stopped"):
            v4.ensure_system_snapshot("action")
        with self.assertRaises(BKBaseResourceMappingError):
            v4.system_snapshot_table("action")

    def test_older_observation_cannot_override_or_echo_newer_ready_join(self):
        self.assertIsNone(v4.ensure_system_snapshot("action", self.binding))

        for state in ("Stopped", "Running"):
            with self.subTest(state=state):
                older_source = {**self.source, "spec": {**self.source["spec"], "current_status": state}}

                def interleave(source=older_source, **_):
                    self.remote.data_source_get.side_effect = None
                    self.assertIsNone(v4.ensure_system_snapshot("action"))
                    return source

                self.remote.data_source_get.side_effect = interleave
                with self.assertRaisesMessage(BKBaseResourceMappingError, "observation was superseded"):
                    v4.ensure_system_snapshot("action")
                self.assertEqual(v4.system_snapshot_table("action"), ("47_iam_actions", ["id", "system_id"]))

    def test_concurrent_same_first_import_rechecks_pending_or_stopped_source(self):
        for phase, state in (("Pending", "Running"), ("Ok", "Stopped")):
            with self.subTest(phase=phase, state=state):
                self.row.config_value = {"config_name": "legacy"}
                self.remote.reset_mock()
                unready = {
                    **self.source,
                    "spec": {**self.source["spec"], "current_status": state},
                    "status": {"phase": phase},
                }
                self.remote.data_source_get.return_value = self.source

                def interleave(source=unready, **_):
                    self.remote.data_source_get.side_effect = None
                    self.assertIsNone(v4.ensure_system_snapshot("action", self.binding))
                    self.remote.data_source_get.return_value = source
                    return source

                self.remote.data_source_get.side_effect = interleave
                if state == "Stopped":
                    with self.assertRaisesMessage(BKBaseResourceMappingError, "DataSource is stopped"):
                        v4.ensure_system_snapshot("action", self.binding)
                else:
                    self.assertEqual(v4.ensure_system_snapshot("action", self.binding), "DataSource")
                self.assertEqual(self.remote.data_source_get.call_count, 3)
                with self.assertRaises(BKBaseResourceMappingError):
                    v4.system_snapshot_table("action")

    def test_concurrent_same_first_import_uses_fresh_observation_after_stale_stop(self):
        def interleave(**_):
            self.remote.data_source_get.side_effect = None
            self.assertIsNone(v4.ensure_system_snapshot("action", self.binding))
            return {**self.source, "spec": {**self.source["spec"], "current_status": "Stopped"}}

        self.remote.data_source_get.side_effect = interleave
        self.assertIsNone(v4.ensure_system_snapshot("action", self.binding))
        self.assertEqual(self.remote.data_source_get.call_count, 3)
        self.assertEqual(v4.system_snapshot_table("action"), ("47_iam_actions", ["id", "system_id"]))

    def test_concurrent_different_first_import_is_rejected_without_recheck(self):
        other = {**self.binding, "redis": ref("Redis", "another_redis", "cluster-project")}

        def interleave(**_):
            self.remote.data_source_get.side_effect = None
            self.assertIsNone(v4.ensure_system_snapshot("action", self.binding))
            return {**self.source, "status": {"phase": "Pending"}}

        self.remote.data_source_get.side_effect = interleave
        with self.assertRaisesMessage(BKBaseResourceMappingError, "different migration binding"):
            v4.ensure_system_snapshot("action", other)
        self.assertEqual(self.remote.data_source_get.call_count, 2)
        self.assertEqual(v4.system_snapshot_table("action"), ("47_iam_actions", ["id", "system_id"]))

    def test_old_ready_without_redis_binding_proof_requires_reverification(self):
        self.assertIsNone(v4.ensure_system_snapshot("action", self.binding))
        saved = self.row.config_value["bkbase_v4"]["default"]["audit"]
        saved.pop("redis_binding")
        self.remote.reset_mock()
        with self.assertRaises(BKBaseResourceMappingError):
            v4.system_snapshot_table("action")
        self.assertEqual(self.remote.mock_calls, [])
        self.assertIsNone(v4.ensure_system_snapshot("action"))
        self.assertEqual(v4.system_snapshot_table("action"), ("47_iam_actions", ["id", "system_id"]))

    def test_sdk_1558025_blocks_this_check_without_claiming_the_exact_join_is_gone(self):
        resource = ResultTableInfo()
        response = mock.Mock(status_code=200)
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "result": False,
            "code": "1558025",
            "message": "资源不存在.",
            "data": "Resource not found.",
        }

        def sdk_request(**params):
            return resource.request(params)

        self.remote.result_table_info.side_effect = sdk_request
        with (
            mock.patch.object(resource.session, "request", return_value=response) as transport,
            mock.patch.object(BkBaseV4Resource, "build_header", return_value={}),
            mock.patch.object(resource, "add_esb_info_before_request", side_effect=lambda data: data),
        ):
            with self.assertRaisesMessage(APIRequestError, "1558025") as raised:
                v4.ensure_system_snapshot("action", self.binding)
            transport.assert_called_once()
            self.assertEqual(raised.exception.data["code"], "1558025")
            self.assertFalse(getattr(raised.exception, "resource_not_found", False))
            self.remote.data_storage_get.assert_not_called()
            self.assertEqual(v4.ensure_system_snapshot("action"), "migration binding")
            with self.assertRaises(BKBaseResourceMappingError):
                v4.system_snapshot_table("action")

            def sdk_request_after_other_import(**params):
                self.remote.result_table_info.side_effect = None
                self.assertIsNone(v4.ensure_system_snapshot("action", self.binding))
                return sdk_request(**params)

            self.remote.result_table_info.side_effect = sdk_request_after_other_import
            with self.assertRaisesMessage(APIRequestError, "1558025"):
                v4.ensure_system_snapshot("action", self.binding)
            saved = self.row.config_value["bkbase_v4"]["default"]["audit"]
            self.assertNotIn("verification_started", saved)
            self.remote.result_table_info.side_effect = sdk_request
            with self.assertRaisesMessage(APIRequestError, "1558025"):
                v4.ensure_system_snapshot("action")
            self.assertEqual(v4.system_snapshot_table("action"), ("47_iam_actions", ["id", "system_id"]))

    @override_settings(BKBASE_API_VERSION="v3", SNAPSHOT_USERINFO_RESOURCE_URL="")
    def test_v3_etl_keeps_legacy_rt_and_key_order(self):
        self.meta.get.side_effect = ["47_legacy_resource", "47_legacy_action", "47_legacy_user"]
        handler = object.__new__(BkBaseConfig)
        handler.join_data_rt = None
        handler.build_config = mock.Mock(return_value={"join": []})
        joins = handler.trans_config({})["join"]
        self.assertEqual(
            [join["result_table_id"] for join in joins], ["47_legacy_resource", "47_legacy_action", "47_legacy_user"]
        )
        self.assertEqual([pair["target_field"] for pair in joins[0]["join_on"]], ["system_id", "id"])
        self.assertEqual(joins[2]["join_on"], [{"this_field": "username", "target_field": "id"}])

    def test_explicit_binding_cannot_replace_ready_chain_and_v3_save_keeps_it(self):
        self.assertIsNone(v4.ensure_system_snapshot("action", self.binding))
        current = deepcopy(self.row.config_value["bkbase_v4"])
        other = {**self.binding, "clean": ref("Clean", "another")}
        with self.assertRaises(BKBaseResourceMappingError):
            v4.ensure_system_snapshot("action", other)
        v4.save_v3_config(ACTION_DATA_CONFIG_KEY, {"config_name": "new_legacy"})
        self.assertEqual(self.row.config_value, {"config_name": "new_legacy", "bkbase_v4": current})

    def test_etl_joins_use_verified_logical_id_and_redis_order(self):
        handler = object.__new__(BkBaseConfig)
        handler.join_data_rt = None
        handler.build_config = mock.Mock(return_value={"join": []})
        with mock.patch(
            "services.web.databus.collector.etl.etl_config_handler.base.system_snapshot_table",
            side_effect=[("47_resource", ["id", "system_id"]), ("47_action", ["system_id", "id"]), None],
        ):
            result = handler.trans_config({})
        self.assertEqual([join["result_table_id"] for join in result["join"]], ["47_resource", "47_action"])
        self.assertEqual(
            result["join"][0]["join_on"],
            [
                {"this_field": "resource_type_id", "target_field": "id"},
                {"this_field": "system_id", "target_field": "system_id"},
            ],
        )


class SystemSnapshotEntrypointTests(SimpleTestCase):
    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_release_still_honors_legacy_complete_marker(self):
        with (
            mock.patch.object(SystemInitHandler, "pre_check", return_value=True) as precheck,
            mock.patch(f"{ENTRY_PATH}.create_iam_data_link") as create,
        ):
            SystemInitHandler().init_snapshot()
        precheck.assert_called_once()
        create.assert_not_called()

    @override_settings(BKBASE_API_VERSION="v4", SNAPSHOT_USERINFO_RESOURCE_URL="configured")
    def test_v4_release_ignores_old_marker_and_continues_other_kinds(self):
        handler = SystemInitHandler()
        with (
            mock.patch.object(SystemInitHandler, "pre_check", return_value=True) as precheck,
            mock.patch.object(SystemInitHandler, "post_init") as post_init,
            mock.patch(f"{ENTRY_PATH}.create_iam_data_link", side_effect=["Clean", None, None]) as create,
        ):
            self.assertIs(handler.init_snapshot(), False)
        precheck.assert_not_called()
        post_init.assert_not_called()
        self.assertEqual(
            create.call_args_list,
            [
                mock.call(kind, init_redis_fallback=handler._resolve_snapshot_redis)
                for kind in ("action", "resource_type", "user")
            ],
        )

    @override_settings(BKBASE_API_VERSION="v4")
    def test_manual_command_propagates_pending_to_exit_status(self):
        with mock.patch(f"{COMMAND_PATH}.create_iam_data_link", return_value="DataStorage") as create:
            with self.assertRaisesMessage(CommandError, "DataStorage"):
                call_command("iam_data_pull", "-t", "action")
        create.assert_called_once_with("action")

    @override_settings(BKBASE_API_VERSION="v4")
    def test_manual_command_accepts_an_explicit_binding_for_optional_user(self):
        with TemporaryDirectory() as temp, mock.patch(
            f"{COMMAND_PATH}.create_iam_data_link", return_value=None
        ) as create:
            binding_file = Path(temp) / "user.json"
            binding = {"result_table_id": "47_iam_users"}
            binding_file.write_text(json.dumps(binding), encoding="utf-8")
            call_command("iam_data_pull", "-t", "user", "--v4-binding-file", str(binding_file))
        create.assert_called_once_with("user", migration_binding=binding)

    @override_settings(BKBASE_API_VERSION="v4")
    def test_release_command_propagates_pending_without_advancing(self):
        initializers = ("pre_init", "init_standard_fields", "init_es", "init_doris", "init_redis")
        self.enterContext(mock.patch.multiple(SystemInitHandler, **dict.fromkeys(initializers, mock.DEFAULT)))
        self.enterContext(mock.patch.object(SystemInitHandler, "init_snapshot", return_value=False))
        with mock.patch.object(SystemInitHandler, "init_event") as later:
            with self.assertRaisesMessage(CommandError, "禁止发布"):
                call_command("init_system")
        later.assert_not_called()
