# -*- coding: utf-8 -*-
from iam.eval.constants import KEYWORD_BK_IAM_PATH
from rest_framework.test import APIRequestFactory

from apps.notice.models import NoticeGroup
from apps.notice.views import NoticeGroupsViewSet
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import InstanceActionPermission
from apps.permission.handlers.resource_types import ResourceEnum
from services.web.scene.constants import ResourceVisibilityType
from services.web.scene.filters import BindingMetadataHelper
from services.web.scene.models import Scene
from tests.base import TestCase


class TestNoticeGroupViewPermissions(TestCase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.view = NoticeGroupsViewSet()

    def test_get_permissions_list_uses_scene_permission(self):
        request = self.factory.get("/notice_group/", {"scene_id": 1})
        self.view.request = request
        self.view.kwargs = {}
        self.view.action = "list"

        permissions = self.view.get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], InstanceActionPermission)
        self.assertEqual(permissions[0].actions, [ActionEnum.LIST_NOTICE_GROUP])

    def test_get_scene_id_by_notice_group_supports_path_group_id(self):
        scene = Scene.objects.create(
            name="notice-scene-detail",
            description="scene detail",
        )
        notice_group = NoticeGroup.objects.create(
            group_name="notice-group-detail",
            group_member=["admin"],
            notice_config=[],
        )
        BindingMetadataHelper.create_resource_binding(
            resource_id=str(notice_group.group_id),
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            scene_id=scene.scene_id,
        )

        request = self.factory.get(f"/notice_group/{notice_group.group_id}/")
        request.parser_context = {"kwargs": {"group_id": str(notice_group.group_id)}}
        self.view.request = request

        self.assertEqual(self.view.get_scene_id_by_notice_group(), scene.scene_id)

    def test_notice_group_batch_create_instance_includes_iam_path(self):
        scene = Scene.objects.create(
            name="notice-scene-batch",
            description="scene batch",
        )
        notice_group = NoticeGroup.objects.create(
            group_name="notice-group-batch",
            group_member=["admin"],
            notice_config=[],
        )
        BindingMetadataHelper.create_resource_binding(
            resource_id=str(notice_group.group_id),
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            scene_id=scene.scene_id,
        )

        resources = ResourceEnum.NOTICE_GROUP.batch_create_instance([notice_group.group_id])

        self.assertEqual(resources[0][0].attribute[KEYWORD_BK_IAM_PATH], f"/scene,{scene.scene_id}/")


class TestListAllNoticeGroup(TestCase):
    def setUp(self):
        super().setUp()
        self.scene_1 = Scene.objects.create(
            name="notice-scene-1",
            description="scene 1",
        )
        self.scene_2 = Scene.objects.create(
            name="notice-scene-2",
            description="scene 2",
        )

    def test_list_all_notice_group_only_returns_target_scene_groups(self):
        notice_group_1 = NoticeGroup.objects.create(
            group_name="notice-group-scene-1",
            group_member=["admin"],
            notice_config=[],
        )
        notice_group_2 = NoticeGroup.objects.create(
            group_name="notice-group-scene-2",
            group_member=["admin"],
            notice_config=[],
        )
        NoticeGroup.objects.create(
            group_name="notice-group-unbound",
            group_member=["admin"],
            notice_config=[],
        )

        BindingMetadataHelper.create_resource_binding(
            resource_id=str(notice_group_1.group_id),
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            scene_id=self.scene_1.scene_id,
        )
        BindingMetadataHelper.create_resource_binding(
            resource_id=str(notice_group_2.group_id),
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            scene_id=self.scene_2.scene_id,
        )

        result = self.resource.notice.list_all_notice_group.request({"scene_id": self.scene_1.scene_id})
        group_ids = [item["id"] for item in result]

        self.assertIn(notice_group_1.group_id, group_ids)
        self.assertNotIn(notice_group_2.group_id, group_ids)
