"""保留未配置采集项删除与 BKLog 异步软删除语义。"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from services.web.bkbase import clean
from services.web.bkbase.exceptions import (
    BKBaseResourceMappingError,
    BKBaseSharedResourceProtected,
)
from services.web.databus.collector.resources import DeleteCollectorResource
from services.web.databus.constants import SourcePlatformChoices
from services.web.databus.models import CollectorConfig


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class CollectorDeleteTests(TestCase):
    def make_collector(self, platform, binding=None, **kwargs):
        return CollectorConfig.objects.create(
            system_id="system_a",
            bk_biz_id=1,
            collector_plugin_id=1,
            collector_config_id=1,
            collector_config_name="source",
            source_platform=platform,
            bkbase_v4_resources=binding or {},
            **kwargs,
        )

    def test_unconfigured_bklog_delete_uses_resource_and_soft_deletes(self):
        owner = self.make_collector(SourcePlatformChoices.BKLOG)
        with mock.patch("bk_resource.api.bk_log.stop_subscription") as stop, mock.patch(
            "services.web.bkbase.clean.api.bk_base_v4.clean_get"
        ) as get:
            DeleteCollectorResource().request({"collector_config_id": owner.collector_config_id})
        self.assertTrue(CollectorConfig._objects.get(pk=owner.pk).is_deleted)
        get.assert_not_called()
        stop.assert_called_once()

    def test_dataid_only_bkbase_source_can_be_deleted_without_remote_clean(self):
        owner = self.make_collector(SourcePlatformChoices.BKBASE, {"data_id": {"name": "source_a"}})
        with mock.patch("services.web.bkbase.clean.api.bk_base_v4.clean_get") as get:
            result = clean.delete_collector(owner)
        self.assertTrue(result["deleted"])
        self.assertFalse(CollectorConfig._objects.filter(pk=owner.pk).exists())
        get.assert_not_called()

    def test_legacy_clean_without_v4_binding_stays_protected(self):
        owner = self.make_collector(
            SourcePlatformChoices.BKLOG, processing_id="legacy_clean", bkbase_table_id="legacy_rt"
        )
        with mock.patch("bk_resource.api.bk_log.stop_subscription") as stop:
            with self.assertRaises((BKBaseSharedResourceProtected, BKBaseResourceMappingError)):
                DeleteCollectorResource().request({"collector_config_id": owner.collector_config_id})
        self.assertFalse(CollectorConfig._objects.get(pk=owner.pk).is_deleted)
        stop.assert_not_called()

    def test_partial_existing_binding_is_not_treated_as_unconfigured(self):
        owner = self.make_collector(
            SourcePlatformChoices.BKBASE, {"clean_role": "existing", "clean_pending_create": True}
        )
        with self.assertRaises(BKBaseResourceMappingError):
            clean.delete_collector(owner)
        self.assertTrue(CollectorConfig.objects.filter(pk=owner.pk).exists())

    def test_owner_without_complete_reference_stays_protected(self):
        owner = self.make_collector(SourcePlatformChoices.BKLOG, {"clean_role": "owner"})
        with mock.patch("bk_resource.api.bk_log.stop_subscription") as stop:
            with self.assertRaises(BKBaseSharedResourceProtected):
                DeleteCollectorResource().request({"collector_config_id": owner.collector_config_id})
        stop.assert_not_called()

    def test_async_bklog_delete_keeps_soft_deleted_record(self):
        ref = {"kind": "Clean", "tenant": "tenant_a", "namespace": "audit", "name": "clean_a"}
        owner = self.make_collector(SourcePlatformChoices.BKLOG, {"clean": ref, "clean_role": "existing"})
        current = {
            "metadata": {"name": "clean_a"},
            "spec": {"desired_status": "Stopped", "current_status": "Stopped"},
            "status": {"phase": "Ok"},
        }
        with mock.patch("bk_resource.api.bk_log.stop_subscription"), mock.patch(
            "services.web.bkbase.clean.resource_lock"
        ), mock.patch("services.web.bkbase.clean.get_resource_or_none", return_value=current), mock.patch(
            "services.web.bkbase.clean.api.bk_base_v4.clean_delete"
        ):
            DeleteCollectorResource().request({"collector_config_id": owner.collector_config_id})
        self.assertTrue(CollectorConfig.objects.filter(pk=owner.pk).exists())
        with mock.patch("services.web.bkbase.clean.resource_lock"), mock.patch(
            "services.web.bkbase.clean.get_resource_or_none", return_value=None
        ):
            clean.poll_clean_operations()
        self.assertTrue(CollectorConfig._objects.get(pk=owner.pk).is_deleted)
        self.assertFalse(CollectorConfig.objects.filter(pk=owner.pk).exists())


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class CollectorDeleteGuardTests(SimpleTestCase):
    def test_invalid_existing_reference_is_rejected_before_stopping_bklog(self):
        references = [
            {},
            {"kind": "Clean", "tenant": "tenant_a", "namespace": "audit"},
            {"kind": "Clean", "tenant": "tenant_b", "namespace": "audit", "name": "clean_a"},
            {"kind": "DataSource", "tenant": "tenant_a", "namespace": "audit", "name": "clean_a"},
        ]
        for ref in references:
            with self.subTest(ref=ref):
                collector = SimpleNamespace(
                    collector_config_id=1,
                    processing_id=None,
                    bkbase_table_id=None,
                    bkbase_v4_resources={"clean_role": "existing", "clean": ref},
                )
                with mock.patch(
                    "services.web.databus.collector.resources.get_object_or_404", return_value=collector
                ), mock.patch("bk_resource.api.bk_log.stop_subscription") as stop:
                    with self.assertRaises(BKBaseResourceMappingError):
                        DeleteCollectorResource().request({"collector_config_id": 1})
                stop.assert_not_called()
