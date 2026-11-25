"""验证系统快照的新建声明和分阶段续跑。"""
import json
from contextlib import contextmanager
from copy import deepcopy
from unittest import mock
from uuid import UUID

import requests
from bk_resource.exceptions import APIRequestError
from django.test import SimpleTestCase, override_settings

from api.bk_base_v4.default import DataConnCreate, DataConnGet, DataSourceUpdate
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
                error = APIRequestError(result={"result": False, "code": "1558025", "data": "Resource not found."})
                error.http_status = 200
                error.resource_not_found = True
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
                    "tenant": kwargs["metadata"]["tenant"],
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

    def test_gateway_404_cannot_start_snapshot_create(self):
        self._assert_lookup_failure_blocks_create(404, {"code": 1640401, "message": "route missing"})

    def test_permission_failures_cannot_start_snapshot_create(self):
        for status in (401, 403):
            with self.subTest(status=status):
                self._assert_lookup_failure_blocks_create(status, {"message": "denied"})

    def test_timeout_cannot_start_snapshot_create(self):
        self._assert_lookup_failure_blocks_create(None, requests.Timeout("synthetic timeout"))

    def test_redirect_cannot_start_snapshot_create(self):
        for status in (301, 302, 307, 308):
            with self.subTest(status=status):
                self._assert_lookup_failure_blocks_create(
                    status, {"result": False, "code": "1558025", "data": "Resource not found."}
                )

    def _assert_lookup_failure_blocks_create(self, status, payload):
        """保留真实 SDK 与编排链，只模拟第三方 HTTP。"""
        resource = DataConnGet()
        self.sdk.data_conn_get.side_effect = resource.request
        response = requests.Response()
        response.status_code = status
        response._content = json.dumps(payload).encode() if status is not None else b""
        response.url = "https://gateway.synthetic.test/resource"
        response.request = requests.Request("GET", response.url).prepare()
        with mock.patch.object(resource, "build_header", return_value={}), mock.patch.object(
            requests.sessions.Session, "request", **({"return_value": response} if status else {"side_effect": payload})
        ), self.assertRaises(APIRequestError):
            provision.ensure_system_snapshot("action")
        self.assertEqual(self.posts, [])

    def test_new_resource_type_resource_names_fit_bkbase_limit(self):
        first_id = UUID("0123456789abcdef0123456789abcdef")
        second_id = UUID("1123456789abcdef0123456789abcdef")
        with mock.patch.object(provision, "uuid") as uuid_source:
            uuid_source.uuid4.side_effect = [first_id, second_id]
            self._complete("resource_type")
            record = self.rows["bkaudit_resource_type_config_data"].config_value["bkbase_v4"]["default"]["audit"]
            fresh = provision._new_record("resource_type", bindings._system_context(), record["redis"])["creation"]

        creation = record["creation"]
        self.assertEqual(creation["operation_id"], first_id.hex)
        self.assertEqual(fresh["operation_id"], second_id.hex)
        stem = "iam_rtype_0123456789abcdef0123456789abcdef"
        resources = (
            ("connection", "DataConn", "_conn", 47),
            ("data_source", "DataSource", "_source", 49),
            ("clean", "Clean", "_clean", 48),
            ("storage", "DataStorage", "_redis", 48),
        )
        for (observed_kind, post), (key, kind, suffix, size) in zip(self.posts, resources, strict=True):
            with self.subTest(kind=kind):
                self.assertEqual(observed_kind, kind)
                self.assertEqual(len(post["metadata"]["name"]), size)
                ref = {"kind": kind, "tenant": "default", "namespace": "audit", "name": stem + suffix}
                self.assertEqual(creation["refs"][key], ref)
                self.assertEqual(post["metadata"]["name"], ref["name"])
                self.assertEqual(post["metadata"]["annotations"]["bkaudit_iam_operation"], first_id.hex)
                self.assertNotEqual(fresh["refs"][key]["name"], ref["name"])
        self.assertEqual(bindings.system_snapshot_table("resource_type"), ("47_" + stem, ["id", "system_id"]))
        self.assertEqual(self.posts[2][1]["spec"]["result_table_id"], "47_" + stem)

    def test_long_snapshot_kind_shares_bounded_stem(self):
        kind = "kind/with:*illegal" * 8
        operation_id = UUID("0123456789abcdef0123456789abcdef")
        context = bindings._system_context()
        redis = {"kind": "Redis", "tenant": "default", "namespace": "clusters", "name": "iam_redis"}
        with mock.patch.object(provision.uuid, "uuid4", return_value=operation_id), mock.patch.object(
            provision, "_params", return_value={}
        ), mock.patch.object(provision, "_input_digest", return_value="synthetic-digest"):
            creation = provision._new_record(kind, context, redis)["creation"]

        self.assertEqual(creation["operation_id"], operation_id.hex)
        self.assertTrue(creation["name"].endswith("_" + operation_id.hex))
        self.assertEqual(creation["logical_id"], "47_" + creation["name"])
        suffixes = {
            "connection": "_conn",
            "data_source": "_source",
            "clean": "_clean",
            "storage": "_redis",
        }
        for key, suffix in suffixes.items():
            name = creation["refs"][key]["name"]
            with self.subTest(key=key):
                self.assertRegex(name, r"^[_A-Za-z0-9][_A-Za-z0-9-]*$")
                self.assertLessEqual(len(name), 50)
                self.assertTrue(name.endswith(suffix))
                self.assertEqual(name[: -len(suffix)], creation["name"])
        self.assertEqual(len(creation["refs"]["data_source"]["name"]), 50)

    def test_pending_long_resource_type_claim_keeps_original_ref_without_repost(self):
        operation_id = "0123456789abcdef0123456789abcdef"
        name = "audit_iam_resource_type_" + operation_id
        context = bindings._system_context()
        redis = {"kind": "Redis", "tenant": "default", "namespace": "clusters", "name": "iam_redis"}
        refs = {
            key: {"kind": kind, "tenant": "default", "namespace": "audit", "name": name + suffix}
            for key, kind, suffix in (
                ("connection", "DataConn", "_conn"),
                ("data_source", "DataSource", "_source"),
                ("clean", "Clean", "_clean"),
                ("storage", "DataStorage", "_redis"),
            )
        }
        operation = {
            "operation_id": operation_id,
            "name": name,
            "logical_id": "47_" + name,
            "revision": 1234,
            "redis": redis,
            "refs": refs,
        }
        params = provision._params("resource_type", operation)
        operation["input_digest"] = provision._input_digest("resource_type", params, redis)
        connection, _ = provision._source_spec(params, operation)
        operation["steps"] = {
            "connection": {"target_digest": source._replay_digest(connection), "attempt": 1, "not_dispatched": False}
        }
        original = {
            "config_name": "legacy_resource_type",
            "bkbase_v4": {
                context["tenant"]: {
                    context["namespace"]: {"snapshot_type": "resource_type", "creation": operation, "ready": False},
                    "other_project": {"ready": True},
                }
            },
        }
        row = mock.Mock(config_value=deepcopy(original))
        self.rows["bkaudit_resource_type_config_data"] = row

        self.assertEqual(provision.ensure_system_snapshot("resource_type"), "DataConn")

        self.sdk.data_conn_get.assert_called_once_with(tenant="default", namespace="audit", name=name + "_conn")
        self.assertEqual(self.posts, [])
        self.assertEqual(row.config_value, original)

    def test_three_schemas_create_once_and_use_formal_refs_and_binding(self):
        operation_id = "0123456789abcdef0123456789abcdef"
        expected_lengths = {
            "action": (48, 50, 49, 49),
            "resource_type": (47, 49, 48, 48),
            "user": (46, 48, 47, 47),
        }
        for kind in ("action", "resource_type", "user"):
            with self.subTest(kind=kind):
                config_key = bindings.SYSTEM_SNAPSHOT_KEYS[kind][0]
                self.rows[config_key] = mock.Mock(config_value={"config_name": "legacy_" + kind, "bkbase_data_id": 12})
                before = len(self.posts)
                with mock.patch.object(provision.uuid, "uuid4", return_value=UUID(operation_id)):
                    self._complete(kind)
                self.assertEqual(
                    [kind for kind, _ in self.posts[before:]], ["DataConn", "DataSource", "Clean", "DataStorage"]
                )
                record = self.rows[config_key].config_value["bkbase_v4"]["default"]["audit"]
                name_kind = "rtype" if kind == "resource_type" else kind
                stem = f"iam_{name_kind}_{operation_id}"
                self.assertEqual(record["creation"]["operation_id"], operation_id)
                for (key, resource_kind, suffix), expected_length, (posted_kind, post) in zip(
                    (
                        ("connection", "DataConn", "_conn"),
                        ("data_source", "DataSource", "_source"),
                        ("clean", "Clean", "_clean"),
                        ("storage", "DataStorage", "_redis"),
                    ),
                    expected_lengths[kind],
                    self.posts[before : before + 4],
                    strict=True,
                ):
                    expected_name = stem + suffix
                    with self.subTest(resource_kind=resource_kind):
                        self.assertEqual(posted_kind, resource_kind)
                        self.assertEqual(record["creation"]["refs"][key]["name"], expected_name)
                        self.assertEqual(post["metadata"]["name"], expected_name)
                        self.assertEqual(len(expected_name), expected_length)
                source_name = record["creation"]["refs"]["data_source"]["name"]
                created_source = self.resources[("DataSource", source_name)]
                self.assertIsNone(created_source["spec"]["report_config"]["data_path"])
                logical_id, keys = bindings.system_snapshot_table(kind)
                self.assertEqual(logical_id, "47_" + stem)
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

    def test_action_snapshot_resumes_when_data_source_spec_readback_differs(self):
        self.assertEqual(provision.ensure_system_snapshot("action"), "DataConn")
        self._settle()
        self.assertEqual(provision.ensure_system_snapshot("action"), "DataSource")
        row = self.rows["bkaudit_action_config_data"]
        ref = deepcopy(row.config_value["bkbase_v4"]["default"]["audit"]["creation"]["refs"]["data_source"])
        observed = self.resources[("DataSource", ref["name"])]["spec"]
        observed["basic_info"].update(access_channel="bkbase", access_channel_alias="计算平台", data_source_alias="平台展示名")
        observed["data_conn"].pop("tenant")
        observed["report_config"]["method"] = "POST"
        observed["report_config"]["pagination"]["platform_default"] = True
        self._settle()

        self._complete("action")

        record = row.config_value["bkbase_v4"]["default"]["audit"]
        self.assertTrue(record["ready"])
        self.assertEqual(record["creation"]["refs"]["data_source"], ref)
        self.assertEqual([kind for kind, _ in self.posts], ["DataConn", "DataSource", "Clean", "DataStorage"])

    def test_action_snapshot_does_not_resume_when_data_source_identity_changes(self):
        self.assertEqual(provision.ensure_system_snapshot("action"), "DataConn")
        self._settle()
        self.assertEqual(provision.ensure_system_snapshot("action"), "DataSource")
        self._settle()
        row = self.rows["bkaudit_action_config_data"]
        original_record = deepcopy(row.config_value)
        ref = original_record["bkbase_v4"]["default"]["audit"]["creation"]["refs"]["data_source"]
        source_value = self.resources[("DataSource", ref["name"])]
        for scope, updates in (
            (source_value, {"kind": "DataConn"}),
            (source_value["metadata"], {"name": "wrong_source"}),
            (source_value["metadata"], {"tenant": "other_tenant"}),
            (source_value["metadata"], {"namespace": "other_project"}),
        ):
            with self.subTest(updates=updates), mock.patch.dict(scope, updates):
                with self.assertRaises(BKBaseResourceMappingError):
                    provision.ensure_system_snapshot("action")

                self.assertEqual(row.config_value, original_record)
                self.assertEqual([kind for kind, _ in self.posts], ["DataConn", "DataSource"])
                self.assertEqual(self.updates, [])

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

    def test_pre_dispatch_rejection_reuses_same_snapshot_ref(self):
        resource = DataConnCreate()
        self.sdk.data_conn_create.side_effect = resource.request
        sent = []

        def transport(**kwargs):
            self.assertFalse(self.in_transaction)
            sent.append(deepcopy(kwargs["json"]))
            response = requests.Response()
            response.url = kwargs["url"]
            response.request = requests.Request("POST", response.url).prepare()
            if len(sent) == 1:
                response.status_code = 404
                payload = {"code": 1640401, "message": "synthetic route rejection"}
            else:
                response.status_code = 200
                payload = {"result": True, "code": "00", "data": self._creator("DataConn")(**kwargs["json"])}
            response._content = json.dumps(payload).encode()
            return response

        with mock.patch.object(resource, "build_header", return_value={}), mock.patch.object(
            requests.sessions.Session, "request", side_effect=transport
        ):
            with self.assertRaises(APIRequestError) as caught:
                provision.ensure_system_snapshot("action")
            self.assertEqual(caught.exception.gateway_error_code, "1640401")
            self.assertEqual(len(sent), 1)
            key = bindings.SYSTEM_SNAPSHOT_KEYS["action"][0]
            first = deepcopy(self.rows[key].config_value["bkbase_v4"]["default"]["audit"])
            self.assertEqual(first["creation"]["steps"]["connection"]["attempt"], 1)
            self.assertIs(first["creation"]["steps"]["connection"]["not_dispatched"], True)
            self.assertEqual(provision.ensure_system_snapshot("action"), "DataConn")
            self.assertEqual(len(sent), 2)
            second = self.rows[key].config_value["bkbase_v4"]["default"]["audit"]
            self.assertEqual(second["creation"]["steps"]["connection"]["attempt"], 2)
            self.assertIs(second["creation"]["steps"]["connection"]["not_dispatched"], False)
            self._settle()
            self._complete("action")
            self.assertIsNone(provision.ensure_system_snapshot("action"))
        self.assertEqual(sent[0]["metadata"], sent[1]["metadata"])
        self.assertEqual(sent[0]["spec"], sent[1]["spec"])
        self.assertEqual(len(sent), 2)
        self.assertEqual(second["creation"]["operation_id"], first["creation"]["operation_id"])
        self.assertEqual(second["creation"]["refs"], first["creation"]["refs"])

    def test_create_digest_is_only_checked_when_resending_a_write(self):
        self.assertEqual(provision.ensure_system_snapshot("action"), "DataConn")
        self._settle()
        row = self.rows["bkaudit_action_config_data"]
        record = row.config_value["bkbase_v4"]["default"]["audit"]
        attempt = record["creation"]["steps"]["connection"]
        attempt.update(target_digest="older-create-payload", not_dispatched=True)
        conn_ref = record["creation"]["refs"]["connection"]
        key = ("DataConn", conn_ref["name"])
        existing = self.resources.pop(key)
        with self.assertRaisesMessage(BKBaseResourceMappingError, "creation inputs changed"):
            provision.ensure_system_snapshot("action")
        self.assertEqual([kind for kind, _ in self.posts], ["DataConn"])

        self.resources[key] = existing
        self._complete("action")
        self.assertEqual([kind for kind, _ in self.posts], ["DataConn", "DataSource", "Clean", "DataStorage"])

    def _connection_claim(self, **step):
        """准备持久化声明，允许覆盖尝试字段以复现旧记录和并发快照。"""
        context = bindings._system_context()
        redis = provision._create_config("action", context)
        record = provision._new_record("action", context, redis)
        desired, _ = provision._source_spec(provision._params("action", record["creation"]), record["creation"])
        record["creation"]["steps"]["connection"] = {"target_digest": source._replay_digest(desired), **step}
        provision._save("action", context, None, record)
        return context, record, desired

    def test_old_target_digest_claim_does_not_repost(self):
        context, record, desired = self._connection_claim()
        create = mock.Mock()
        with self.assertLogs("app", level="WARNING") as captured:
            current, observed = provision._ensure_resource(
                "action", context, record, "connection", desired, self._getter("DataConn"), create
            )
        self.assertIsNone(current)
        self.assertEqual(observed, record)
        create.assert_not_called()
        self.assertEqual(len(captured.output), 1)
        self.assertIn("DataConn", captured.output[0])
        self.assertIn(record["creation"]["refs"]["connection"]["name"], captured.output[0])
        self.assertNotIn("Authorization", captured.output[0])
        self.assertNotIn("fixture_token", captured.output[0])

    def test_unknown_snapshot_write_errors_do_not_allow_retry(self):
        for status, code in ((404, None), (403, "1640401"), (500, "1640401"), (None, None)):
            with self.subTest(status=status, code=code):
                self.rows.clear()
                context, record, desired = self._connection_claim(attempt=1, not_dispatched=True)
                failure = APIRequestError(result={"message": "[1640401] synthetic uncertain outcome"})
                failure.http_status = status
                if code:
                    failure.gateway_error_code = code
                create = mock.Mock(side_effect=failure)
                with self.assertRaises(APIRequestError) as caught:
                    provision._ensure_resource(
                        "action", context, record, "connection", desired, self._getter("DataConn"), create
                    )
                self.assertIs(caught.exception, failure)
                key = bindings.SYSTEM_SNAPSHOT_KEYS["action"][0]
                saved = self.rows[key].config_value["bkbase_v4"]["default"]["audit"]
                self.assertIs(saved["creation"]["steps"]["connection"]["not_dispatched"], False)
                current, _ = provision._ensure_resource(
                    "action", context, saved, "connection", desired, self._getter("DataConn"), create
                )
                self.assertIsNone(current)
                create.assert_called_once()

    def test_old_or_superseded_snapshot_claim_does_not_repost(self):
        context, stale, desired = self._connection_claim(attempt=1, not_dispatched=True)
        rejection = APIRequestError(result={"message": "synthetic route rejection"})
        rejection.http_status = 404
        rejection.gateway_error_code = "1640401"
        newer_create = mock.Mock(side_effect=rejection)
        stale_create = mock.Mock()

        def after_newer_rejection(**params):
            with self.assertRaises(APIRequestError) as caught:
                provision._ensure_resource(
                    "action", context, stale, "connection", desired, self._getter("DataConn"), newer_create
                )
            self.assertIs(caught.exception, rejection)
            return self._getter("DataConn")(**params)

        with self.assertRaisesMessage(BKBaseResourceMappingError, "changed concurrently"):
            provision._ensure_resource(
                "action", context, stale, "connection", desired, after_newer_rejection, stale_create
            )
        newer_create.assert_called_once()
        stale_create.assert_not_called()
        key = bindings.SYSTEM_SNAPSHOT_KEYS["action"][0]
        step = self.rows[key].config_value["bkbase_v4"]["default"]["audit"]["creation"]["steps"]["connection"]
        self.assertEqual(step["attempt"], 2)
        self.assertIs(step["not_dispatched"], True)

    def test_superseded_snapshot_claim_cannot_overwrite_newer_rejection(self):
        context, record, desired = self._connection_claim(attempt=1, not_dispatched=True)
        rejection = APIRequestError(result={"message": "synthetic delayed rejection"})
        rejection.http_status = 404
        rejection.gateway_error_code = "1640401"
        key = bindings.SYSTEM_SNAPSHOT_KEYS["action"][0]

        def late_rejection(**params):
            claimed = deepcopy(self.rows[key].config_value["bkbase_v4"]["default"]["audit"])
            confirmed = deepcopy(claimed)
            confirmed["creation"]["steps"]["connection"]["not_dispatched"] = True
            provision._save("action", context, claimed, confirmed)
            with self.assertRaises(APIRequestError):
                provision._ensure_resource(
                    "action",
                    context,
                    confirmed,
                    "connection",
                    desired,
                    self._getter("DataConn"),
                    mock.Mock(side_effect=rejection),
                )
            raise rejection

        with self.assertRaisesMessage(BKBaseResourceMappingError, "changed concurrently") as caught:
            provision._ensure_resource(
                "action", context, record, "connection", desired, self._getter("DataConn"), late_rejection
            )
        self.assertIs(caught.exception.__context__, rejection)
        saved = self.rows[key].config_value["bkbase_v4"]["default"]["audit"]
        self.assertEqual(saved["creation"]["steps"]["connection"]["attempt"], 3)
        self.assertIs(saved["creation"]["steps"]["connection"]["not_dispatched"], True)

    def test_unknown_exception_after_retry_claim_does_not_repost(self):
        context, record, desired = self._connection_claim(attempt=1, not_dispatched=True)
        failure = RuntimeError("synthetic unknown outcome")
        create = mock.Mock(side_effect=failure)
        with self.assertRaises(RuntimeError) as caught:
            provision._ensure_resource(
                "action", context, record, "connection", desired, self._getter("DataConn"), create
            )
        self.assertIs(caught.exception, failure)
        key = bindings.SYSTEM_SNAPSHOT_KEYS["action"][0]
        saved = self.rows[key].config_value["bkbase_v4"]["default"]["audit"]
        self.assertEqual(saved["creation"]["steps"]["connection"]["attempt"], 2)
        self.assertIs(saved["creation"]["steps"]["connection"]["not_dispatched"], False)
        current, _ = provision._ensure_resource(
            "action", context, saved, "connection", desired, self._getter("DataConn"), create
        )
        self.assertIsNone(current)
        create.assert_called_once()

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
        current = self.resources[("DataSource", self.updates[0]["metadata"]["name"])]
        current["metadata"]["annotations"]["platform_observation"] = "accepted"
        current["spec"]["basic_info"]["description"] = "platform display description"
        current["spec"]["report_config"]["method"] = "POST"
        self._settle()
        self._complete("action")
        self.assertEqual(len(self.updates), 1)

    def _activation_failure(self, failure):
        """推进真实编排至第一次启用失败，保留原来源和下游资源。"""
        self.sdk.data_source_update.side_effect = failure
        for _ in range(15):
            try:
                provision.ensure_system_snapshot("action")
            except type(failure) as caught:
                self.assertIs(caught, failure)
                key = bindings.SYSTEM_SNAPSHOT_KEYS["action"][0]
                return deepcopy(self.rows[key].config_value["bkbase_v4"][bindings._system_context()["tenant"]]["audit"])
            self._settle()
        self.fail("activation was not reached")

    def _activation_rejection(self):
        failure = APIRequestError(result={"message": "synthetic activation route rejection"})
        failure.http_status = 404
        failure.gateway_error_code = "1640401"
        return failure

    def _assert_activation_rejection_resumes(self):
        resource = DataSourceUpdate()
        self.sdk.data_source_update.side_effect = resource.request
        sent = []

        def transport(**kwargs):
            self.assertFalse(self.in_transaction)
            sent.append(deepcopy(kwargs["json"]))
            response = requests.Response()
            response.url = kwargs["url"]
            response.request = requests.Request("PUT", response.url).prepare()
            if len(sent) == 1:
                response.status_code = 404
                payload = {"code": 1640401, "message": "synthetic route rejection"}
            else:
                response.status_code = 200
                data = kwargs["json"]
                payload = {
                    "result": True,
                    "code": "00",
                    "data": self._update_source(name=data["metadata"]["name"], **data),
                }
            response._content = json.dumps(payload).encode()
            return response

        with mock.patch.object(resource, "build_header", return_value={}), mock.patch.object(
            requests.sessions.Session, "request", side_effect=transport
        ):
            for _ in range(15):
                try:
                    provision.ensure_system_snapshot("action")
                except APIRequestError as error:
                    self.assertEqual(error.gateway_error_code, "1640401")
                    break
                self._settle()
            else:
                self.fail("activation was not reached")
            key = bindings.SYSTEM_SNAPSHOT_KEYS["action"][0]
            tenant = bindings._system_context()["tenant"]
            first = deepcopy(self.rows[key].config_value["bkbase_v4"][tenant]["audit"])
            intent = first["creation"]["source_start"]
            self.assertEqual(intent["attempt"], 1)
            self.assertIs(intent["not_dispatched"], True)
            self.assertNotEqual(intent["before_digest"], intent["target_digest"])
            self.assertEqual(len(sent), 1)
            self.assertEqual(provision.ensure_system_snapshot("action"), "DataSource")
            self.assertEqual(len(sent), 2)
            current = self.resources[("DataSource", first["creation"]["refs"]["data_source"]["name"])]
            current["status"]["phase"] = "Ok"
            self.assertEqual(provision.ensure_system_snapshot("action"), "DataSource")
            self.assertEqual(len(sent), 2)
            self._settle()
            self._complete("action")
            self.assertIsNone(provision.ensure_system_snapshot("action"))
        self.assertEqual(sent[0], sent[1])
        self.assertEqual(sent[1]["spec"]["desired_status"], "Running")
        self.assertEqual(len(sent), 2)
        final = self.rows[key].config_value["bkbase_v4"][tenant]["audit"]
        self.assertEqual(final["creation"]["operation_id"], first["creation"]["operation_id"])
        self.assertEqual(final["creation"]["refs"], first["creation"]["refs"])
        self.assertEqual(final["creation"]["source_start"]["attempt"], 2)
        self.assertIs(final["creation"]["source_start"]["not_dispatched"], False)

    def test_resume_source_activation_after_proven_route_rejection(self):
        self._assert_activation_rejection_resumes()

    @override_settings(
        BKPAAS_MULTI_TENANT_MODE=True,
        BK_TENANT_ID="tencent",
        BKBASE_V4_TENANT="tencent",
        BKBASE_V4_SYSTEM_SNAPSHOT_CREATE={
            "action": {"redis": {"kind": "Redis", "tenant": "tencent", "namespace": "clusters", "name": "iam_redis"}}
        },
    )
    def test_resume_source_activation_in_multitenant_mode(self):
        self._assert_activation_rejection_resumes()

    def test_snapshot_resumes_when_asset_specs_readback_differs(self):
        record = self._activation_failure(self._activation_rejection())
        refs = record["creation"]["refs"]
        conn = self.resources[("DataConn", refs["connection"]["name"])]["spec"]
        conn["data_conn_alias"] = "platform display name"
        conn["conn_info"]["platform_default"] = True
        conn["conn_info"]["headers"]["X-Platform-Default"] = "true"
        headers = conn["conn_info"]["headers"]
        headers["Content-Type"] = headers.pop("Content-type")
        cleaner = self.resources[("Clean", refs["clean"]["name"])]["spec"]
        cleaner["alias"] = "platform display name"
        cleaner["deploy_revision"] += 1
        cleaner["data_id"].pop("tenant")
        cleaner["data_id"]["platform_default"] = True
        stored = self.resources[("DataStorage", refs["storage"]["name"])]["spec"]
        stored["tableInfo"]["storage"]["platform_default"] = True
        stored["tableInfo"]["expire"] = 1
        stored["taskFieldSetting"]["key_fields"] = ["system_id", "id"]

        def table_with_platform_fields(**kwargs):
            table = self._table(**kwargs)
            spec = table["status"]["related"][0]["spec"]
            spec["data"] = {**spec["data"], "platform_default": True}
            spec["storage"] = {key: value for key, value in spec["storage"].items() if key != "tenant"}
            return table

        self.sdk.result_table_info.side_effect = table_with_platform_fields
        self.sdk.data_source_update.side_effect = self._update_source
        self._complete("action")

        final = self.rows["bkaudit_action_config_data"].config_value["bkbase_v4"]["default"]["audit"]
        self.assertTrue(final["ready"])
        self.assertEqual(final["creation"]["refs"], refs)
        self.assertEqual(final["redis_key_fields"], ["system_id", "id"])
        self.assertEqual([kind for kind, _ in self.posts], ["DataConn", "DataSource", "Clean", "DataStorage"])
        self.assertEqual(self.sdk.data_source_update.call_count, 2)

    def test_snapshot_checks_usable_redis_keys_before_activating_source(self):
        record = self._activation_failure(self._activation_rejection())
        ref = record["creation"]["refs"]["storage"]
        stored = self.resources[("DataStorage", ref["name"])]["spec"]
        stored["taskFieldSetting"]["key_fields"] = ["id"]

        with self.assertRaisesMessage(BKBaseResourceMappingError, "Redis Join key fields mismatch"):
            provision.ensure_system_snapshot("action")

        self.assertEqual(self.sdk.data_source_update.call_count, 1)

    def test_asset_readback_rejects_different_resource_identity_before_activation(self):
        record = self._activation_failure(self._activation_rejection())
        refs = record["creation"]["refs"]
        for kind, key in (
            ("DataConn", "connection"),
            ("Clean", "clean"),
            ("DataStorage", "storage"),
        ):
            metadata = self.resources[(kind, refs[key]["name"])]["metadata"]
            with self.subTest(kind=kind), mock.patch.dict(metadata, name="another_ref"):
                with self.assertRaisesMessage(BKBaseResourceMappingError, "resource identity changed"):
                    provision.ensure_system_snapshot("action")
        self.assertEqual(self.sdk.data_source_update.call_count, 1)
        self.assertEqual([kind for kind, _ in self.posts], ["DataConn", "DataSource", "Clean", "DataStorage"])

    def test_legacy_source_activation_only_observes_state_without_replay(self):
        record = self._activation_failure(self._activation_rejection())
        current = self.resources[("DataSource", record["creation"]["refs"]["data_source"]["name"])]
        record["creation"]["source_start"] = {"target_digest": "old-format-digest"}
        key = bindings.SYSTEM_SNAPSHOT_KEYS["action"][0]
        self.rows[key].config_value["bkbase_v4"]["default"]["audit"] = deepcopy(record)
        self.assertEqual(provision.ensure_system_snapshot("action"), "DataSource")
        self.assertEqual(self.sdk.data_source_update.call_count, 1)
        current["spec"]["current_status"] = "Running"
        current["spec"].pop("desired_status")
        self.assertIsNone(provision.ensure_system_snapshot("action"))
        self.assertEqual(self.sdk.data_source_update.call_count, 1)

    def test_unknown_source_activation_waits_without_rewriting_unchanged_source(self):
        record = self._activation_failure(APIRequestError(result={"message": "synthetic unknown outcome"}))
        for _ in range(2):
            self.assertEqual(provision.ensure_system_snapshot("action"), "DataSource")
        self.assertEqual(self.sdk.data_source_update.call_count, 1)
        key = bindings.SYSTEM_SNAPSHOT_KEYS["action"][0]
        saved = self.rows[key].config_value["bkbase_v4"]["default"]["audit"]
        self.assertFalse(saved["ready"])
        self.assertEqual(
            saved["creation"]["source_start"]["before_digest"], record["creation"]["source_start"]["before_digest"]
        )
        self.assertIs(saved["creation"]["source_start"]["not_dispatched"], False)

    def test_resume_source_activation_rechecks_real_downstream_readiness(self):
        record = self._activation_failure(self._activation_rejection())
        cleaner = self.resources[("Clean", record["creation"]["refs"]["clean"]["name"])]
        cleaner["status"]["phase"] = "Pending"
        self.assertEqual(provision.ensure_system_snapshot("action"), "Clean")
        cleaner["status"]["phase"] = "Ok"
        stored = self.resources[("DataStorage", record["creation"]["refs"]["storage"]["name"])]
        stored["status"]["phase"] = "Pending"
        self.assertEqual(provision.ensure_system_snapshot("action"), "DataStorage")
        stored["status"]["phase"] = "Ok"

        def pending_table(**kwargs):
            table = self._table(**kwargs)
            table["status"]["phase"] = "Pending"
            return table

        def pending_redis(**kwargs):
            table = self._table(**kwargs)
            table["status"]["related"][0]["status"]["related"][0]["status"]["phase"] = "Pending"
            return table

        for getter in (pending_table, pending_redis):
            self.sdk.result_table_info.side_effect = getter
            self.assertEqual(provision.ensure_system_snapshot("action"), "RedisBinding")
        self.sdk.result_table_info.side_effect = self._table
        self.assertEqual(self.sdk.data_source_update.call_count, 1)

    def test_resume_source_activation_waits_for_actual_stopped_source(self):
        record = self._activation_failure(self._activation_rejection())
        current = self.resources[("DataSource", record["creation"]["refs"]["data_source"]["name"])]
        current["status"]["phase"] = "Pending"
        self.assertEqual(provision.ensure_system_snapshot("action"), "DataSource")
        current["status"]["phase"] = "Ok"
        current["spec"]["current_status"] = "Running"
        self.assertEqual(provision.ensure_system_snapshot("action"), "DataSource")
        self.assertEqual(self.sdk.data_source_update.call_count, 1)

    def test_resume_source_activation_rechecks_source_before_put(self):
        record = self._activation_failure(self._activation_rejection())
        current = self.resources[("DataSource", record["creation"]["refs"]["data_source"]["name"])]
        reads = []

        def changed_during_downstream_check(**params):
            reads.append(params)
            if len(reads) == 2:
                current["spec"]["desired_status"] = "Running"
            return self._getter("DataSource")(**params)

        self.sdk.data_source_get.side_effect = changed_during_downstream_check
        self.assertEqual(provision.ensure_system_snapshot("action"), "DataSource")
        self.assertEqual(len(reads), 2)
        self.assertEqual(self.sdk.data_source_update.call_count, 1)

    def test_resume_source_activation_preserves_latest_spec_from_the_same_resource(self):
        record = self._activation_failure(self._activation_rejection())
        current = self.resources[("DataSource", record["creation"]["refs"]["data_source"]["name"])]
        reads = []

        def changed_during_downstream_check(**params):
            reads.append(params)
            if len(reads) == 2:
                current["spec"]["report_config"]["method"] = "POST"
            return self._getter("DataSource")(**params)

        self.sdk.data_source_get.side_effect = changed_during_downstream_check
        self.sdk.data_source_update.side_effect = self._update_source
        self.assertEqual(provision.ensure_system_snapshot("action"), "DataSource")
        self.assertEqual(self.sdk.data_source_update.call_count, 2)
        self.assertEqual(self.updates[0]["spec"]["report_config"]["method"], "POST")
        self.assertEqual(self.updates[0]["spec"]["desired_status"], "Running")
        self._settle()
        self._complete("action")
        self.assertEqual(self.sdk.data_source_update.call_count, 2)

    def test_snapshot_cannot_rebind_source_before_first_activation(self):
        for pending in ("DataConn", "DataSource", "Clean"):
            self.assertEqual(provision.ensure_system_snapshot("action"), pending)
            self._settle()

        key = bindings.SYSTEM_SNAPSHOT_KEYS["action"][0]
        row = self.rows[key]
        record = deepcopy(row.config_value["bkbase_v4"]["default"]["audit"])
        self.assertNotIn("source_start", record["creation"])
        ref = record["creation"]["refs"]["data_source"]
        current = self.resources[("DataSource", ref["name"])]
        for fields, change in (
            (current["spec"]["data_id"], {"name": "another_data_id"}),
            (current["metadata"]["labels"], {"raw_data_id": "99"}),
        ):
            with self.subTest(change=change), mock.patch.dict(fields, change):
                with self.assertRaises(BKBaseResourceMappingError):
                    provision.ensure_system_snapshot("action")
            self.assertEqual(row.config_value["bkbase_v4"]["default"]["audit"], record)
            self.assertEqual([kind for kind, _ in self.posts], ["DataConn", "DataSource", "Clean"])
            self.sdk.data_source_update.assert_not_called()

    def test_resume_source_activation_cannot_rebind_changed_raw_data_id(self):
        record = self._activation_failure(self._activation_rejection())
        current = self.resources[("DataSource", record["creation"]["refs"]["data_source"]["name"])]
        current["metadata"]["labels"]["raw_data_id"] = "99"
        with self.assertRaises(BKBaseResourceMappingError):
            provision.ensure_system_snapshot("action")
        key = bindings.SYSTEM_SNAPSHOT_KEYS["action"][0]
        self.assertEqual(self.rows[key].config_value["bkbase_v4"]["default"]["audit"], record)
        self.assertEqual(self.sdk.data_source_update.call_count, 1)

    def test_resume_source_activation_cannot_rebind_changed_data_id(self):
        record = self._activation_failure(self._activation_rejection())
        current = self.resources[("DataSource", record["creation"]["refs"]["data_source"]["name"])]
        current["spec"]["data_id"]["name"] = "another_data_id"
        with self.assertRaises(BKBaseResourceMappingError):
            provision.ensure_system_snapshot("action")
        key = bindings.SYSTEM_SNAPSHOT_KEYS["action"][0]
        self.assertEqual(self.rows[key].config_value["bkbase_v4"]["default"]["audit"], record)
        self.assertEqual(self.sdk.data_source_update.call_count, 1)

    def test_resume_source_activation_cannot_rebind_changed_result_table(self):
        record = self._activation_failure(self._activation_rejection())

        def changed_table(**params):
            table = self._table(**params)
            table["metadata"]["name"] = "another_result_table"
            return table

        self.sdk.result_table_info.side_effect = changed_table
        with self.assertRaises(BKBaseResourceMappingError):
            provision.ensure_system_snapshot("action")
        key = bindings.SYSTEM_SNAPSHOT_KEYS["action"][0]
        self.assertEqual(self.rows[key].config_value["bkbase_v4"]["default"]["audit"], record)
        self.assertEqual(self.sdk.data_source_update.call_count, 1)

    def test_superseded_source_activation_claim_cannot_put_again(self):
        failure = self._activation_rejection()
        stale = self._activation_failure(failure)
        with self.assertRaises(APIRequestError) as caught:
            provision.ensure_system_snapshot("action")
        self.assertIs(caught.exception, failure)
        self.assertEqual(self.sdk.data_source_update.call_count, 2)
        context = bindings._system_context()
        with self.assertRaisesMessage(BKBaseResourceMappingError, "changed concurrently"):
            provision._advance("action", context, stale, stale["creation"]["redis"])
        self.assertEqual(self.sdk.data_source_update.call_count, 2)
        key = bindings.SYSTEM_SNAPSHOT_KEYS["action"][0]
        intent = self.rows[key].config_value["bkbase_v4"]["default"]["audit"]["creation"]["source_start"]
        self.assertEqual(intent["attempt"], 2)
        self.assertIs(intent["not_dispatched"], True)

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

    @override_settings(
        BKPAAS_MULTI_TENANT_MODE=True,
        BK_TENANT_ID="tencent",
        BKBASE_V4_TENANT="tencent",
        BKBASE_V4_SYSTEM_SNAPSHOT_CREATE={
            "action": {"redis": {"kind": "Redis", "tenant": "tencent", "namespace": "clusters", "name": "iam_redis"}}
        },
    )
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

    def test_init_fallback_records_the_only_registered_redis(self):
        redis_ref = {"kind": "Redis", "tenant": "default", "namespace": "audit", "name": "registered"}
        fallback = mock.Mock(return_value=redis_ref)
        with override_settings(BKBASE_V4_SYSTEM_SNAPSHOT_CREATE={}):
            for _ in range(12):
                waiting = provision.ensure_system_snapshot("action", init_redis_fallback=fallback)
                self._settle()
                if waiting is None:
                    break
        record = bindings._scoped_binding(
            bindings._read_config(bindings.SYSTEM_SNAPSHOT_KEYS["action"][0]), bindings._system_context()
        )
        self.assertEqual(record["creation"]["redis"], redis_ref)
        storage_spec = next(params["spec"] for kind, params in self.posts if kind == "DataStorage")
        self.assertEqual(storage_spec["tableInfo"]["storage"], redis_ref)
        fallback.assert_called_once()
        # 显式覆盖仍优先，且不因登记候选不同而触发选择器。
        fallback.reset_mock()
        provision.ensure_system_snapshot("user", init_redis_fallback=fallback)
        fallback.assert_not_called()
        record = bindings._scoped_binding(
            bindings._read_config(bindings.SYSTEM_SNAPSHOT_KEYS["user"][0]), bindings._system_context()
        )
        self.assertEqual(record["creation"]["redis"]["name"], "iam_redis")

    def test_init_resume_keeps_claimed_redis(self):
        redis_ref = {"kind": "Redis", "tenant": "default", "namespace": "audit", "name": "registered"}
        with override_settings(BKBASE_V4_SYSTEM_SNAPSHOT_CREATE={}):
            provision.ensure_system_snapshot("action", init_redis_fallback=mock.Mock(return_value=redis_ref))
            saved_before = deepcopy(self.rows[bindings.SYSTEM_SNAPSHOT_KEYS["action"][0]].config_value)
            fallback = mock.Mock(side_effect=AssertionError("must preserve claimed Redis"))
            provision.ensure_system_snapshot("action", init_redis_fallback=fallback)
            fallback.assert_not_called()
        saved_after = self.rows[bindings.SYSTEM_SNAPSHOT_KEYS["action"][0]].config_value
        self.assertEqual(saved_after, saved_before)
        with override_settings(
            BKBASE_V4_SYSTEM_SNAPSHOT_CREATE={"action": {"redis": {**redis_ref, "name": "changed"}}}
        ):
            with self.assertRaises(BKBaseResourceMappingError):
                provision.ensure_system_snapshot("action", init_redis_fallback=fallback)
        self.assertEqual(self.rows[bindings.SYSTEM_SNAPSHOT_KEYS["action"][0]].config_value, saved_before)
        self.assertEqual(len(self.posts), 1)
