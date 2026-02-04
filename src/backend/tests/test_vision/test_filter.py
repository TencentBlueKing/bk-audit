# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
"""
from types import SimpleNamespace
from unittest import mock

from apps.meta.models import System
from core.exceptions import PermissionException
from services.web.vision.exceptions import SingleSystemDiagnosisSystemParamsError
from services.web.vision.handlers.filter import (
    DeptFilter,
    SingleSystemDiagnosisFilter,
    SystemDiagnosisFilter,
)
from tests.base import TestCase


class TestVisionFilters(TestCase):
    def setUp(self):
        super().setUp()
        self.system_a = System.objects.create(
            system_id="bk_a",
            namespace=self.namespace,
            name="Alpha",
            instance_id="inst_a",
        )
        self.system_b = System.objects.create(
            system_id="bk_b",
            namespace=self.namespace,
            name="Beta",
            instance_id="inst_b",
        )

    @mock.patch("services.web.vision.handlers.filter.Permission")
    @mock.patch("services.web.vision.handlers.filter.DeptConvertor.convert")
    @mock.patch("services.web.vision.handlers.filter.api.user_manage.list_user_departments")
    @mock.patch("services.web.vision.handlers.filter.get_local_request")
    def test_dept_filter_get_data_merges_sources(
        self,
        mock_get_request,
        mock_list_departments,
        mock_convert,
        mock_permission,
    ):
        mock_request = mock.Mock()
        mock_request.user.username = "tester"
        mock_get_request.return_value = mock_request
        mock_list_departments.return_value = [{"full_name": "DeptB"}]
        mock_permission.return_value.make_request.return_value = "req"
        mock_permission.return_value.iam_client._do_policy_query.return_value = {"op": "AND"}
        mock_convert.return_value = SimpleNamespace(value=["DeptA"])

        data = DeptFilter().get_data()

        self.assertEqual(
            data,
            [
                {"label": "DeptA", "value": "DeptA"},
                {"label": "DeptB", "value": "DeptB"},
            ],
        )

    @mock.patch.object(DeptFilter, "get_data", return_value=[{"label": "Dept", "value": "Dept"}])
    def test_dept_filter_check_data_returns_single_value(self, _):
        result = DeptFilter().check_data("Dept/Sub")
        self.assertEqual(result, "Dept/Sub")

    @mock.patch.object(DeptFilter, "get_data", return_value=[{"label": "Dept", "value": "Dept"}])
    def test_dept_filter_check_data_raises_without_permission(self, _):
        with self.assertRaises(PermissionException):
            DeptFilter().check_data(["OtherDept"])

    @mock.patch.object(SystemDiagnosisFilter, "_fetch_iam_permissions_systems")
    def test_system_diagnosis_filter_respects_limit(self, mock_fetch):
        mock_fetch.return_value = System.objects.all()
        data = SystemDiagnosisFilter().get_data(limit_systems=["bk_a"])
        self.assertEqual(data, [{"label": "Alpha", "value": "bk_a"}])

    @mock.patch.object(SystemDiagnosisFilter, "get_data")
    def test_system_diagnosis_filter_check_data_returns_authed(self, mock_get_data):
        mock_get_data.return_value = [
            {"label": "Alpha", "value": "bk_a"},
            {"label": "Beta", "value": "bk_b"},
        ]
        result = SystemDiagnosisFilter().check_data([])
        self.assertEqual(result, ["bk_a", "bk_b"])

    @mock.patch("services.web.vision.handlers.filter.Permission")
    @mock.patch.object(SystemDiagnosisFilter, "get_data", return_value=[{"label": "Alpha", "value": "bk_a"}])
    def test_system_diagnosis_filter_check_data_raises(self, _, mock_permission):
        mock_permission.return_value.get_apply_data.return_value = ({"apply": True}, "url")
        with self.assertRaises(PermissionException):
            SystemDiagnosisFilter().check_data(["bk_unknown"])

    def test_single_system_diagnosis_filter_requires_constants(self):
        filter_instance = SingleSystemDiagnosisFilter(vision_handler_params={})
        with self.assertRaises(SingleSystemDiagnosisSystemParamsError):
            filter_instance.get_data()

    @mock.patch.object(SystemDiagnosisFilter, "_fetch_iam_permissions_systems")
    def test_single_system_diagnosis_filter_filters_target(self, mock_fetch):
        mock_fetch.return_value = System.objects.all()
        filter_instance = SingleSystemDiagnosisFilter(
            vision_handler_params={"constants": {"system_id": "bk_a"}},
        )
        data = filter_instance.get_data()
        self.assertEqual(data, [{"label": "Alpha", "value": "bk_a"}])
