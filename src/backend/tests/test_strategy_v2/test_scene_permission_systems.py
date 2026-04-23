from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.meta.models import System
from services.web.scene.models import SceneSystem
from services.web.scene.resources import GetScenePermissionSystems


class TestGetScenePermissionSystems(TestCase):
    """测试 GetScenePermissionSystems 资源类"""

    def setUp(self):
        self.resource = GetScenePermissionSystems()

    @patch.object(System.objects, 'filter')
    @patch.object(SceneSystem.objects, 'filter')
    def test_perform_request_with_system_whitelist(self, mock_scene_filter, mock_system_filter):
        """测试场景配置了系统白名单的情况"""
        # SceneSystem 查询返回的 queryset mock
        mock_scene_qs = MagicMock()
        mock_scene_filter.return_value = mock_scene_qs
        # is_all_systems=True 不存在
        mock_scene_qs.filter.return_value.exists.return_value = False
        # values_list 返回系统ID列表
        mock_scene_qs.values_list.return_value = ['system1', 'system2']

        mock_system1 = MagicMock()
        mock_system1.system_id = 'system1'
        mock_system1.name = '系统1'
        mock_system2 = MagicMock()
        mock_system2.system_id = 'system2'
        mock_system2.name = '系统2'
        mock_system_filter.return_value = [mock_system1, mock_system2]

        result = self.resource.perform_request({'scene_id': 1})

        expected_result = [
            {'system_id': 'system1', 'system_name': '系统1'},
            {'system_id': 'system2', 'system_name': '系统2'},
        ]
        self.assertEqual(result, expected_result)
        mock_scene_filter.assert_called_once_with(scene_id=1)
        mock_system_filter.assert_called_once_with(system_id__in=['system1', 'system2'])

    @patch.object(System.objects, 'all')
    @patch.object(SceneSystem.objects, 'filter')
    def test_perform_request_with_all_systems(self, mock_scene_filter, mock_system_all):
        """测试场景配置了 is_all_systems=True 的情况，返回所有系统"""
        mock_scene_qs = MagicMock()
        mock_scene_filter.return_value = mock_scene_qs
        # is_all_systems=True 存在
        mock_scene_qs.filter.return_value.exists.return_value = True

        mock_system1 = MagicMock()
        mock_system1.system_id = 'system1'
        mock_system1.name = '系统1'
        mock_system2 = MagicMock()
        mock_system2.system_id = 'system2'
        mock_system2.name = '系统2'
        mock_system_all.return_value = [mock_system1, mock_system2]

        result = self.resource.perform_request({'scene_id': 1})

        expected_result = [
            {'system_id': 'system1', 'system_name': '系统1'},
            {'system_id': 'system2', 'system_name': '系统2'},
        ]
        self.assertEqual(result, expected_result)
        mock_scene_filter.assert_called_once_with(scene_id=1)
        mock_system_all.assert_called_once()

    @patch.object(SceneSystem.objects, 'filter')
    def test_perform_request_no_systems(self, mock_scene_filter):
        """测试场景没有配置任何系统的情况，返回空列表"""
        mock_scene_qs = MagicMock()
        mock_scene_filter.return_value = mock_scene_qs
        # is_all_systems=True 不存在
        mock_scene_qs.filter.return_value.exists.return_value = False
        # 没有配置任何系统
        mock_scene_qs.values_list.return_value = []

        result = self.resource.perform_request({'scene_id': 1})

        self.assertEqual(result, [])
        mock_scene_filter.assert_called_once_with(scene_id=1)

    def test_request_serializer_validation(self):
        """测试请求序列化器验证"""
        serializer = self.resource.RequestSerializer(data={'scene_id': 1})
        self.assertTrue(serializer.is_valid())

        # 测试缺少必填字段
        serializer = self.resource.RequestSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn('scene_id', serializer.errors)

    def test_response_serializer_structure(self):
        """测试响应序列化器结构"""
        serializer = self.resource.ResponseSerializer(data={'system_id': 'test_system', 'system_name': '测试系统'})
        self.assertTrue(serializer.is_valid())
