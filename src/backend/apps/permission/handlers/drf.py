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

from functools import wraps
from typing import Callable, List

from bk_resource import resource
from bk_resource.utils.common_utils import is_backend
from iam import Resource
from rest_framework import permissions

from apps.permission.handlers.actions import ActionMeta
from apps.permission.handlers.permission import Permission
from apps.permission.handlers.resource_types.base import ResourceTypeMeta


class IAMPermission(permissions.BasePermission):
    def __init__(self, actions: List[ActionMeta], resources: List[Resource] = None):
        self.actions = actions
        self.resources = resources or []

    def has_permission(self, request, view):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        if not self.actions:
            return True

        client = Permission()
        for action in self.actions:
            client.is_allowed(
                action=action,
                resources=self.resources,
                raise_exception=True,
            )
        return True

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return self.has_permission(request, view)

    def __call__(self, *args, **kwargs):
        return self


class InstanceActionPermission(IAMPermission):
    """
    关联其他资源的权限检查
    """

    def __init__(
        self, actions: List[ActionMeta], resource_meta: ResourceTypeMeta, lookup_field=None, get_instance_id=None
    ):
        """
        :params: actions 操作
        :params: resource_meta 操作关联的实例资源类型
        :params: lookup_field 自定义从view.kwargs中获取instance_id的key
        :params: get_instance_id 自定义获取instance_id的方法
        """
        self.resource_meta = resource_meta
        self.lookup_field = lookup_field
        self.get_instance_id = get_instance_id
        super(InstanceActionPermission, self).__init__(actions)

    def has_permission(self, request, view):
        # Perform the lookup filtering.

        if self.lookup_field:
            # 优先使用自定义的lookup_field
            instance_id = view.kwargs[self.lookup_field]
        else:
            if self.get_instance_id:
                instance_id = self.get_instance_id()
            else:
                lookup_url_kwarg = view.lookup_url_kwarg or view.lookup_field

                assert lookup_url_kwarg in view.kwargs, (
                    "Expected view %s to be called with a URL keyword argument "
                    'named "%s". Fix your URL conf, or set the `.lookup_field` '
                    "attribute on the view correctly." % (self.__class__.__name__, lookup_url_kwarg)
                )

                instance_id = view.kwargs[lookup_url_kwarg]

        resource = self.resource_meta.create_instance(instance_id)
        self.resources = [resource]
        return super(InstanceActionPermission, self).has_permission(request, view)


class ActionPermission(IAMPermission):
    """
    任何一个操作的权限
    """

    def has_permission(self, request, view):
        if not self.actions:
            return True

        client = Permission(request=request)
        return any(client.has_action_any_permission(action=action) for action in self.actions)


def wrapper_permission_field(
    result_list: List[dict],
    actions: List[ActionMeta],
    id_field: Callable = lambda item: item["id"],
    always_allowed: Callable = lambda item: False,
    many: bool = True,
):
    """
    实例数据新增权限字段
    """
    if not many:
        result_list = [result_list]

    # 生成资源实例信息
    instance_ids = {}
    for item in result_list:
        instance_id = str(id_field(item))
        if not instance_id and instance_id in instance_ids:
            continue
        instance_ids[instance_id] = True

    # 无实例鉴权 or 后台进程
    if not instance_ids or is_backend():
        return result_list

    permission_result = resource.permission.batch_is_allowed(
        action_ids=[action.id for action in actions], resources=instance_ids.keys()
    )

    for item in result_list:
        origin_instance_id = id_field(item)
        if not origin_instance_id:
            # 如果拿不到实例ID，则不处理
            continue
        instance_id = str(origin_instance_id)
        item.setdefault("permission", {})
        item["permission"].update(permission_result[instance_id])

        if always_allowed(item):
            # 权限豁免
            for action_id in item["permission"]:
                item["permission"][action_id] = True

    return result_list


def insert_permission_field(
    actions: List[ActionMeta],
    id_field: Callable = lambda item: item["id"],
    data_field: Callable = lambda data_list: data_list,
    always_allowed: Callable = lambda item: False,
    many: bool = True,
):
    """
    数据返回后，插入权限相关字段
    :param actions: 动作列表
    :param id_field: 从结果集获取ID字段的方式
    :param data_field: 从response.data中获取结果集的方式
    :param always_allowed: 满足一定条件进行权限豁免
    :param many: 是否为列表数据
    """

    def wrapper(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            response = view_func(*args, **kwargs)

            result_list = data_field(response.data)
            wrapper_permission_field(result_list, actions, id_field, always_allowed, many)
            return response

        return wrapped_view

    return wrapper


def insert_action_permission_field(
    actions: List[ActionMeta],
    data_field: Callable = lambda data_list: data_list,
    always_allowed: Callable = lambda item: False,
    many: bool = True,
):
    """
    数据返回后，插入权限相关字段
    :param actions: 动作列表
    :param data_field: 从response.data中获取结果集的方式
    :param always_allowed: 满足一定条件进行权限豁免
    :param many: 是否为列表数据
    """

    def wrapper(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            response = view_func(*args, **kwargs)

            result_list = data_field(response.data)
            if not many:
                result_list = [result_list]

            client = Permission()
            permission_result = {}
            for action in actions:
                permission_result[action.id] = client.is_allowed(action, raise_exception=False)

            for item in result_list:
                item["permission"] = permission_result
                if always_allowed(item):
                    # 权限豁免
                    for action_id in item["permission"]:
                        item["permission"][action_id] = True

            return response

        return wrapped_view

    return wrapper
