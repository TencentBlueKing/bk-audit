# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import uuid
from types import SimpleNamespace

from django.http import Http404
from rest_framework.permissions import IsAuthenticated

from apps.meta.exceptions import TagNameInValid
from apps.meta.models import Tag
from apps.meta.views.tag_views import TagBindingsViewSet
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import IAMPermission, InstanceActionPermission
from services.web.scene.constants import BindingType, ResourceVisibilityType
from services.web.scene.models import ResourceBinding, ResourceBindingScene, Scene
from services.web.strategy_v2.models import (
    LinkTable,
    LinkTableTag,
    Strategy,
    StrategyTag,
)
from services.web.tool.constants import ToolTypeEnum
from services.web.tool.models import Tool, ToolTag
from tests.base import TestCase


class TagBindingsTest(TestCase):
    def setUp(self):
        self.namespace = "default"
        self.other_namespace = "other"
        self.strategy = Strategy.objects.create(namespace=self.namespace, strategy_name="strategy-one")
        self.link_table = LinkTable.objects.create(
            namespace=self.namespace,
            uid=str(uuid.uuid4()),
            version=1,
            name="link-table-one",
            config={},
        )
        self.tool = Tool.objects.create(
            namespace=self.namespace,
            name="tool-one",
            uid=str(uuid.uuid4()),
            version=1,
            tool_type=ToolTypeEnum.DATA_SEARCH.value,
            config={},
            permission_owner="admin",
        )

    def save_tags(self, resource_type, resource_id, tags, namespace=None):
        return self.resource.meta.save_tag_bindings(
            namespace=namespace or self.namespace,
            resource_type=resource_type,
            resource_id=str(resource_id),
            tags=tags,
        )

    def get_tag_names(self, relation_model, resource_field, resource_id):
        tag_ids = relation_model.objects.filter(**{resource_field: resource_id}).values_list("tag_id", flat=True)
        return set(Tag.objects.filter(tag_id__in=tag_ids).values_list("tag_name", flat=True))

    def test_bind_strategy_tags(self):
        result = self.save_tags("strategy", self.strategy.strategy_id, ["tag-a", "tag-b"])

        self.assertEqual({item["tag_name"] for item in result}, {"tag-a", "tag-b"})
        self.assertEqual(
            self.get_tag_names(StrategyTag, "strategy_id", self.strategy.strategy_id),
            {"tag-a", "tag-b"},
        )

    def test_replace_strategy_tags(self):
        self.save_tags("strategy", self.strategy.strategy_id, ["tag-a", "tag-b"])
        self.save_tags("strategy", self.strategy.strategy_id, ["tag-b", "tag-c"])

        self.assertEqual(
            self.get_tag_names(StrategyTag, "strategy_id", self.strategy.strategy_id),
            {"tag-b", "tag-c"},
        )

    def test_bound_tags_keep_binding_order(self):
        """顺序按绑定先后，而不是 tag_id：先绑新标签 A，再绑老标签 B，结果应为 A、B"""
        old_tag = Tag.objects.create(tag_name="old-tag")
        new_tag = Tag.objects.create(tag_name="new-tag")

        self.save_tags("strategy", self.strategy.strategy_id, [new_tag.tag_name])
        result = self.save_tags("strategy", self.strategy.strategy_id, [new_tag.tag_name, old_tag.tag_name])

        self.assertEqual([item["tag_name"] for item in result], ["new-tag", "old-tag"])
        self.assertEqual(
            list(
                StrategyTag.objects.filter(strategy_id=self.strategy.strategy_id)
                .order_by("id")
                .values_list("tag__tag_name", flat=True)
            ),
            ["new-tag", "old-tag"],
        )

    def test_clear_strategy_tags(self):
        self.save_tags("strategy", self.strategy.strategy_id, ["tag-a"])
        result = self.save_tags("strategy", self.strategy.strategy_id, [])

        self.assertEqual(result, [])
        self.assertFalse(StrategyTag.objects.filter(strategy_id=self.strategy.strategy_id).exists())

    def test_bind_link_table_tags(self):
        self.save_tags("link_table", self.link_table.uid, ["link-tag"])

        self.assertEqual(
            self.get_tag_names(LinkTableTag, "link_table_uid", self.link_table.uid),
            {"link-tag"},
        )

    def test_bind_tool_tags_without_creating_new_version(self):
        tool_count = Tool.objects.filter(uid=self.tool.uid).count()

        self.save_tags("tool", self.tool.uid, ["tool-tag"])

        self.assertEqual(
            self.get_tag_names(ToolTag, "tool_uid", self.tool.uid),
            {"tool-tag"},
        )
        self.assertEqual(Tool.objects.filter(uid=self.tool.uid).count(), tool_count)

    def test_duplicate_tags_are_deduplicated(self):
        self.save_tags("strategy", self.strategy.strategy_id, ["same-tag", "same-tag"])

        self.assertEqual(StrategyTag.objects.filter(strategy_id=self.strategy.strategy_id).count(), 1)

    def test_invalid_tag_name(self):
        with self.assertRaises(TagNameInValid):
            self.save_tags("strategy", self.strategy.strategy_id, ["invalid tag!"])

    def test_resource_in_other_namespace_not_found(self):
        other_strategy = Strategy.objects.create(namespace=self.other_namespace, strategy_name="strategy-other")

        with self.assertRaises(Http404):
            self.save_tags("strategy", other_strategy.strategy_id, ["tag-a"])

    def test_resource_not_found(self):
        with self.assertRaises(Http404):
            self.save_tags("strategy", 999999, ["tag-a"])

    def test_non_uuid_resource_id_is_treated_as_not_found(self):
        with self.assertRaises(Http404):
            self.save_tags("tool", "not-a-uuid", ["tag-a"])


class TagBindingsViewPermissionsTest(TestCase):
    def setUp(self):
        self.namespace = "default"
        self.scene = Scene.objects.create(name="tag-binding-scene")
        self.tool = Tool.objects.create(
            namespace=self.namespace,
            name="tool-one",
            uid=str(uuid.uuid4()),
            version=1,
            tool_type=ToolTypeEnum.DATA_SEARCH.value,
            config={},
            permission_owner="admin",
        )

    def build_view(self, resource_type, resource_id):
        view = TagBindingsViewSet()
        view.action = "bindings"
        view.kwargs = {"namespace": self.namespace}
        view.request = SimpleNamespace(
            query_params={},
            data={"resource_type": resource_type, "resource_id": resource_id},
            parser_context={"kwargs": {"namespace": self.namespace}},
        )
        return view

    def test_strategy_permission_uses_edit_strategy(self):
        view = self.build_view("strategy", "123")

        permission = view.get_permissions()[0]

        self.assertIsInstance(permission, InstanceActionPermission)
        self.assertEqual(permission.actions, [ActionEnum.EDIT_STRATEGY])
        self.assertEqual(permission._get_instance_id(view.request, view), "123")

    def test_link_table_permission_uses_edit_link_table(self):
        view = self.build_view("link_table", str(uuid.uuid4()))

        permission = view.get_permissions()[0]

        self.assertIsInstance(permission, InstanceActionPermission)
        self.assertEqual(permission.actions, [ActionEnum.EDIT_LINK_TABLE])

    def test_scene_tool_permission_uses_manage_scene(self):
        binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id=self.tool.uid,
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=binding, scene=self.scene)
        view = self.build_view("tool", self.tool.uid)

        permission = view.get_permissions()[0]

        self.assertIsInstance(permission, InstanceActionPermission)
        self.assertEqual(permission.actions, [ActionEnum.MANAGE_SCENE])
        self.assertEqual(permission._get_instance_id(view.request, view), str(self.scene.scene_id))

    def test_platform_tool_permission_uses_manage_platform(self):
        ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id=self.tool.uid,
            binding_type=BindingType.PLATFORM_BINDING,
        )
        view = self.build_view("tool", self.tool.uid)

        permission = view.get_permissions()[0]

        self.assertIsInstance(permission, IAMPermission)
        self.assertEqual(permission.actions, [ActionEnum.MANAGE_PLATFORM])

    def test_unknown_resource_type_requires_authentication(self):
        view = self.build_view("unknown", "123")

        permission = view.get_permissions()[0]

        self.assertIsInstance(permission, IsAuthenticated)
