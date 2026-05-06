from unittest.mock import patch

from django.conf import settings
from django.test import TestCase

from services.web.scene.resources import GetScenePermissionSystems


class TestGetScenePermissionSystems(TestCase):
    """测试 GetScenePermissionSystems 资源类"""

    def setUp(self):
        self.resource = GetScenePermissionSystems()

    @patch("services.web.scene.resources.resource.meta.system_list_all")
    def test_perform_request_with_systems(self, mock_system_list_all):
        """测试通过 SystemListAllResource scope 获取系统列表"""
        mock_system_list_all.return_value = [
            {"system_id": "system1", "name": "系统1"},
            {"system_id": "system2", "name": "系统2"},
        ]

        result = self.resource.perform_request({"scene_id": 1})

        expected_result = [
            {"system_id": "system1", "system_name": "系统1"},
            {"system_id": "system2", "system_name": "系统2"},
        ]
        self.assertEqual(result, expected_result)
        mock_system_list_all.assert_called_once_with(
            namespace=settings.DEFAULT_NAMESPACE,
            scope_type="scene",
            scope_id="1",
        )

    @patch("services.web.scene.resources.resource.meta.system_list_all")
    def test_perform_request_no_systems(self, mock_system_list_all):
        """测试 scope 下无系统时返回空列表"""
        mock_system_list_all.return_value = []

        result = self.resource.perform_request({"scene_id": 99})

        self.assertEqual(result, [])
        mock_system_list_all.assert_called_once_with(
            namespace=settings.DEFAULT_NAMESPACE,
            scope_type="scene",
            scope_id="99",
        )

    @patch("services.web.scene.resources.resource.meta.system_list_all")
    def test_perform_request_scene_id_converted_to_str(self, mock_system_list_all):
        """测试 scene_id 被正确转换为字符串传入 scope_id"""
        mock_system_list_all.return_value = [
            {"system_id": "bk_cmdb", "name": "配置平台"},
        ]

        result = self.resource.perform_request({"scene_id": 42})

        self.assertEqual(result, [{"system_id": "bk_cmdb", "system_name": "配置平台"}])
        mock_system_list_all.assert_called_once_with(
            namespace=settings.DEFAULT_NAMESPACE,
            scope_type="scene",
            scope_id="42",
        )

    def test_request_serializer_validation(self):
        """测试请求序列化器验证"""
        serializer = self.resource.RequestSerializer(data={"scene_id": 1})
        self.assertTrue(serializer.is_valid())

        # 测试缺少必填字段
        serializer = self.resource.RequestSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("scene_id", serializer.errors)

    def test_response_serializer_structure(self):
        """测试响应序列化器结构"""
        serializer = self.resource.ResponseSerializer(data={"system_id": "test_system", "system_name": "测试系统"})
        self.assertTrue(serializer.is_valid())
