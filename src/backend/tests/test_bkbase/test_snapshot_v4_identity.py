"""完整 V4 Snapshot 身份与在途摘要的纯边界回归。"""
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from services.web.bkbase import source
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.constants import SnapshotRunningStatus


class SnapshotV4IdentityTests(SimpleTestCase):
    def setUp(self):
        def ref(kind, name):
            return {"kind": kind, "tenant": "default", "namespace": "audit", "name": name}

        self.context = {"tenant": "default", "namespace": "audit"}
        self.binding = {
            "data_source": ref("DataSource", "source"),
            "data_id": ref("DataId", "data"),
            "clean": ref("Clean", "clean"),
            "clean_role": "owner",
            "result_table_id": "71_rt",
            "result_table": ref("ResultTable", "rt"),
            "storages": {"redis": ref("DataStorage", "redis")},
        }
        self.snapshot = SimpleNamespace(
            pk=1,
            system_id="synthetic",
            resource_type_id="asset",
            join_data_type="basic",
            bkbase_data_id=71,
            bkbase_processing_id=None,
            bkbase_table_id="71_rt",
            bkbase_v4_resources=self.binding,
            pull_type="partial",
            pull_config={"sensitivity": "private", "keep": 1},
            custom_config={},
            storages=SimpleNamespace(values_list=lambda *a: [("redis", SnapshotRunningStatus.RUNNING)]),
        )
        self.params = {"access_raw_data": {"sensitivity": "private", "keep": 1}, "keep": 1}
        snapshots = self.enterContext(mock.patch.object(source.Snapshot.objects, "filter"))
        snapshots.return_value.exclude.return_value.exists.return_value = False
        systems = self.enterContext(mock.patch.object(source.System.objects, "filter"))
        systems.return_value.values.return_value.first.return_value = {
            "callback_url": "https://source.invalid",
            "auth_token": "synthetic",
            "namespace": "audit",
        }
        resources = self.enterContext(mock.patch.object(source.ResourceType.objects, "filter"))
        resources.return_value.values.return_value.first.return_value = {"path": "/objects"}

    def test_complete_v4_inputs_keep_exact_old_digest_shape_and_raw_legacy_values(self):
        # Frozen hashes from the explicitly specified input contract, including legacy_ids.
        cases = [
            ('basic', False, None, False, 'aa4f1c08abc28d0911414e2e3966483d95cd3f780fde2f6e0553bfdce6457b4b'),
            ('basic', False, '', False, '2bd9cf46737a7639aab4b2620279270212b309451aed01f346607e4639a8775a'),
            ('basic', False, 'legacy_a', False, '844ad31e5336c172fb8c73f4fe533e0e42777853cfd554f52dd11d319e9f86c7'),
            ('basic', False, 'legacy_a', True, '8247a31563db8656035dea98d34df9e97a765fc27b74708d0b77d2e3a4b63ced'),
            ('basic', True, None, False, '3a819c794f4e8170f110faedd9355970b4233c7e4a8a41d02f80bef33f04d49d'),
            ('basic', True, '', False, '8f108c5675f7faa4dd526f1f9af948c56adee32695a92d79ce2b484a1887614e'),
            ('basic', True, 'legacy_a', False, '4b15e1f8596dccd8fef5730c48e03e4102f96584622c396b6ea70f554f27ac1a'),
            ('basic', True, 'legacy_a', True, '00dd3a469f6240cf44c6ee56f39e799d4dcc6efdd677c9dc0434457796de3d97'),
            ('asset', True, None, False, '0d63b352823401a3677e5d2f3e55a53c247d5c1e0c3dcc07d1ee07c6777570a4'),
            ('asset', True, '', False, '4f0c0b0891b450153de5e612a48cbc29da5ad9599fc83c282477ce35b300a0f4'),
            ('asset', True, 'legacy_a', False, '1cb195837076b1345f731b005a119b391ee25c909bcc8a15f3e95efe35b10908'),
            ('asset', True, 'legacy_a', True, '402565fbc8791dbc8c1ca6148544a16fd39f6ce5b380c24c654773b320737efe'),
        ]
        original_binding = deepcopy(self.binding)
        for join, restore, pid, legacy, expected in cases:
            with self.subTest(join=join, restore=restore, pid=pid, legacy=legacy):
                self.snapshot.join_data_type = join
                self.snapshot.bkbase_processing_id = pid
                try:
                    digest = source._replay_inputs(
                        self.snapshot, self.params, self.context, restore=restore, legacy=legacy
                    )
                except BKBaseResourceMappingError:
                    self.fail("Complete explicit V4 binding was rejected solely because its legacy PID is absent")
                self.assertEqual(digest, expected)
                self.assertEqual(self.snapshot.bkbase_processing_id, pid)
                self.assertEqual(self.binding, original_binding)

    def test_complete_binding_does_not_accept_invalid_nonempty_legacy_identity(self):
        for pid in (False, 1, " ", "legacy,b", "legacy=b"):
            self.snapshot.bkbase_processing_id = pid
            with self.subTest(pid=pid), self.assertRaises(BKBaseResourceMappingError):
                source._replay_inputs(self.snapshot, self.params, self.context)

    def test_missing_refs_role_raw_or_pending_creation_cannot_use_optional_pid(self):
        for key, value in (
            ("clean", None),
            ("clean_role", "unknown"),
            ("raw_data_id", 72),
            ("clean_pending_create", True),
        ):
            self.snapshot.bkbase_processing_id = "legacy_a" if key == "clean_pending_create" else None
            self.snapshot.bkbase_v4_resources = {**self.binding, key: value}
            with self.subTest(key=key), self.assertRaises(BKBaseResourceMappingError):
                source._replay_inputs(self.snapshot, self.params, self.context)

    def test_clean_labels_absent_or_matching_are_valid_without_inventing_processing_id(self):
        for pid in (None, ""):
            self.snapshot.bkbase_processing_id = pid
            for labels in ({}, {"raw_data_id": "71", "result_table_id": "71_rt"}):
                resource = {"metadata": {"labels": deepcopy(labels)}}
                before = deepcopy(resource)
                self.assertTrue(source._snapshot_clean_identity_matches(self.snapshot, resource))
                self.assertEqual(resource, before)
                self.assertEqual(self.snapshot.bkbase_processing_id, pid)

    def test_clean_known_pid_missing_or_conflicting_identity_labels_are_rejected(self):
        self.snapshot.bkbase_processing_id = "legacy_a"
        self.assertTrue(
            source._snapshot_clean_identity_matches(
                self.snapshot, {"metadata": {"labels": {"processing_id": "legacy_a"}}}
            )
        )
        for labels in (
            {},
            {"processing_id": None},
            {"processing_id": "other"},
            {"processing_id": "legacy_a", "raw_data_id": "72"},
            {"processing_id": "legacy_a", "raw_data_id": 71},
            {"processing_id": "legacy_a", "result_table_id": "other"},
        ):
            with self.subTest(labels=labels):
                self.assertFalse(
                    source._snapshot_clean_identity_matches(self.snapshot, {"metadata": {"labels": labels}})
                )

    def test_clean_optional_pid_does_not_ignore_existing_identity_label_conflicts(self):
        for pid in (None, ""):
            self.snapshot.bkbase_processing_id = pid
            for labels in (
                None,
                {"raw_data_id": "72"},
                {"raw_data_id": 71},
                {"result_table_id": "other"},
                {"result_table_id": None},
            ):
                with self.subTest(pid=pid, labels=labels):
                    self.assertFalse(
                        source._snapshot_clean_identity_matches(self.snapshot, {"metadata": {"labels": labels}})
                    )

    def test_unbound_legacy_discovery_still_requires_actual_legacy_pid(self):
        for pid in (None, ""):
            self.snapshot.bkbase_processing_id = pid
            with self.subTest(pid=pid), self.assertRaises(BKBaseResourceMappingError):
                source._discover_snapshot_binding(self.snapshot, self.context, {"redis"})
