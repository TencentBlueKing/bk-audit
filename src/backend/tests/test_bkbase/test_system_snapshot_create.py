"""验证系统快照的新建声明和分阶段续跑。"""
import json
from contextlib import contextmanager
from copy import deepcopy
from unittest import mock

from bk_resource.exceptions import APIRequestError
from django.test import SimpleTestCase, override_settings

from services.web.bkbase import source
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.collector.snapshot.system import provision, pull
from services.web.databus.collector.snapshot.system import v4 as bindings


class SystemPullDeclarationTests(SimpleTestCase):
    def test_report_preserves_legacy_window_and_pagination_without_delay(self):
        params = {
            "access_conf_info": {
                "collection_model": {"period": 1},
                "resource": {
                    "scope": [
                        {
                            "method": "post",
                            "url": "https://iam.example.test/api/v1/resources/",
                            "body": {
                                "content": json.dumps(
                                    {
                                        "filter": {"start_time": "<start>", "end_time": "<end>"},
                                        "page": {"offset": "<offset>", "limit": "<limit>"},
                                    }
                                ),
                                "time": {"format": "Unix Time Stamp(milliseconds)", "delay": {"value": 1}},
                                "page": {"start_offset": 0, "limit": 100, "total_path": ".data.count"},
                            },
                        }
                    ],
                },
            },
        }
        report = source.build_pull_report_config(params, "iam_conn", "https://iam.example.test")
        self.assertEqual(report["body"], params["access_conf_info"]["resource"]["scope"][0]["body"]["content"])
        self.assertEqual(report["path"], "/api/v1/resources/")
        self.assertEqual(report["increment_field"], {"type": "time", "time_format": "Unix Time Stamp(milliseconds)"})
        self.assertEqual(report["pagination"], {"start_offset": 0, "limit": 100, "total_path": ".data.count"})
        self.assertIsNone(report["history_data"])
        self.assertIsNone(report["data_path"])
        self.assertNotIn("delay", report)
        with mock.patch.object(
            source.System.objects, "get", return_value=mock.Mock(callback_url="https://iam.example.test")
        ):
            self.assertEqual(
                source._provision_report_config(mock.Mock(system_id="fixture"), params, "iam_conn"), report
            )
        for path in (None, ".data.results"):
            observed = deepcopy(report)
            observed["data_path"] = path
            original = deepcopy(observed)
            with mock.patch.object(source, "_provision_report_config", return_value=deepcopy(report)):
                source.validate_source_provision_report(None, params, "iam_conn", observed)
            self.assertEqual(observed, original)
        with mock.patch.object(source, "_provision_report_config", return_value=deepcopy(report)):
            for unknown in ({}, {"data_path": ".custom"}):
                with self.assertRaises(BKBaseResourceMappingError):
                    source.validate_source_provision_report(None, params, "iam_conn", unknown)
        initial = deepcopy(report)
        source._set_pull_replay_history(initial)
        self.assertEqual(initial["history_data"], {"start_time": "0"})


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="default",
    BKBASE_V4_NAMESPACE="audit",
    APP_CODE="audit_fixture",
    DEFAULT_BK_BIZ_ID=47,
    FETCH_INSTANCE_USERNAME="fixture",
    SNAPSHOT_USERINFO_RESOURCE_URL="https://users.example.test/api/users/",
    BKBASE_V4_SYSTEM_SNAPSHOT_CREATE={
        kind: {"redis": {"kind": "Redis", "tenant": "default", "namespace": "clusters", "name": "iam_redis"}}
        for kind in ("action", "resource_type", "user")
    },
)
class SystemSnapshotCreationTests(SimpleTestCase):
    def setUp(self):
        self.rows = {}
        self.resources = {}
        self.in_transaction = False
        self.posts = []
        self.updates = []
        self.meta = mock.Mock()
        self.meta.get.side_effect = (
            lambda key, **kw: deepcopy(self.rows[key].config_value) if key in self.rows else kw.get("default")
        )
        self.meta.objects.select_for_update.return_value.get_or_create.side_effect = self._row
        self.meta.objects.select_for_update.return_value.filter.side_effect = lambda **keys: mock.Mock(
            first=lambda: self.rows.get(keys["config_key"])
        )
        self.enterContext(mock.patch.object(bindings, "GlobalMetaConfig", new=self.meta))
        self.enterContext(mock.patch.object(bindings.transaction, "atomic", side_effect=self._atomic))
        token = mock.Mock()
        token.get.return_value = "fixture_token"
        token.objects.get_or_create.return_value = (mock.Mock(config_value="fixture_token"), False)
        self.enterContext(mock.patch("services.web.databus.collector.snapshot.system.pull.GlobalMetaConfig", new=token))
        self.enterContext(
            mock.patch(
                "services.web.databus.collector.snapshot.system.pull.get_saas_url",
                return_value="https://iam.example.test",
            )
        )
        self.sdk = mock.Mock()
        api = mock.Mock(bk_base_v4=self.sdk)
        self.enterContext(mock.patch.object(provision, "api", new=api))
        self.enterContext(mock.patch.object(bindings, "api", new=api))
        for name, kind in (
            ("data_conn", "DataConn"),
            ("data_source", "DataSource"),
            ("clean", "Clean"),
            ("data_storage", "DataStorage"),
        ):
            getattr(self.sdk, name + "_get").side_effect = self._getter(kind)
            getattr(self.sdk, name + "_create").side_effect = self._creator(kind)
        self.sdk.data_source_update.side_effect = self._update_source
        self.sdk.result_table_info.side_effect = self._table

    def _row(self, **keys):
        key = keys["config_key"]
        created = key not in self.rows
        self.rows.setdefault(key, mock.Mock(config_value=None))
        return self.rows[key], created

    @contextmanager
    def _atomic(self):
        self.assertFalse(self.in_transaction)
        self.in_transaction = True
        try:
            yield
        finally:
            self.in_transaction = False

    def _getter(self, kind):
        def get(**kwargs):
            self.assertFalse(self.in_transaction)
            resource = self.resources.get((kind, kwargs["name"]))
            if resource is None:
                error = APIRequestError(result={"message": "missing"})
                error.http_status = 404
                raise error
            return deepcopy(resource)

        return get

    def _creator(self, kind):
        def create(**kwargs):
            self.assertFalse(self.in_transaction)
            self.assertIsNone(kwargs["status"])
            resource = {
                "kind": kind,
                "metadata": deepcopy(kwargs["metadata"]),
                "spec": deepcopy(kwargs["spec"]),
                "status": {"phase": "Pending"},
            }
            self.posts.append((kind, deepcopy(kwargs)))
            if kind == "DataConn":
                resource["metadata"].setdefault("annotations", {})["conn_info_encrypted"] = "true"
                resource["spec"]["conn_info"]["headers"]["Authorization"] = "encrypted_fixture"
            if kind == "DataSource":
                resource["metadata"].setdefault("labels", {})["raw_data_id"] = "73"
                resource["spec"]["data_id"] = {
                    "kind": "DataId",
                    "tenant": "default",
                    "namespace": "audit",
                    "name": "actual_dataid_" + kwargs["metadata"]["name"],
                }
            self.resources[(kind, kwargs["metadata"]["name"])] = resource
            return deepcopy(resource)

        return create

    def _update_source(self, **kwargs):
        self.assertFalse(self.in_transaction)
        resource = self.resources[("DataSource", kwargs["name"])]
        self.updates.append(deepcopy(kwargs))
        resource.update(
            metadata=deepcopy(kwargs["metadata"]), spec=deepcopy(kwargs["spec"]), status={"phase": "Pending"}
        )
        return deepcopy(resource)

    def _table(self, *, tenant, result_table_id):
        self.assertFalse(self.in_transaction)
        clean = next(
            (
                value
                for (kind, _), value in self.resources.items()
                if kind == "Clean" and value["spec"]["result_table_id"] == result_table_id
            ),
            None,
        )
        if clean is None:
            raise APIRequestError(result={"code": "1558025", "message": "missing"})
        table = {
            "kind": "ResultTable",
            "tenant": tenant,
            "namespace": "audit",
            "name": "actual-cr-" + clean["metadata"]["name"],
        }
        related = []
        for (kind, _), storage in self.resources.items():
            if kind != "DataStorage" or storage["spec"]["tableInfo"]["source"] != table:
                continue
            redis = storage["spec"]["tableInfo"]["storage"]
            related.append(
                {
                    "kind": "RedisBinding",
                    "metadata": {
                        "tenant": tenant,
                        "namespace": "audit",
                        "name": "binding-" + storage["metadata"]["name"],
                    },
                    "spec": {"data": table, "storage": redis},
                    "status": {
                        "phase": storage["status"]["phase"],
                        "related": [
                            {
                                "kind": "Redis",
                                "metadata": {key: redis[key] for key in ("tenant", "namespace", "name")},
                                "spec": {},
                                "status": {"phase": "Ok"},
                            }
                        ],
                    },
                }
            )
        return {
            "metadata": {key: table[key] for key in ("tenant", "namespace", "name")},
            "spec": {"predefiendResultTableId": result_table_id},
            "status": {"phase": "Ok", "related": related},
        }

    def _settle(self):
        for (kind, _), resource in self.resources.items():
            resource["status"]["phase"] = "Ok"
            if kind in ("DataSource", "Clean"):
                resource["spec"]["current_status"] = resource["spec"]["desired_status"]

    def _complete(self, kind):
        for _ in range(15):
            pending = provision.ensure_system_snapshot(kind)
            self._settle()
            if pending is None:
                return
        self.fail("system snapshot did not complete")

    def test_three_schemas_create_once_and_use_formal_refs_and_binding(self):
        for kind in ("action", "resource_type", "user"):
            with self.subTest(kind=kind):
                config_key = bindings.SYSTEM_SNAPSHOT_KEYS[kind][0]
                self.rows[config_key] = mock.Mock(config_value={"config_name": "legacy_" + kind, "bkbase_data_id": 12})
                before = len(self.posts)
                self._complete(kind)
                self.assertEqual(
                    [kind for kind, _ in self.posts[before:]], ["DataConn", "DataSource", "Clean", "DataStorage"]
                )
                [created_source] = [
                    v
                    for (resource_kind, _), v in self.resources.items()
                    if resource_kind == "DataSource" and v["metadata"]["name"].startswith("audit_iam_" + kind + "_")
                ]
                self.assertIsNone(created_source["spec"]["report_config"]["data_path"])
                logical_id, keys = bindings.system_snapshot_table(kind)
                self.assertEqual(set(keys), {"id"} if kind == "user" else {"id", "system_id"})
                source_request = self.posts[before + 1][1]["spec"]
                self.assertEqual(source_request["desired_status"], "Stopped")
                self.assertEqual(source_request["report_config"]["history_data"], {"start_time": "0"})
                self.assertNotIn("delay", source_request["report_config"])
                clean = self.posts[before + 2][1]["spec"]
                self.assertEqual(clean["result_table_id"], logical_id)
                self.assertEqual(clean["result_table_source"], "new")
                self.assertEqual(
                    self.posts[before + 3][1]["spec"]["tableInfo"]["source"]["name"],
                    "actual-cr-" + self.posts[before + 2][1]["metadata"]["name"],
                )
                self.assertIsNone(provision.ensure_system_snapshot(kind))
                self.assertEqual(len(self.posts), before + 4)
                self.assertEqual(self.rows[config_key].config_value["config_name"], "legacy_" + kind)
                self.assertEqual(self.rows[config_key].config_value["bkbase_data_id"], 12)
        self.assertEqual(len(self.updates), 3)
        saved = json.dumps({key: row.config_value for key, row in self.rows.items()})
        self.assertNotIn("fixture_token", saved)
        self.assertNotIn("encrypted_fixture", saved)

    def test_old_list_plan_resumes_without_changing_source_or_clean_shape(self):
        kind = "action"
        config_key = bindings.SYSTEM_SNAPSHOT_KEYS[kind][0]
        redis = provision._create_config(kind, bindings._system_context())
        record = provision._new_record(kind, bindings._system_context(), redis)
        operation = record["creation"]
        params = provision._params(kind, operation)
        operation["input_digest"] = provision._input_digest(
            kind, params, redis, report_config={"data_path": ".data.results"}
        )
        self.rows[config_key] = mock.Mock(config_value={"bkbase_v4": {"default": {"audit": record}}})
        self._complete(kind)
        [source_value] = [
            value for (resource_kind, _), value in self.resources.items() if resource_kind == "DataSource"
        ]
        [clean_value] = [value for (resource_kind, _), value in self.resources.items() if resource_kind == "Clean"]
        self.assertEqual(source_value["spec"]["report_config"]["data_path"], ".data.results")
        self.assertEqual(len([r for r in clean_value["spec"]["rules"] if r["operator"]["type"] == "json_de"]), 1)
        self.assertEqual([kind for kind, _ in self.posts], ["DataConn", "DataSource", "Clean", "DataStorage"])

    def test_unknown_post_is_only_observed_and_never_repeated(self):
        create = self._creator("DataConn")

        def unknown(**kwargs):
            create(**kwargs)
            raise APIRequestError(result={"message": "receipt unavailable"})

        self.sdk.data_conn_create.side_effect = unknown
        with self.assertRaises(APIRequestError):
            provision.ensure_system_snapshot("action")
        self.assertEqual(len(self.posts), 1)
        self._settle()
        self._complete("action")
        self.assertEqual([kind for kind, _ in self.posts].count("DataConn"), 1)

    def test_existing_unclaimed_source_is_never_adopted(self):
        provision.ensure_system_snapshot("action")
        self._settle()
        key = bindings.SYSTEM_SNAPSHOT_KEYS["action"][0]
        record = self.rows[key].config_value["bkbase_v4"]["default"]["audit"]
        ref = record["creation"]["refs"]["data_source"]
        self.resources[("DataSource", ref["name"])] = {
            "kind": "DataSource",
            "metadata": {k: ref[k] for k in ("tenant", "namespace", "name")},
            "spec": {},
            "status": {"phase": "Ok"},
        }
        with self.assertRaisesMessage(BKBaseResourceMappingError, "exists without this creation claim"):
            provision.ensure_system_snapshot("action")
        self.assertEqual(len(self.posts), 1)

    def test_missing_binding_keeps_source_stopped_until_formal_binding_is_ready(self):
        table = self._table

        def without_binding(**kwargs):
            result = table(**kwargs)
            result["status"]["related"] = []
            return result

        self.sdk.result_table_info.side_effect = without_binding
        for _ in range(9):
            pending = provision.ensure_system_snapshot("action")
            self._settle()
        self.assertEqual(pending, "RedisBinding")
        self.assertEqual(len(self.posts), 4)
        self.assertEqual(self.updates, [])
        self.assertEqual(
            next(value for (kind, _), value in self.resources.items() if kind == "DataSource")["spec"][
                "current_status"
            ],
            "Stopped",
        )
        self.sdk.result_table_info.side_effect = table
        self._complete("action")
        self.assertEqual(len(self.updates), 1)

    def test_unknown_missing_post_outcome_does_not_retry_create(self):
        self.sdk.data_conn_create.side_effect = APIRequestError(result={"message": "unknown outcome"})
        with self.assertRaises(APIRequestError):
            provision.ensure_system_snapshot("action")
        for _ in range(3):
            self.assertEqual(provision.ensure_system_snapshot("action"), "DataConn")
        self.sdk.data_conn_create.assert_called_once()

    def test_concurrent_reentry_during_post_observes_the_persisted_claim(self):
        create = self._creator("DataConn")

        def concurrent(**kwargs):
            self.assertEqual(provision.ensure_system_snapshot("action"), "DataConn")
            return create(**kwargs)

        self.sdk.data_conn_create.side_effect = concurrent
        self.assertEqual(provision.ensure_system_snapshot("action"), "DataConn")
        self.sdk.data_conn_create.assert_called_once()
        self._settle()
        self._complete("action")

    def test_activation_unknown_receipt_is_observed_without_a_second_put(self):
        update = self._update_source

        def unknown(**kwargs):
            update(**kwargs)
            raise APIRequestError(result={"message": "unknown activation"})

        self.sdk.data_source_update.side_effect = unknown
        for _ in range(12):
            try:
                provision.ensure_system_snapshot("action")
            except APIRequestError:
                break
            self._settle()
        else:
            self.fail("activation was not reached")
        self.assertEqual(len(self.updates), 1)
        self._settle()
        self._complete("action")
        self.assertEqual(len(self.updates), 1)

    def test_v4_callback_token_reuses_atomic_record_and_v3_keeps_legacy_path(self):
        token = pull.GlobalMetaConfig
        token.reset_mock()
        pull.HttpPullHandler("action")
        pull.HttpPullHandler("resource_type")
        self.assertEqual(token.objects.get_or_create.call_count, 2)
        token.set.assert_not_called()
        token.get.assert_not_called()
        with override_settings(BKBASE_API_VERSION="v3"):
            pull.HttpPullHandler("action")
        token.get.assert_called_once()
        token.set.assert_called_once()

    @override_settings(BKPAAS_MULTI_TENANT_MODE=True, BK_TENANT_ID="tencent")
    def test_multitenant_data_conn_registers_internal_callback_tenant_header(self):
        self.assertEqual(provision.ensure_system_snapshot("action"), "DataConn")
        kind, registration = self.posts[0]
        self.assertEqual(kind, "DataConn")
        headers = registration["spec"]["conn_info"]["headers"]
        self.assertEqual(headers["X-Bk-Tenant-Id"], "tencent")
        self.assertTrue(headers["Authorization"].startswith("Basic "))

    def test_callback_tenant_header_is_not_sent_to_external_provider_or_in_single_tenant(self):
        for multi_tenant, kind in ((True, "user"), (False, "resource_type")):
            with (
                self.subTest(multi_tenant=multi_tenant, kind=kind),
                override_settings(BKPAAS_MULTI_TENANT_MODE=multi_tenant, BK_TENANT_ID="system"),
            ):
                params = pull.HttpPullHandler(kind).build_params()
                headers = params["access_conf_info"]["resource"]["scope"][0]["headers"]
                self.assertNotIn("X-Bk-Tenant-Id", headers)

    def test_unowned_existing_name_and_changed_inputs_do_not_write(self):
        provision.ensure_system_snapshot("action")
        self._settle()
        with override_settings(DEFAULT_BK_BIZ_ID=99):
            with self.assertRaises(BKBaseResourceMappingError):
                provision.ensure_system_snapshot("action")
        self.assertEqual(len(self.posts), 1)
        other_redis = {"kind": "Redis", "tenant": "default", "namespace": "clusters", "name": "other"}
        with override_settings(BKBASE_V4_SYSTEM_SNAPSHOT_CREATE={"action": {"redis": other_redis}}):
            with self.assertRaises(BKBaseResourceMappingError):
                provision.ensure_system_snapshot("action")
        self.assertEqual(len(self.posts), 1)

    def test_migration_input_rejected_during_creation_and_no_implicit_create(self):
        with override_settings(BKBASE_V4_SYSTEM_SNAPSHOT_CREATE={}):
            self.assertEqual(provision.ensure_system_snapshot("action"), "migration binding")
        self.assertEqual(self.posts, [])
        provision.ensure_system_snapshot("action")
        with self.assertRaises(BKBaseResourceMappingError):
            provision.ensure_system_snapshot("action", migration_binding={"snapshot_type": "action"})
        self.assertEqual(len(self.posts), 1)
