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

from typing import List, Optional, Tuple, Type

from bk_resource import resource
from django.db import models, transaction
from django.db.models import QuerySet
from django.http import Http404

from apps.meta.constants import TagBindingResourceType
from apps.meta.models import Tag


@transaction.atomic
def sync_resource_tags(
    relation_resource_field: str,
    resource_uid: str,
    tag_names: List[str],
    relation_model: Type[models.Model],
) -> QuerySet:
    """
    同步资源标签关联

    参数:
        relation_resource_field: 关联表中关联资源的字段名，
        resource_uid: 资源唯一标识
        tag_names: 标签名列表
        relation_model: 关联表模型类
    返回:
        当前绑定的标签列表
    """
    # 删除旧关联
    filter_kwargs = {relation_resource_field: resource_uid}
    relation_model.objects.filter(**filter_kwargs).delete()

    if not tag_names:
        return Tag.objects.none()

    # 批量保存标签
    tags = resource.meta.save_tags([{"tag_name": t} for t in tag_names])
    tag_ids = [t["tag_id"] for t in tags]
    # 批量创建关联
    objs = [relation_model(**{relation_resource_field: resource_uid, "tag_id": tag_id}) for tag_id in tag_ids]
    relation_model.objects.bulk_create(objs)

    return Tag.objects.filter(tag_id__in=tag_ids)


class TagBindingHandler:
    """策略/联表/工具标签绑定"""

    @classmethod
    def save(cls, namespace: str, resource_type: str, resource_id: str, tags: List[str]) -> QuerySet:
        relation_model, relation_resource_field, normalized_id = cls.resolve(
            resource_type=resource_type,
            resource_id=resource_id,
            namespace=namespace,
        )
        return sync_resource_tags(
            relation_resource_field=relation_resource_field,
            resource_uid=normalized_id,
            tag_names=tags,
            relation_model=relation_model,
        )

    @classmethod
    def resolve(cls, resource_type: str, resource_id: str, namespace: str) -> Tuple[Type[models.Model], str, str]:
        if resource_type == TagBindingResourceType.STRATEGY:
            from services.web.strategy_v2.models import Strategy, StrategyTag

            strategy_id = int(resource_id)
            if not Strategy.objects.filter(strategy_id=strategy_id, namespace=namespace).exists():
                raise Http404
            return StrategyTag, "strategy_id", str(strategy_id)

        if resource_type == TagBindingResourceType.LINK_TABLE:
            from services.web.strategy_v2.models import LinkTable, LinkTableTag

            if not LinkTable.objects.filter(uid=resource_id, namespace=namespace).exists():
                raise Http404
            return LinkTableTag, "link_table_uid", str(resource_id)

        if resource_type == TagBindingResourceType.TOOL:
            from services.web.tool.models import Tool, ToolTag

            if not Tool.objects.filter(uid=resource_id, namespace=namespace).exists():
                raise Http404
            return ToolTag, "tool_uid", str(resource_id)

        raise Http404


def get_tool_binding_info(resource_id: str) -> Tuple[bool, Optional[str]]:
    from services.web.scene.constants import (
        BindingType,
        ResourceVisibilityType,
        SceneStatus,
    )
    from services.web.scene.models import ResourceBinding

    binding = ResourceBinding.objects.filter(
        resource_type=ResourceVisibilityType.TOOL,
        resource_id=str(resource_id),
    ).first()
    if not binding or binding.binding_type != BindingType.SCENE_BINDING:
        return False, None

    scene_id = (
        binding.binding_scenes.filter(
            scene__is_deleted=False,
            scene__status=SceneStatus.ENABLED,
        )
        .values_list("scene_id", flat=True)
        .first()
    )
    return True, str(scene_id) if scene_id is not None else None
