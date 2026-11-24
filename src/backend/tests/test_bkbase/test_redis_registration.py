"""Redis注册经真实Handler/Resource.request保存权威Ref并供已有入库消费者使用。

只替换HTTP边界，注册与配置绑定不等于Redis连接、任务运行或数据验收。
"""
import json
from copy import deepcopy
from unittest import mock

import requests
from blueapps.utils.logger import logger
from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from apps.meta.models import ResourceType, System
from services.web.bkbase import storage
from services.web.bkbase.common import get_bkbase_context
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.collector.snapshot.join.base import BaseJoinDataHandler
from services.web.databus.collector.snapshot.join.etl_storage import (
    AssetEtlStorageHandler,
    JoinDataEtlStorageHandler,
)
from services.web.databus.models import RedisConfig, Snapshot, SnapshotStorage
from services.web.databus.storage.handler.redis import RedisHandler
from services.web.databus.storage.resources import CreateOrUpdateRedisResource
from services.web.databus.storage.serializers import RedisConnectionInfoSerializer


@override_settings(
    BKBASE_V4_TENANT="tenant_a",
    BKBASE_V4_NAMESPACE="bk_project",
    BK_RESOURCE={"PLATFORM_AUTH_ENABLED": True, "PLATFORM_AUTH_ACCESS_USERNAME": "synthetic_platform"},
)
class RedisRegistrationParamsTests(SimpleTestCase):
    def setUp(self):
        self.info = {
            "enable_sentinel": False,
            "name_sentinel": "string",
            "host_sentinel": "string",
            "port_sentinel": 0,
            "host": "redis.synthetic.test",
            "port": 6379,
            "password": "synthetic_password",
        }

    def registration(self, info):
        return storage._redis_registration_params(
            {"resource_set_id": "synthetic_redis", "resource_set_name": "Synthetic Redis", "connection_info": info}
        )[2]

    def test_disabled_sentinel_placeholders_are_omitted_from_direct_connection(self):
        serializer = RedisConnectionInfoSerializer(data=self.info)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        payload = self.registration(serializer.validated_data)
        self.assertEqual(
            payload["connection"],
            {
                "kind": "Redis",
                "config": {"host": "redis.synthetic.test", "port": 6379, "password": "synthetic_password"},
            },
        )

    def test_serializer_defaults_missing_sentinel_flag_to_direct_connection(self):
        info = {key: value for key, value in self.info.items() if key != "enable_sentinel"}
        serializer = RedisConnectionInfoSerializer(data=info)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        payload = self.registration(serializer.validated_data)
        self.assertEqual(
            payload["connection"],
            {
                "kind": "Redis",
                "config": {"host": "redis.synthetic.test", "port": 6379, "password": "synthetic_password"},
            },
        )

    def test_sentinel_without_explicit_disable_and_invalid_direct_options_are_rejected(self):
        cases = [
            {**self.info, "enable_sentinel": True},
            {key: value for key, value in self.info.items() if key != "enable_sentinel"},
            {**self.info, "host": ""},
            {**self.info, "port": 0},
            {**self.info, "password": "*******"},
            {**self.info, "unsupported": "value"},
        ]
        for info in cases:
            with self.subTest(info=info), self.assertRaises(BKBaseResourceMappingError):
                self.registration(info)


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="tenant_a",
    BKBASE_V4_NAMESPACE="bk_project",
    APP_CODE="synthetic_app",
    SECRET_KEY="synthetic_secret",
    BK_RESOURCE={
        "PLATFORM_AUTH_ENABLED": True,
        "PLATFORM_AUTH_ACCESS_USERNAME": "synthetic_platform",
        "PLATFORM_AUTH_ACCESS_TOKEN": "synthetic_token",
    },
)
class RedisRegistrationTests(TransactionTestCase):
    def setUp(self):
        self.data = {
            "namespace": "audit_namespace",
            "redis_name_en": "synthetic_redis",
            "redis_name": "合成Redis",
            "connection_info": {
                "enable_sentinel": False,
                "host": "redis.synthetic.test",
                "port": 6379,
                "password": "synthetic_password",
            },
            "version": "6.0",
        }
        self.ref = {"kind": "Redis", "tenant": "tenant_a", "namespace": "bk_project", "name": "synthetic_redis"}
        self.calls = []
        self.asset = None
        self.post_error = None
        self.detail_error = False
        self.detail_ref = self.ref
        self.redirect_post = False
        self.enterContext(mock.patch("requests.sessions.Session.request", side_effect=self.transport))
        self.enterContext(
            mock.patch(
                "services.web.databus.storage.handler.redis.get_request_username", return_value="synthetic_operator"
            )
        )

    def response(self, url, value, success=True, code="00"):
        response = requests.Response()
        response.status_code = 200
        response.url = url
        response._content = json.dumps(
            {"result": success, "code": code, "data": value, "message": None if success else "synthetic error"}
        ).encode()
        return response

    def transport(self, method, url, **kwargs):
        self.assertFalse(connection.in_atomic_block, "Redis network must not hold a DB transaction")
        self.calls.append((method.upper(), url, deepcopy(kwargs)))
        auth = json.loads(kwargs["headers"]["x-bkapi-authorization"])
        self.assertEqual(auth["bk_username"], "synthetic_platform")
        if "/res_manage/" in url:
            self.assertEqual(kwargs["headers"]["X-Bk-Tenant-Id"], "tenant_a")
            self.assertNotIn("tenant", kwargs.get("json", {}))
            self.assertNotIn("tenant", kwargs.get("params", {}))
        if method == "POST" and url.endswith("/res_manage/assets/storage/"):
            intent = RedisConfig.objects.get(redis_name_en=self.data["redis_name_en"])
            self.assertEqual(intent.extra["bkbase_v4"]["registration_state"], "registering")
            if self.asset is not None:
                return self.response(url, None, False, "1553003")
            self.asset = {
                "asset_name": self.data["redis_name_en"],
                "belong_type": "project_private",
                "project_name": "bk_project",
                "resource_ns": deepcopy(self.detail_ref),
                "ext_properties": {"connection": {"config": {"password": "*******"}}},
            }
            if self.post_error:
                raise self.post_error
            response = self.response(url, {"asset_name": self.data["redis_name_en"]})
            if self.redirect_post:
                response.status_code = 307
            return response
        if method == "GET" and "/res_manage/assets/bk_project/Redis/" in url:
            if self.detail_error:
                raise requests.Timeout("synthetic detail timeout")
            if self.asset is None:
                return self.response(url, None, False, "1553002")
            value = deepcopy(self.asset)
            value["resource_ns"] = deepcopy(self.detail_ref)
            return self.response(url, value)
        if method == "GET" and url.endswith("/res_manage/assets/"):
            return self.response(
                url,
                {
                    "list": [] if self.asset is None else [deepcopy(self.asset)],
                    "total": int(self.asset is not None),
                    "pages_num": int(self.asset is not None),
                },
            )
        if method == "GET" and "/datastorages/" in url:
            return self.response(url, "Resource not found.", False, "1558025")
        if method == "POST" and url.endswith("/datastorages/"):
            return self.response(
                url,
                {
                    "kind": "DataStorage",
                    "metadata": kwargs["json"]["metadata"],
                    "spec": kwargs["json"]["spec"],
                    "status": {"phase": "Pending"},
                },
            )
        raise AssertionError("Unexpected endpoint: " + method + " " + url)

    def create(self):
        return RedisHandler().update_or_create(deepcopy(self.data))

    def posts(self):
        return [c for c in self.calls if c[0] == "POST" and "/res_manage/assets/storage/" in c[1]]

    def test_handler_registers_private_asset_with_platform_identity_and_persists_authoritative_ref(self):
        result = CreateOrUpdateRedisResource().request(deepcopy(self.data))
        row = RedisConfig.objects.get(redis_id=result["redis_id"])
        payload = self.posts()[0][2]["json"]
        self.assertEqual(payload["project_name"], "bk_project")
        self.assertEqual(payload["asset_name"], self.data["redis_name_en"])
        self.assertEqual(payload["asset_alias"], self.data["redis_name"])
        self.assertEqual(payload["belong_type"], "project_private")
        self.assertTrue(payload["sync_to_iam"])
        self.assertTrue(payload["encrypt_password"])
        self.assertEqual(
            payload["connection"],
            {
                "kind": "Redis",
                "config": {"host": "redis.synthetic.test", "port": 6379, "password": "synthetic_password"},
            },
        )
        for key in ("bk_username", "admin", "share", "bk_biz_id", "namespace", "version"):
            self.assertNotIn(key, payload)
        self.assertEqual(row.extra["bkbase_v4"]["resource_ref"], self.ref)
        self.assertEqual(row.extra["bkbase_v4"]["registration_state"], "bound")
        self.assertEqual(row.admin, ["synthetic_platform"])
        self.assertEqual(row.namespace, "audit_namespace")
        self.assertEqual(row.connection_info["password"], "synthetic_password")

    def test_registered_ref_is_used_by_real_redis_selection_and_storage_consumer(self):
        row = self.create()
        row.extra.update(count=3, systems=[], future={"preserve": True})
        row.save(update_fields=["extra"])
        system = System.objects.create(system_id="redis_system", namespace="audit_namespace")
        kind = ResourceType.objects.create(
            system_id=system.system_id, resource_type_id="asset", unique_id="redis_system:asset"
        )
        rt = {"kind": "ResultTable", "tenant": "tenant_a", "namespace": "tables", "name": "actual_rt"}
        owner = Snapshot.objects.create(
            system_id=system.system_id, resource_type_id="asset", bkbase_v4_resources={"result_table": rt}
        )
        handler = JoinDataEtlStorageHandler(11, system, kind, "redis", snapshot=owner)
        stored = SnapshotStorage.objects.create(snapshot=owner, storage_type="redis")
        upper = mock.Mock(snapshot=owner, system=system, resource_type=kind, storage_type="redis")
        upper.etl_storage_handler_cls.return_value = handler
        with mock.patch.object(storage.GlobalMetaConfig, "get", return_value={}), mock.patch.object(
            storage, "resource_lock"
        ):
            self.assertFalse(BaseJoinDataHandler.create_data_storage(upper))
        stored.refresh_from_db()
        self.assertEqual(stored.status, "preparing")
        payload = next(c[2]["json"] for c in self.calls if c[0] == "POST" and c[1].endswith("/datastorages/"))
        self.assertEqual(payload["spec"]["tableInfo"]["storage"], self.ref)
        row.refresh_from_db()
        self.assertEqual(row.extra["count"], 4)
        self.assertEqual(row.extra["systems"], [system.system_id])
        self.assertEqual(row.extra["future"], {"preserve": True})
        self.assertEqual(row.extra["bkbase_v4"]["resource_ref"], self.ref)

    def test_resource_preserves_password_and_rejects_unknown_or_db(self):
        for option in ("db", "unknown_option"):
            data = deepcopy(self.data)
            data["connection_info"][option] = 2
            with self.assertRaises(Exception):
                CreateOrUpdateRedisResource().request(data)
            self.assertFalse(self.posts())
        data = deepcopy(self.data)
        data["connection_info"]["password"] = "  synthetic password  "
        CreateOrUpdateRedisResource().request(data)
        self.assertEqual(self.posts()[0][2]["json"]["connection"]["config"]["password"], "  synthetic password  ")

    def test_registered_and_legacy_mapping_conflict_or_incomplete_rejected(self):
        row = self.create()
        context = get_bkbase_context()
        mapping = {"redis": {"synthetic_redis": {**self.ref, "name": "other"}}}
        with mock.patch.object(storage.GlobalMetaConfig, "get", return_value=mapping):
            with self.assertRaises(BKBaseResourceMappingError):
                storage.resolve_storage_cluster(
                    context,
                    audit_namespace="audit_namespace",
                    storage_type="redis",
                    legacy_cluster_id="synthetic_redis",
                )
            row.extra["bkbase_v4"]["registration_state"] = "unknown"
            row.save(update_fields=["extra"])
            with self.assertRaises(BKBaseResourceMappingError):
                storage.resolve_storage_cluster(
                    context,
                    audit_namespace="audit_namespace",
                    storage_type="redis",
                    legacy_cluster_id="synthetic_redis",
                )
            row.extra.pop("bkbase_v4")
            row.save(update_fields=["extra"])
            self.assertEqual(
                storage.resolve_storage_cluster(
                    context,
                    audit_namespace="audit_namespace",
                    storage_type="redis",
                    legacy_cluster_id="synthetic_redis",
                ),
                mapping["redis"]["synthetic_redis"],
            )

    def test_join_redis_storage_state_requires_running_observation(self):
        owner = Snapshot.objects.create(system_id="state_system", resource_type_id="asset")
        row = SnapshotStorage.objects.create(snapshot=owner, storage_type="redis")
        handler = mock.Mock(snapshot=owner, system=mock.Mock(), resource_type=mock.Mock(), storage_type="redis")
        operation = handler.etl_storage_handler_cls.return_value.create_storage
        for state, expected, ready in [(None, "preparing", False), ("running", "running", True)]:
            operation.return_value = {"task_state": state}
            self.assertEqual(BaseJoinDataHandler.create_data_storage(handler), ready)
            row.refresh_from_db()
            self.assertEqual(row.status, expected)
        operation.return_value = {"task_state": "failed"}
        with self.assertRaises(BKBaseResourceMappingError):
            BaseJoinDataHandler.create_data_storage(handler)
        row.refresh_from_db()
        self.assertEqual(row.status, "failed")
        operation.side_effect = RuntimeError("failure")
        with self.assertRaises(RuntimeError):
            BaseJoinDataHandler.create_data_storage(handler)
        row.refresh_from_db()
        self.assertEqual(row.status, "failed")

    def test_asset_redis_rejects_unimplemented_maintenance_before_storage_write(self):
        system = System.objects.create(system_id="asset_guard", namespace="audit_namespace")
        kind = ResourceType.objects.create(
            system_id=system.system_id, resource_type_id="asset", unique_id="asset_guard:asset"
        )
        owner = Snapshot.objects.create(system_id=system.system_id, resource_type_id="asset")
        handler = AssetEtlStorageHandler(11, system, kind, "redis", snapshot=owner)
        handler.__dict__["schema_fields"] = []
        with mock.patch.object(storage, "configure_storage") as write:
            for update in (False, True):
                with self.assertRaises(BKBaseResourceMappingError) as caught:
                    handler.create_storage(update=update)
                self.assertIn("maintenance", str(caught.exception))
            write.assert_not_called()
        with mock.patch.object(JoinDataEtlStorageHandler, "create_storage", return_value="ok"):
            handler.storage_type = "doris"
            self.assertEqual(handler.create_storage(), "ok")
            handler.storage_type = "redis"
            with override_settings(BKBASE_API_VERSION="v3"):
                self.assertEqual(handler.create_storage(), "ok")

    def test_accepted_registration_detail_retry_only_reads_without_reposting(self):
        self.detail_error = True
        with self.assertRaises(BKBaseResourceMappingError):
            self.create()
        row = RedisConfig.objects.get(redis_name_en=self.data["redis_name_en"])
        self.assertEqual(row.extra["bkbase_v4"]["registration_state"], "accepted")
        self.assertNotIn("resource_ref", row.extra["bkbase_v4"])
        row.extra.update(count=7, systems=["existing_system"])
        row.save(update_fields=["extra"])
        self.detail_error = False
        bound = self.create()
        self.assertEqual(bound.pk, row.pk)
        self.assertEqual(len(self.posts()), 1)
        self.assertEqual(bound.extra["count"], 7)
        self.assertEqual(bound.extra["systems"], ["existing_system"])
        self.assertEqual(bound.extra["bkbase_v4"]["resource_ref"], self.ref)

    def test_unknown_registration_does_not_retry_post_or_adopt_found_resource(self):
        self.post_error = requests.Timeout("synthetic creation outcome unknown")
        with self.assertRaises(BKBaseResourceMappingError):
            self.create()
        self.post_error = None
        with self.assertRaises(BKBaseResourceMappingError):
            self.create()
        self.assertEqual(len(self.posts()), 1)
        row = RedisConfig.objects.get(redis_name_en=self.data["redis_name_en"])
        self.assertEqual(row.extra["bkbase_v4"]["registration_state"], "unknown")
        self.assertNotIn("resource_ref", row.extra["bkbase_v4"])

    def test_unverified_or_wrong_tenant_ref_never_becomes_bound(self):
        self.detail_ref = {**self.ref, "tenant": "other_tenant"}
        with self.assertRaises(BKBaseResourceMappingError):
            self.create()
        row = RedisConfig.objects.get(redis_name_en=self.data["redis_name_en"])
        self.assertEqual(row.extra["bkbase_v4"]["registration_state"], "accepted")
        self.assertNotIn("resource_ref", row.extra["bkbase_v4"])

    def test_sentinel_and_masked_password_are_rejected_before_registering(self):
        for params in ({"enable_sentinel": True}, {"password": "*******"}):
            with self.subTest(params=params):
                self.data["connection_info"].update(params)
                with self.assertRaises(BKBaseResourceMappingError):
                    self.create()
                self.assertFalse(RedisConfig.objects.exists())
                self.assertEqual(self.calls, [])
                self.data["connection_info"] = {
                    "enable_sentinel": False,
                    "host": "redis.synthetic.test",
                    "port": 6379,
                    "password": "synthetic_password",
                }

    def test_existing_update_is_skipped_and_resource_returns_the_registered_configuration(self):
        row = self.create()
        old = RedisConfig.objects.filter(pk=row.pk).values().get()
        before = len(self.calls)
        changed = {
            **self.data,
            "redis_id": row.pk,
            "redis_name": "Changed Redis",
            "version": "7.0",
            "connection_info": {
                **self.data["connection_info"],
                "host": "redis.changed.synthetic.test",
                "password": "synthetic_changed_secret",
            },
        }
        with self.assertLogs(logger, level="WARNING") as emitted:
            result = CreateOrUpdateRedisResource().request(changed)
        expected = {
            key: old[key]
            for key in [
                "redis_id",
                "namespace",
                "redis_name_en",
                "redis_name",
                "admin",
                "connection_info",
                "version",
                "extra",
                "is_deleted",
            ]
        }
        # BKSEC 1578945：响应白名单剔除连接密码，其余字段仍与库内原记录一致
        expected["connection_info"] = {key: value for key, value in old["connection_info"].items() if key != "password"}
        self.assertEqual(result, expected)
        row.refresh_from_db()
        self.assertEqual(RedisConfig.objects.filter(pk=row.pk).values().get(), old)
        self.assertEqual(row.extra["bkbase_v4"]["registration_state"], "bound")
        self.assertEqual(len(self.calls), before)
        logs = "\n".join(emitted.output)
        self.assertIn("跳过", logs)
        self.assertNotIn("synthetic_changed_secret", logs)
        self.assertNotIn("redis.changed.synthetic.test", logs)

    def test_existing_unverified_update_does_not_manufacture_a_bound_registration(self):
        row = RedisConfig.objects.create(
            namespace=self.data["namespace"],
            redis_name_en=self.data["redis_name_en"],
            redis_name=self.data["redis_name"],
            connection_info=self.data["connection_info"],
            version=self.data["version"],
            admin=["synthetic_operator"],
            extra={"bkbase_v4": {"registration_state": "unknown", "payload_digest": "synthetic_original_digest"}},
        )
        old = RedisConfig.objects.filter(pk=row.pk).values().get()
        with self.assertLogs(logger, level="WARNING"):
            result = RedisHandler(row.pk).update_or_create({**self.data, "redis_name": "Changed Redis"})
        self.assertIsInstance(result, RedisConfig)
        self.assertEqual(result.pk, row.pk)
        self.assertEqual(result.extra, old["extra"])
        self.assertEqual(result.connection_info, old["connection_info"])
        self.assertEqual(RedisConfig.objects.filter(pk=row.pk).values().get(), old)
        self.assertEqual(self.calls, [])

    def test_same_tenant_duplicate_asset_is_not_adopted_or_reposted(self):
        self.asset = {"asset_name": self.data["redis_name_en"], "belong_type": "shared"}
        for _ in range(2):
            with self.assertRaises(BKBaseResourceMappingError):
                self.create()
        self.assertEqual(len(self.posts()), 1)
        row = RedisConfig.objects.get(redis_name_en=self.data["redis_name_en"])
        self.assertEqual(row.extra["bkbase_v4"]["registration_state"], "rejected")
        self.assertNotIn("resource_ref", row.extra["bkbase_v4"])

    def test_registration_redirect_is_unknown_without_automatic_post_follow(self):
        self.redirect_post = True
        with self.assertRaises(BKBaseResourceMappingError):
            self.create()
        self.assertIs(self.posts()[0][2]["allow_redirects"], False)
        row = RedisConfig.objects.get(redis_name_en=self.data["redis_name_en"])
        self.assertEqual(row.extra["bkbase_v4"]["registration_state"], "unknown")

    def test_registered_list_and_shared_detail_preserve_authoritative_owner_namespace(self):
        self.asset = {"asset_name": "shared_redis", "belong_type": "shared", "project_name": "owner_project"}
        self.detail_ref = {**self.ref, "namespace": "owner_project", "name": "shared_redis"}
        page = storage.list_registered_redis_assets(page=2, page_size=10, asset_name="redis")
        self.assertEqual(page["list"][0]["project_name"], "owner_project")
        call = self.calls[-1][2]
        self.assertEqual(call["params"]["project_name"], "bk_project")
        self.assertEqual(call["params"]["sub_types"], ["Redis"])
        self.assertEqual((call["params"]["page"], call["params"]["page_size"]), (2, 10))
        detail = storage.api.bk_base_v4.storage_asset_get.request(
            tenant="tenant_a", project_name="bk_project", sub_type="Redis", asset_name="shared_redis"
        )
        self.assertEqual(detail["resource_ns"], self.detail_ref)
        self.assertNotIn("project_name", self.calls[-1][2]["params"])

    def test_repeat_bound_request_returns_same_row_without_post_or_mask_reuse(self):
        first = self.create()
        second = self.create()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(len(self.posts()), 1)
        self.assertEqual(second.connection_info["password"], "synthetic_password")

    def test_changed_create_payload_does_not_mutate_existing_bound_registration(self):
        row = self.create()
        before = deepcopy(row.extra)
        self.data["connection_info"]["port"] = 6380
        with self.assertRaises(BKBaseResourceMappingError):
            self.create()
        self.assertEqual(len(self.posts()), 1)
        row.refresh_from_db()
        self.assertEqual(row.extra, before)
        self.assertEqual(row.connection_info["port"], 6379)

    def test_unbound_registration_is_not_available_for_redis_selection(self):
        self.detail_error = True
        with self.assertRaises(BKBaseResourceMappingError):
            self.create()
        System.objects.create(system_id="redis_system", namespace="audit_namespace")
        with self.assertRaises(BKBaseResourceMappingError):
            RedisHandler.pick_redis("redis_system")

    @override_settings(BKBASE_V4_NAMESPACE="")
    def test_missing_trusted_project_never_uses_frontend_audit_namespace(self):
        with self.assertRaises(BKBaseResourceMappingError):
            self.create()
        self.assertEqual(self.calls, [])
        self.assertFalse(RedisConfig.objects.exists())

    @override_settings(
        BK_RESOURCE={"PLATFORM_AUTH_ENABLED": False, "PLATFORM_AUTH_ACCESS_USERNAME": "synthetic_platform"}
    )
    def test_disabled_platform_auth_does_not_claim_caller_as_platform_admin(self):
        with self.assertRaises(BKBaseResourceMappingError):
            self.create()
        self.assertEqual(self.calls, [])
        self.assertFalse(RedisConfig.objects.exists())

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_handler_keeps_original_registration_and_admin(self):
        with mock.patch.object(storage.api.bk_base, "create_resource_set", return_value={}) as legacy:
            row = self.create()
        self.assertEqual(row.admin, ["synthetic_operator"])
        self.assertEqual(legacy.call_args.kwargs["resource_set_id"], self.data["redis_name_en"])
        self.assertFalse(legacy.call_args.kwargs["share"])
        self.assertEqual(legacy.call_args.kwargs["bk_username"], "synthetic_operator")
        self.assertEqual(self.calls, [])
