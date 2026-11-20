"""验证新 PULL 状态机制和敏感级别兼容。"""
from unittest import mock

import requests
from django.db import connection
from django.test import TransactionTestCase, override_settings

from apps.exceptions import SnapshotPreparingException
from apps.meta.models import ResourceType, System
from services.web.bkbase import source
from services.web.databus import tasks
from services.web.databus.collector.resources import ToggleJoinDataResource
from services.web.databus.collector.snapshot.join.http_pull import HttpPullHandler
from services.web.databus.constants import JoinDataType, SnapshotRunningStatus
from services.web.databus.models import Snapshot


@override_settings(
    BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="default", BKBASE_V4_NAMESPACE="project_a", HIGH_RISK_PORTS=[]
)
class SnapshotProvisioningTests(TransactionTestCase):
    def setUp(self):
        self.c24_guard = mock.patch.object(source, "require_new_pull_sensitivity")
        self.c24_guard.start()
        self.addCleanup(self.c24_guard.stop)

    def test_expired_claim_with_changed_config_finishes_without_retry(self):
        system = System.objects.create(
            system_id="expired_test", namespace="audit", callback_url="https://source.test", auth_token="synthetic"
        )
        resource_type = ResourceType.objects.create(
            system_id=system.system_id, resource_type_id="asset", unique_id="expired_test:asset", path="/resources"
        )
        snapshot = Snapshot.objects.create(
            system_id=system.system_id,
            resource_type_id="asset",
            join_data_type=JoinDataType.ASSET,
            status=SnapshotRunningStatus.PREPARING,
        )
        handler = HttpPullHandler(system, resource_type, snapshot, JoinDataType.ASSET)
        handler.update_or_create()
        binding = snapshot.bkbase_v4_resources.copy()
        binding["source_provision"] = {**binding["source_provision"], "stage": "conn_inflight", "claim_expires": 0}
        Snapshot.objects.filter(pk=snapshot.pk).update(bkbase_v4_resources=binding, pull_config={"period": 9})
        with mock.patch.object(source.api.bk_base_v4, "data_conn_create") as post:
            handler.advance_provision()
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.status, SnapshotRunningStatus.FAILED)
        self.assertEqual(snapshot.pull_config, {"period": 9})
        self.assertIn("outcome unknown", snapshot.status_msg)
        post.assert_not_called()

    def test_task_invalid_config_finishes_existing_intent_without_retry(self):
        system = System.objects.create(
            system_id="bad_config_test", namespace="audit", callback_url="https://source.test", auth_token="synthetic"
        )
        resource_type = ResourceType.objects.create(
            system_id=system.system_id, resource_type_id="asset", unique_id="bad_config_test:asset", path="/resources"
        )
        snapshot = Snapshot.objects.create(
            system_id=system.system_id,
            resource_type_id="asset",
            join_data_type=JoinDataType.ASSET,
            status=SnapshotRunningStatus.PREPARING,
        )
        handler = HttpPullHandler(system, resource_type, snapshot, JoinDataType.ASSET)
        handler.update_or_create()
        Snapshot.objects.filter(pk=snapshot.pk).update(pull_config={"period": "invalid"})
        with mock.patch("core.lock.CacheLock.locked", new_callable=mock.PropertyMock, return_value=False), mock.patch(
            "core.lock.CacheLock.release", return_value=True
        ), mock.patch.object(source.api.bk_base_v4, "data_conn_create") as post:
            tasks.start_snapshot.run()
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.status, SnapshotRunningStatus.FAILED)
        self.assertEqual(snapshot.pull_config, {"period": "invalid"})
        self.assertIn("inputs unavailable", snapshot.status_msg)
        post.assert_not_called()

    def test_task_invalid_context_finishes_existing_intent_without_recomputing_context(self):
        system = System.objects.create(
            system_id="bad_context_test", namespace="audit", callback_url="https://source.test", auth_token="synthetic"
        )
        resource_type = ResourceType.objects.create(
            system_id=system.system_id, resource_type_id="asset", unique_id="bad_context_test:asset", path="/resources"
        )
        snapshot = Snapshot.objects.create(
            system_id=system.system_id,
            resource_type_id="asset",
            join_data_type=JoinDataType.ASSET,
            status=SnapshotRunningStatus.PREPARING,
        )
        HttpPullHandler(system, resource_type, snapshot, JoinDataType.ASSET).update_or_create()
        operation = snapshot.bkbase_v4_resources["source_provision"].copy()
        with override_settings(BKBASE_V4_RESULT_TABLE_NAMESPACES="{invalid"), mock.patch(
            "core.lock.CacheLock.locked", new_callable=mock.PropertyMock, return_value=False
        ), mock.patch("core.lock.CacheLock.release", return_value=True), mock.patch.object(
            source.api.bk_base_v4, "data_conn_create"
        ) as post:
            tasks.start_snapshot.run()
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.status, SnapshotRunningStatus.FAILED)
        self.assertEqual(snapshot.bkbase_v4_resources["source_provision"], operation)
        post.assert_not_called()

    def test_real_entry_proceeds_past_source_sensitivity(self):
        system = System.objects.create(
            system_id="c24_test", namespace="audit", callback_url="https://source.test", auth_token="synthetic"
        )
        ResourceType.objects.create(
            system_id=system.system_id, resource_type_id="asset", unique_id="c24_test:asset", path="/resources"
        )
        snapshot = Snapshot.objects.create(
            system_id=system.system_id,
            resource_type_id="asset",
            join_data_type=JoinDataType.ASSET,
            status=SnapshotRunningStatus.PREPARING,
            pull_config={"sensitivity": "public"},
        )
        with mock.patch("core.lock.CacheLock.locked", new_callable=mock.PropertyMock, return_value=False), mock.patch(
            "core.lock.CacheLock.release", return_value=True
        ), mock.patch.object(
            source.api.bk_base_v4, "data_conn_create", side_effect=ValueError("synthetic failure")
        ) as conn, mock.patch.object(
            source.api.bk_base_v4, "data_source_create"
        ) as source_post:
            tasks.start_snapshot.run()
        snapshot.refresh_from_db()
        conn.assert_called_once()
        source_post.assert_not_called()
        self.assertEqual(snapshot.status, SnapshotRunningStatus.FAILED)
        self.assertNotIn("C24", snapshot.status_msg)

    def test_unknown_or_legacy_binding_cannot_use_c24_local_close(self):
        system = System.objects.create(
            system_id="no_guess", namespace="audit", callback_url="https://source.test", auth_token="synthetic"
        )
        ResourceType.objects.create(
            system_id=system.system_id, resource_type_id="asset", unique_id="no_guess:asset", path="/resources"
        )
        snapshot = Snapshot.objects.create(
            system_id=system.system_id,
            resource_type_id="asset",
            join_data_type=JoinDataType.ASSET,
            status=SnapshotRunningStatus.FAILED,
            bkbase_data_id=11,
        )
        with self.assertRaises(source.BKBaseResourceMappingError):
            ToggleJoinDataResource().request(system_id=system.system_id, resource_type_id="asset", is_enabled=False)
        snapshot.bkbase_data_id = None
        snapshot.bkbase_v4_resources = {"source_provision": {"stage": "source_inflight"}}
        snapshot.save(update_fields=["bkbase_data_id", "bkbase_v4_resources"])
        with self.assertRaises(source.BKBaseResourceMappingError):
            ToggleJoinDataResource().request(system_id=system.system_id, resource_type_id="asset", is_enabled=False)
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.status, SnapshotRunningStatus.FAILED)
        snapshot.status = SnapshotRunningStatus.PREPARING
        snapshot.bkbase_v4_resources = {}
        snapshot.save(update_fields=["status", "bkbase_v4_resources"])
        with self.assertRaises(SnapshotPreparingException):
            ToggleJoinDataResource().request(system_id=system.system_id, resource_type_id="asset", is_enabled=False)
        snapshot.status = SnapshotRunningStatus.FAILED
        snapshot.save(update_fields=["status"])
        snapshot.bkbase_data_id = 11
        snapshot.save(update_fields=["bkbase_data_id"])
        with override_settings(BKBASE_API_VERSION="v3"), mock.patch.object(source, "stop_collector") as legacy:
            self.assertTrue(source.stop_snapshot(snapshot, {"bkbase_data_id": 11}))
            legacy.assert_called_once_with(bkbase_data_id=11)

    def test_existing_unsubmitted_intent_proceeds_past_sensitivity(self):
        system = System.objects.create(
            system_id="c24_resume", namespace="audit", callback_url="https://source.test", auth_token="synthetic"
        )
        resource_type = ResourceType.objects.create(
            system_id=system.system_id, resource_type_id="asset", unique_id="c24_resume:asset", path="/resources"
        )
        snapshot = Snapshot.objects.create(
            system_id=system.system_id,
            resource_type_id="asset",
            join_data_type=JoinDataType.ASSET,
            status=SnapshotRunningStatus.PREPARING,
        )
        handler = HttpPullHandler(system, resource_type, snapshot, JoinDataType.ASSET)
        handler.update_or_create()
        with mock.patch.object(
            source.api.bk_base_v4, "data_conn_create", side_effect=RuntimeError("synthetic failure")
        ) as conn:
            with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
                handler.advance_provision()
            conn.assert_called_once()

    def test_unknown_source_write_is_never_adopted_or_reposted(self):
        system = System.objects.create(
            system_id="source_unknown_test",
            instance_id="source_unknown_test",
            namespace="audit",
            callback_url="https://source.test",
            auth_token="synthetic",
        )
        resource_type = ResourceType.objects.create(
            system_id=system.system_id,
            resource_type_id="asset",
            unique_id=system.system_id + ":asset",
            path="/resources",
        )
        snapshot = Snapshot.objects.create(
            system_id=system.system_id,
            resource_type_id="asset",
            join_data_type=JoinDataType.ASSET,
            status=SnapshotRunningStatus.PREPARING,
        )
        handler = HttpPullHandler(system, resource_type, snapshot, JoinDataType.ASSET)
        handler.update_or_create()
        operation = snapshot.bkbase_v4_resources["source_provision"]
        conn = {
            "kind": "DataConn",
            "metadata": {"tenant": "default", "namespace": "project_a", "name": operation["conn_name"]},
            "status": {"phase": "Ok"},
        }
        binding = snapshot.bkbase_v4_resources.copy()
        binding["source_provision"] = {**operation, "stage": "conn_accepted"}
        Snapshot.objects.filter(pk=snapshot.pk).update(bkbase_v4_resources=binding)
        with mock.patch.object(source.api.bk_base_v4, "data_conn_get", return_value=conn), mock.patch.object(
            source.api.bk_base_v4, "data_source_create", side_effect=requests.Timeout("unknown")
        ) as post:
            with self.assertRaises(requests.Timeout):
                handler.advance_provision()
            handler.advance_provision()
            snapshot.refresh_from_db()
            self.assertEqual(snapshot.status, SnapshotRunningStatus.PREPARING)
            self.assertNotIn("data_source", snapshot.bkbase_v4_resources)
            with mock.patch.object(source.time, "time", return_value=20000000000):
                handler.advance_provision()
            snapshot.refresh_from_db()
            self.assertEqual(snapshot.status, SnapshotRunningStatus.FAILED)
            self.assertNotIn("data_source", snapshot.bkbase_v4_resources)
            post.assert_called_once()

    def test_accepted_source_failed_or_drifted_remains_stoppable(self):
        for observed in ("Failed", "Running"):
            with self.subTest(observed=observed):
                system = System.objects.create(
                    system_id="stop_" + observed,
                    instance_id=observed,
                    namespace="audit",
                    callback_url="https://source.test",
                    auth_token="synthetic",
                )
                resource_type = ResourceType.objects.create(
                    system_id=system.system_id,
                    resource_type_id="asset",
                    unique_id=system.system_id + ":asset",
                    path="/resources",
                )
                snapshot = Snapshot.objects.create(
                    system_id=system.system_id,
                    resource_type_id="asset",
                    join_data_type=JoinDataType.ASSET,
                    status=SnapshotRunningStatus.PREPARING,
                )
                handler = HttpPullHandler(system, resource_type, snapshot, JoinDataType.ASSET)
                handler.update_or_create()
                operation = snapshot.bkbase_v4_resources["source_provision"]
                ref = {
                    "kind": "DataSource",
                    "tenant": "default",
                    "namespace": "project_a",
                    "name": operation["source_name"],
                }
                binding = snapshot.bkbase_v4_resources.copy()
                binding["data_source"] = ref
                binding["source_provision"] = {**operation, "stage": "source_accepted", "accepted_source": ref}
                Snapshot.objects.filter(pk=snapshot.pk).update(bkbase_v4_resources=binding)
                remote = {
                    "kind": "DataSource",
                    "metadata": {k: ref[k] for k in ("tenant", "namespace", "name")},
                    "spec": {"desired_status": "Stopped", "current_status": observed},
                    "status": {"phase": "Failed" if observed == "Failed" else "Ok"},
                }
                with mock.patch.object(source.api.bk_base_v4, "data_source_get", return_value=remote):
                    handler.advance_provision()
                snapshot.refresh_from_db()
                self.assertEqual(snapshot.status, SnapshotRunningStatus.FAILED)
                self.assertEqual(snapshot.bkbase_v4_resources["data_source"], ref)
                with mock.patch.object(
                    source, "stop_source", return_value={"ref": ref, "task_state": "stopped", "message": ""}
                ) as stop:
                    self.assertTrue(source.stop_snapshot(snapshot, {}))
                    self.assertEqual(stop.call_args.args[1], ref)

    def test_late_observer_exception_does_not_fail_advanced_stage(self):
        system = System.objects.create(
            system_id="observer_test", namespace="audit", callback_url="https://source.test", auth_token="synthetic"
        )
        resource_type = ResourceType.objects.create(
            system_id=system.system_id, resource_type_id="asset", unique_id="observer_test:asset", path="/resources"
        )
        snapshot = Snapshot.objects.create(
            system_id=system.system_id,
            resource_type_id="asset",
            join_data_type=JoinDataType.ASSET,
            status=SnapshotRunningStatus.PREPARING,
        )
        handler = HttpPullHandler(system, resource_type, snapshot, JoinDataType.ASSET)
        handler.update_or_create()
        operation = snapshot.bkbase_v4_resources["source_provision"].copy()
        binding = snapshot.bkbase_v4_resources.copy()
        binding["source_provision"] = {**operation, "stage": "source_accepted"}
        Snapshot.objects.filter(pk=snapshot.pk).update(bkbase_v4_resources=binding)
        source.fail_source_provision(snapshot, operation["operation_id"], "new", operation["digest"], handler.config)
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.status, SnapshotRunningStatus.PREPARING)
        self.assertEqual(snapshot.bkbase_v4_resources["source_provision"]["stage"], "source_accepted")

    def test_sensitivity_change_does_not_invalidate_new_intent(self):
        system = System.objects.create(
            system_id="sensitivity_test", namespace="audit", callback_url="https://source.test", auth_token="synthetic"
        )
        resource_type = ResourceType.objects.create(
            system_id=system.system_id, resource_type_id="asset", unique_id="sensitivity_test:asset", path="/resources"
        )
        snapshot = Snapshot.objects.create(
            system_id=system.system_id,
            resource_type_id="asset",
            join_data_type=JoinDataType.ASSET,
            status=SnapshotRunningStatus.PREPARING,
            pull_config={"sensitivity": "confidential"},
        )
        handler = HttpPullHandler(system, resource_type, snapshot, JoinDataType.ASSET)
        with mock.patch.object(source.api.bk_base_v4, "data_conn_create") as conn:
            handler.update_or_create()
            original = snapshot.bkbase_v4_resources["source_provision"].copy()
            snapshot.pull_config = {"sensitivity": "public"}
            snapshot.save(update_fields=["pull_config"])
            HttpPullHandler(system, resource_type, snapshot, JoinDataType.ASSET).update_or_create()
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.bkbase_v4_resources["source_provision"], original)
        conn.assert_not_called()

    def test_late_receipt_cannot_overwrite_closed_snapshot(self):
        system = System.objects.create(
            system_id="late_test", namespace="audit", callback_url="https://source.test", auth_token="synthetic"
        )
        resource_type = ResourceType.objects.create(
            system_id=system.system_id, resource_type_id="asset", unique_id="late_test:asset", path="/resources"
        )
        snapshot = Snapshot.objects.create(
            system_id=system.system_id,
            resource_type_id="asset",
            join_data_type=JoinDataType.ASSET,
            status=SnapshotRunningStatus.PREPARING,
        )
        handler = HttpPullHandler(system, resource_type, snapshot, JoinDataType.ASSET)
        handler.update_or_create()

        def late(**kwargs):
            self.assertFalse(connection.in_atomic_block)
            Snapshot.objects.filter(pk=snapshot.pk).update(status=SnapshotRunningStatus.CLOSED)
            return {"metadata": kwargs["metadata"], "spec": kwargs["spec"]}

        with mock.patch.object(source.api.bk_base_v4, "data_conn_create", side_effect=late):
            handler.advance_provision()
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.status, SnapshotRunningStatus.CLOSED)
        self.assertEqual(snapshot.bkbase_v4_resources["source_provision"]["stage"], "conn_inflight")

    def test_unknown_post_does_not_retry_and_finishes_failed(self):
        system = System.objects.create(
            system_id="unknown_test", namespace="audit", callback_url="https://source.test", auth_token="synthetic"
        )
        resource_type = ResourceType.objects.create(
            system_id=system.system_id, resource_type_id="asset", unique_id="unknown_test:asset", path="/resources"
        )
        snapshot = Snapshot.objects.create(
            system_id=system.system_id,
            resource_type_id="asset",
            join_data_type=JoinDataType.ASSET,
            status=SnapshotRunningStatus.PREPARING,
        )
        handler = HttpPullHandler(system, resource_type, snapshot, JoinDataType.ASSET)
        handler.update_or_create()
        with mock.patch.object(
            source.api.bk_base_v4, "data_conn_create", side_effect=requests.Timeout("unknown")
        ) as post:
            with self.assertRaises(requests.Timeout):
                handler.advance_provision()
            with mock.patch.object(source.time, "time", return_value=20000000000):
                handler.advance_provision()
            snapshot.refresh_from_db()
            self.assertEqual(snapshot.status, SnapshotRunningStatus.FAILED)
            self.assertEqual(post.call_count, 1)

    def test_task_polls_new_intent_without_invoking_clean(self):
        system = System.objects.create(
            system_id="task_test", namespace="audit", callback_url="https://source.test", auth_token="synthetic"
        )
        ResourceType.objects.create(
            system_id=system.system_id, resource_type_id="asset", unique_id="task_test:asset", path="/resources"
        )
        snapshot = Snapshot.objects.create(
            system_id=system.system_id,
            resource_type_id="asset",
            join_data_type=JoinDataType.ASSET,
            status=SnapshotRunningStatus.PREPARING,
        )

        def accepted(**kwargs):
            self.assertFalse(connection.in_atomic_block)
            return {"metadata": kwargs["metadata"], "spec": kwargs["spec"]}

        with mock.patch.object(source.api.bk_base_v4, "data_conn_create", side_effect=accepted) as post, mock.patch(
            "services.web.databus.collector.snapshot.join.base.BaseJoinDataHandler.create_data_etl"
        ) as clean, mock.patch(
            "core.lock.CacheLock.locked", new_callable=mock.PropertyMock, return_value=False
        ), mock.patch(
            "core.lock.CacheLock.release", return_value=True
        ):
            tasks.start_snapshot.run()
            snapshot.refresh_from_db()
            self.assertEqual(snapshot.status, SnapshotRunningStatus.PREPARING)
            self.assertEqual(snapshot.bkbase_v4_resources["source_provision"]["stage"], "conn_accepted")
            post.assert_called_once()
            clean.assert_not_called()

    def test_pull_handler_records_connection_intent_before_waiting_for_data_id(self):
        system = System.objects.create(
            system_id="provision_test", namespace="audit", callback_url="https://source.test", auth_token="synthetic"
        )
        resource_type = ResourceType.objects.create(
            system_id=system.system_id, resource_type_id="asset", unique_id="provision_test:asset", path="/resources"
        )
        snapshot = Snapshot.objects.create(
            system_id=system.system_id,
            resource_type_id="asset",
            join_data_type=JoinDataType.ASSET,
            status=SnapshotRunningStatus.PREPARING,
        )

        def accepted(**kwargs):
            self.assertFalse(connection.in_atomic_block)
            handler.advance_provision()
            return {"metadata": kwargs["metadata"], "spec": kwargs["spec"], "status": {"phase": "Pending"}}

        with mock.patch.object(
            source.api.bk_base_v4, "data_conn_create", side_effect=accepted
        ) as conn_post, mock.patch.object(
            source.api.bk_base_v4, "data_source_create", side_effect=accepted
        ) as source_post:
            handler = HttpPullHandler(system, resource_type, snapshot, JoinDataType.ASSET)
            self.assertIsNone(handler.update_or_create())
            snapshot.refresh_from_db()
            self.assertIsNone(snapshot.bkbase_data_id)
            self.assertEqual(snapshot.status, SnapshotRunningStatus.PREPARING)
            conn_post.assert_not_called()
            handler.advance_provision()
            conn_post.assert_called_once()
            source_post.assert_not_called()
            operation = snapshot.bkbase_v4_resources["source_provision"]
            conn_ref = {
                "kind": "DataConn",
                "tenant": "default",
                "namespace": "project_a",
                "name": operation["conn_name"],
            }
            src_ref = {
                "kind": "DataSource",
                "tenant": "default",
                "namespace": "project_a",
                "name": operation["source_name"],
            }
            conn = {
                "kind": "DataConn",
                "metadata": {k: conn_ref[k] for k in ("tenant", "namespace", "name")},
                "status": {"phase": "Ok"},
            }
            remote = {
                "kind": "DataSource",
                "metadata": {**{k: src_ref[k] for k in ("tenant", "namespace", "name")}, "labels": {}},
                "status": {"phase": "Pending"},
                "spec": {
                    "data_conn": conn_ref,
                    "desired_status": "Stopped",
                    "current_status": "Stopped",
                    "data_id": {"kind": "DataId", "tenant": "", "namespace": "", "name": ""},
                },
            }
            with mock.patch.object(source.api.bk_base_v4, "data_conn_get", return_value=conn), mock.patch.object(
                source.api.bk_base_v4, "data_source_get", return_value=remote
            ):
                handler.advance_provision()
                source_post.assert_called_once()
                remote["spec"]["report_config"] = source_post.call_args.kwargs["spec"]["report_config"]
                snapshot.refresh_from_db()
                self.assertEqual(snapshot.bkbase_v4_resources["data_source"], src_ref)
                handler.advance_provision()
                snapshot.refresh_from_db()
                self.assertIsNone(snapshot.bkbase_data_id)
                remote["status"]["phase"] = "Ok"
                remote["metadata"]["labels"]["raw_data_id"] = "123"
                handler.advance_provision()
                snapshot.refresh_from_db()
                self.assertIsNone(snapshot.bkbase_data_id)
                remote["spec"]["data_id"] = {
                    "kind": "DataId",
                    "tenant": "default",
                    "namespace": "other",
                    "name": "data_a",
                }
                for invalid in ("0", "-1", "not-a-number"):
                    remote["metadata"]["labels"]["raw_data_id"] = invalid
                    handler.advance_provision()
                    snapshot.refresh_from_db()
                    self.assertIsNone(snapshot.bkbase_data_id)
                remote["metadata"]["labels"]["raw_data_id"] = "123"
                handler.advance_provision()
                snapshot.refresh_from_db()
                self.assertEqual(snapshot.bkbase_data_id, 123)
                self.assertEqual(snapshot.status, SnapshotRunningStatus.PREPARING)
                self.assertEqual(snapshot.bkbase_v4_resources["data_id"], remote["spec"]["data_id"])
                handler.update_or_create()
                self.assertEqual(conn_post.call_count, 1)
                self.assertEqual(source_post.call_count, 1)
                handler.advance_provision()
                snapshot.refresh_from_db()
                self.assertEqual(snapshot.status, SnapshotRunningStatus.PREPARING)
                self.assertEqual(conn_post.call_count, 1)
                self.assertEqual(source_post.call_count, 1)
