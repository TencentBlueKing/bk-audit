"""项目别名来自同一次正式目录响应，不改变权限与逻辑标识。"""
import json
from unittest import mock
from urllib.parse import urlparse

from bk_resource.exceptions import ValidateException
from django.test import SimpleTestCase, override_settings

from services.web.bkbase import permissions
from services.web.strategy_v2 import resources
from tests.test_bkbase import test_list_performance as fixtures


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="tenant_a",
    BKBASE_V4_NAMESPACE="audit",
    BKBASE_V4_RESULT_TABLE_NAMESPACES={},
    APP_CODE="synthetic_app",
    SECRET_KEY="synthetic_secret",
    PLATFORM_AUTH_ACCESS_USERNAME="synthetic_admin",
    BK_RESOURCE={
        "PLATFORM_AUTH_ENABLED": True,
        "PLATFORM_AUTH_ACCESS_USERNAME": "synthetic_admin",
        "PLATFORM_AUTH_ACCESS_TOKEN": "synthetic_platform_token",
    },
)
class ProjectAliasTests(SimpleTestCase):
    rt_id = staticmethod(fixtures.ListPerformanceTests.rt_id)
    row = fixtures.ListPerformanceTests.row
    result_table = fixtures.ListPerformanceTests.result_table

    def setUp(self):
        fixtures.ListPerformanceTests.setUp(self)
        self.aliases = {}
        self.enterContext(mock.patch.object(permissions, "get_request_username", return_value="user_a"))

    def transport(self, method, url, **kwargs):
        response = fixtures.ListPerformanceTests.transport(self, method, url, **kwargs)
        if urlparse(url).path.endswith('/namespaces'):
            payload = json.loads(response.content)
            for row in payload['data']:
                name = row['metadata']['name']
                if name in self.aliases:
                    row['spec']['alias'] = self.aliases[name]
            response._content = json.dumps(payload).encode()
        return response

    def test_alias_label_and_fallbacks_use_one_authoritative_directory_call(self):
        self.projects = ['default_47', 'missing', 'blank', 'null', 'same', 'empty']
        self.aliases = {'default_47': '  蓝鲸审计中心  ', 'blank': '  ', 'null': None, 'same': 'same', 'empty': ''}
        for table_type, expected_kind in [
            ('MineBizRt', 'UserNamespacesList'),
            ('BizRt', 'NamespacesList'),
            ('BuildIn', 'NamespacesList'),
        ]:
            self.calls.clear()
            with mock.patch.object(resources.ListTableProjects, '_need_cache_wrap', return_value=False):
                result = resources.ListTableProjects().request(namespace='default', table_type=table_type)
            self.assertEqual(
                result,
                [
                    dict(
                        label='蓝鲸审计中心（default_47）' if n == 'default_47' else n,
                        value=n,
                        namespace=n,
                        node_type='project',
                        leaf=False,
                    )
                    for n in sorted(self.projects)
                ],
            )
            self.assertEqual([c['kind'] for c in self.calls], [expected_kind])

    def test_legacy_project_identity_lists_are_unchanged(self):
        self.projects = ['project_999', 'shared']
        self.aliases = {'project_999': '中文项目'}
        self.assertEqual(permissions.list_projects(), self.projects)
        self.assertEqual(permissions.list_user_projects(), self.projects)
        self.assertEqual([c['kind'] for c in self.calls], ['NamespacesList', 'UserNamespacesList'])

    def test_alias_never_becomes_a_namespace_or_changes_personal_table_lookup(self):
        self.projects = ['project_999']
        self.aliases = {'project_999': '中文项目'}
        self.rows['project_999'] = [self.row(0)]
        with mock.patch.object(resources.ListProjectTables, '_need_cache_wrap', return_value=False):
            data = resources.ListProjectTables().request(
                namespace='default', table_type='MineBizRt', bkbase_namespace='project_999'
            )
            self.assertEqual([r['value'] for r in data], [self.rt_id(0)])
            before = len(self.calls)
            with self.assertRaises(ValidateException):
                resources.ListProjectTables().request(
                    namespace='default', table_type='MineBizRt', bkbase_namespace='中文项目（project_999）'
                )
            self.assertEqual(len(self.calls), before)
        self.assertEqual([c['kind'] for c in self.calls], ['UserNamespacesList', 'UserDatasetList'])
