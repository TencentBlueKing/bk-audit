# -*- coding: utf-8 -*-
from unittest import mock

from django.test import SimpleTestCase

from api.bk_itsm_v4.default import SystemWorkflowList


def _mock_response(data):
    response = mock.MagicMock()
    response.json.return_value = {"data": data, "request_id": "request-id"}
    response.raise_for_status.return_value = None
    response.request.url = "http://bkitsm.test"
    return response


class TestSystemWorkflowListBuildHeader(SimpleTestCase):
    @mock.patch("api.bk_itsm_v4.default.get_itsm_v4_system_token", return_value="")
    def test_build_header_without_token_keeps_parent_headers(self, _mock_token):
        resource = SystemWorkflowList()

        headers = resource.build_header({})

        # 平台鉴权头由父类注入，未配置 system_token 时不加 SYSTEM-TOKEN
        self.assertNotIn("SYSTEM-TOKEN", headers)

    @mock.patch("api.bk_itsm_v4.default.get_itsm_v4_system_token", return_value="global-system-token")
    def test_build_header_uses_global_token(self, _mock_token):
        resource = SystemWorkflowList()

        headers = resource.build_header({})

        self.assertEqual(headers["SYSTEM-TOKEN"], "global-system-token")

    @mock.patch("api.bk_itsm_v4.default.get_itsm_v4_system_token", return_value="global-system-token")
    def test_build_header_request_token_overrides_global(self, _mock_token):
        resource = SystemWorkflowList()

        headers = resource.build_header({"system_token": "request-system-token"})

        self.assertEqual(headers["SYSTEM-TOKEN"], "request-system-token")


class TestSystemWorkflowListRequest(SimpleTestCase):
    @mock.patch("api.bk_itsm_v4.default.get_itsm_v4_system_token", return_value="global-system-token")
    def test_request_sends_system_token_header(self, _mock_token):
        resource = SystemWorkflowList()
        resource.session.request = mock.Mock(return_value=_mock_response({"count": 0, "items": []}))

        resource.request({})

        kwargs = resource.session.request.call_args.kwargs
        self.assertEqual(kwargs["headers"]["SYSTEM-TOKEN"], "global-system-token")

    @mock.patch("api.bk_itsm_v4.default.get_itsm_v4_system_token", return_value="")
    def test_request_without_token_has_no_system_token_header(self, _mock_token):
        resource = SystemWorkflowList()
        resource.session.request = mock.Mock(return_value=_mock_response({"count": 0, "items": []}))

        resource.request({})

        kwargs = resource.session.request.call_args.kwargs
        self.assertNotIn("SYSTEM-TOKEN", kwargs["headers"])
