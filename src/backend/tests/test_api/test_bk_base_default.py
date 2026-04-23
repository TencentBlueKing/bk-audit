# -*- coding: utf-8 -*-
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase
from django.test.utils import override_settings

from api.bk_base.constants import UserAuthActionEnum
from api.bk_base.default import ProjectDataBatchAdd, ProjectDataBatchCheck
from api.bk_base.serializers import (
    GetMineResultTablesReqSerializer,
    ProjectDataBatchAddReqSerializer,
    ProjectDataBatchCheckReqSerializer,
)


def expected_project_id():
    return int(settings.BKBASE_PROJECT_ID)


@override_settings(BKBASE_PROJECT_ID="591")
class TestProjectDataBatchCheckReqSerializer(SimpleTestCase):
    def test_should_fill_default_project_id(self):
        object_id = "mock_rt_7f3a9c2d"
        serializer = ProjectDataBatchCheckReqSerializer(
            data={
                "action_id": UserAuthActionEnum.RT_QUERY,
                "object_ids": [object_id],
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["project_id"], expected_project_id())
        self.assertEqual(serializer.validated_data["action_id"], UserAuthActionEnum.RT_QUERY)


@override_settings(BKBASE_PROJECT_ID="591")
class TestProjectDataBatchAddReqSerializer(SimpleTestCase):
    def test_should_fill_default_project_and_biz_id(self):
        serializer = ProjectDataBatchAddReqSerializer(data={"object_ids": ["11_hltest"]})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["project_id"], expected_project_id())
        self.assertEqual(serializer.validated_data["bk_biz_id"], settings.DEFAULT_BK_BIZ_ID)


class TestGetMineResultTablesReqSerializer(SimpleTestCase):
    def test_should_fill_default_action_and_biz_id(self):
        serializer = GetMineResultTablesReqSerializer(data={"bk_username": "tester"})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["bk_username"], "tester")
        self.assertEqual(serializer.validated_data["action_id"], UserAuthActionEnum.RT_QUERY)
        self.assertEqual(serializer.validated_data["bk_biz_id"], settings.DEFAULT_BK_BIZ_ID)


@override_settings(BKBASE_PROJECT_ID="591")
class TestProjectDataBatchCheckResource(SimpleTestCase):
    @mock.patch.object(ProjectDataBatchCheck, "build_header", return_value={})
    def test_request_should_validate_and_parse_response(self, _mock_build_header):
        resource = ProjectDataBatchCheck()
        permitted_object_id = "mock_rt_7f3a9c2d"
        denied_object_id = "mock_rt_b18e4f6a"
        mock_response = mock.MagicMock()
        mock_response.json.return_value = {
            "result": True,
            "data": {
                "permissions": [permitted_object_id],
                "no_permissions": [denied_object_id],
            },
            "code": "1500200",
            "message": "ok",
            "errors": None,
        }
        mock_response.raise_for_status.return_value = None
        mock_response.request.url = "http://bkbase.test"
        resource.session.request = mock.Mock(return_value=mock_response)

        result = resource.request(
            {
                "action_id": UserAuthActionEnum.RT_QUERY,
                "object_ids": [
                    permitted_object_id,
                    denied_object_id,
                ],
            }
        )

        self.assertEqual(
            result,
            {
                "permissions": [permitted_object_id],
                "no_permissions": [denied_object_id],
            },
        )
        kwargs = resource.session.request.call_args.kwargs
        self.assertTrue(kwargs["url"].endswith(f"/v3/auth/projects/{settings.BKBASE_PROJECT_ID}/data/batch_check/"))
        self.assertEqual(kwargs["json"]["project_id"], expected_project_id())
        self.assertEqual(kwargs["json"]["action_id"], UserAuthActionEnum.RT_QUERY)


@override_settings(BKBASE_PROJECT_ID="591")
class TestProjectDataBatchAddResource(SimpleTestCase):
    @mock.patch.object(ProjectDataBatchAdd, "build_header", return_value={})
    def test_request_should_validate_and_parse_response(self, _mock_build_header):
        resource = ProjectDataBatchAdd()
        mock_response = mock.MagicMock()
        mock_response.json.return_value = {
            "result": True,
            "data": "ok",
            "code": "1500200",
            "message": "ok",
            "errors": None,
        }
        mock_response.raise_for_status.return_value = None
        mock_response.request.url = "http://bkbase.test"
        resource.session.request = mock.Mock(return_value=mock_response)

        result = resource.request({"object_ids": ["11_hltest"]})

        self.assertEqual(result, "ok")
        kwargs = resource.session.request.call_args.kwargs
        self.assertTrue(kwargs["url"].endswith(f"/v3/auth/projects/{settings.BKBASE_PROJECT_ID}/data/batch_add/"))
        self.assertEqual(kwargs["json"]["project_id"], expected_project_id())
        self.assertEqual(kwargs["json"]["bk_biz_id"], settings.DEFAULT_BK_BIZ_ID)
        self.assertEqual(kwargs["json"]["object_ids"], ["11_hltest"])


class TestGetMineResultTablesResource(SimpleTestCase):
    def test_should_disable_platform_authorization(self):
        from api.bk_base.default import GetMineResultTables

        self.assertFalse(GetMineResultTables.platform_authorization)

    @mock.patch("api.bk_base.default.BkBaseResource.build_header", return_value={})
    def test_request_should_validate_and_parse_response(self, _mock_build_header):
        from api.bk_base.default import GetMineResultTables

        resource = GetMineResultTables()
        result_table_id = "mock_rt_a92f4c1e"
        mock_response = mock.MagicMock()
        mock_response.json.return_value = {
            "result": True,
            "data": [
                {
                    "result_table_id": result_table_id,
                    "result_table_name": "mock_rt_name",
                    "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
                    "project_id": settings.BKBASE_PROJECT_ID,
                }
            ],
            "code": "1500200",
            "message": "ok",
            "errors": None,
        }
        mock_response.raise_for_status.return_value = None
        mock_response.request.url = "http://bkbase.test"
        resource.session.get = mock.Mock(return_value=mock_response)

        result = resource.request({"bk_username": "tester"})

        self.assertEqual(
            result,
            [
                {
                    "result_table_id": result_table_id,
                    "result_table_name": "mock_rt_name",
                    "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
                    "project_id": settings.BKBASE_PROJECT_ID,
                }
            ],
        )
        kwargs = resource.session.get.call_args.kwargs
        self.assertEqual(kwargs["params"]["bk_username"], "tester")
        self.assertEqual(kwargs["params"]["action_id"], UserAuthActionEnum.RT_QUERY)
        self.assertEqual(kwargs["params"]["bk_biz_id"], settings.DEFAULT_BK_BIZ_ID)
        self.assertTrue(resource.session.get.call_args.args[0].endswith("/v3/meta/result_tables/mine/"))
