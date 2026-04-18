# -*- coding: utf-8 -*-
from django.test import TestCase

from services.web.vision.serializers import (
    DeleteSceneReportGroupRequestSerializer,
    PlatformPanelListQuerySerializer,
    SceneReportGroupOrderRequestSerializer,
    SceneReportGroupPanelOrderRequestSerializer,
)


class TestSceneReportGroupSerializers(TestCase):
    def test_platform_panel_list_query_with_paginate(self):
        serializer = PlatformPanelListQuerySerializer(
            data={
                "enable_paginate": True,
                "page": 1,
                "page_size": 20,
                "status": "published",
                "name": "审计",
                "description": "平台",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_group_order_serializer(self):
        serializer = SceneReportGroupOrderRequestSerializer(
            data={"scene_id": 100001, "groups": [{"group_id": 1, "priority_index": 10}]}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_group_panel_order_serializer(self):
        serializer = SceneReportGroupPanelOrderRequestSerializer(
            data={
                "scene_id": 100001,
                "items": [
                    {"panel_id": "p1", "group_id": 1, "priority_index": 9},
                    {"panel_id": "p2", "group_id": 1, "priority_index": 8},
                ],
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_delete_group_serializer(self):
        serializer = DeleteSceneReportGroupRequestSerializer(data={"scene_id": 100001, "group_id": 1})
        self.assertTrue(serializer.is_valid(), serializer.errors)
