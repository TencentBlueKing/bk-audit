import inspect
import re

from drf_spectacular.openapi import AutoSchema
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter
from rest_framework import serializers as drf_serializers


class BKResourceAutoSchema(AutoSchema):
    """
    自定义 AutoSchema 以适配 bk_resource.viewsets.ResourceViewSet
    """

    def _get_action_for_route(self, route):
        """
        根据 ResourceRoute 推断 DRF action 名称
        """
        if route.endpoint:
            return route.endpoint

        # 映射表
        mapping = {
            "GET": "retrieve" if route.pk_field else "list",
            "POST": "create",
            "PUT": "update",
            "PATCH": "partial_update",
            "DELETE": "destroy",
        }
        return mapping.get(route.method.upper())

    def _get_matched_route(self):
        """获取当前 action 匹配的 ResourceRoute"""
        view = self.view
        if hasattr(view, 'resource_routes'):
            for route in view.resource_routes:
                if view.action == self._get_action_for_route(route):
                    return route
        return None

    def _get_path_parameter_names(self):
        """提取当前路由模板中的路径参数，避免它们重复出现在 body 或 query schema。"""
        return set(re.findall(r"\{([\w-]+)\}", self.path))

    def get_request_serializer(self):
        route = self._get_matched_route()
        if route:
            req_serializer = route.resource_class.RequestSerializer
            if req_serializer:
                serializer = req_serializer()
                for field_name in self._get_path_parameter_names():
                    serializer.fields.pop(field_name, None)
                return serializer
        return super().get_request_serializer()

    def _is_list_view(self, serializer=None):
        route = self._get_matched_route()
        if route:
            return route.enable_paginate
        return super()._is_list_view(serializer)

    def get_response_serializers(self):
        route = self._get_matched_route()
        if route:
            serializer = route.resource_class.ResponseSerializer or route.resource_class.serializer_class
            if serializer:
                return serializer
            # 没有 ResponseSerializer（如文件下载接口），返回二进制响应类型
            return OpenApiTypes.BINARY
        return super().get_response_serializers()

    def get_override_parameters(self):
        params = super().get_override_parameters()
        route = self._get_matched_route()
        if route:
            serializer_class = route.resource_class.RequestSerializer
            if serializer_class:
                try:
                    serializer = serializer_class()
                    path_parameter_names = self._get_path_parameter_names()
                    for field_name, field in serializer.fields.items():
                        if field_name in path_parameter_names:
                            location = OpenApiParameter.PATH
                        elif route.method.upper() == "GET":
                            location = OpenApiParameter.QUERY
                        else:
                            continue

                        # UUID 路径参数显式声明格式；其余常用 DRF 字段映射为基础类型。
                        field_type_map = {
                            drf_serializers.UUIDField: OpenApiTypes.UUID,
                            drf_serializers.IntegerField: int,
                            drf_serializers.FloatField: float,
                            drf_serializers.BooleanField: bool,
                        }
                        openapi_type = field_type_map.get(type(field), str)
                        params.append(
                            OpenApiParameter(
                                name=field_name,
                                type=openapi_type,
                                location=location,
                                description=str(field.help_text or field.label or field_name),
                                required=True if location == OpenApiParameter.PATH else field.required,
                            )
                        )
                except Exception:
                    pass
            # 如果开启了分页，添加分页参数
            if route.enable_paginate:
                params.extend(
                    [
                        OpenApiParameter("page", type=int, location=OpenApiParameter.QUERY, description="Page number"),
                        OpenApiParameter(
                            "page_size", type=int, location=OpenApiParameter.QUERY, description="Page size"
                        ),
                    ]
                )
        return params

    def get_tags(self):
        # 尝试从 Resource 类获取 tags
        tags = super().get_tags()
        route = self._get_matched_route()
        if route:
            resource_tags = getattr(route.resource_class, 'tags', [])
            if resource_tags:
                return resource_tags
        return tags

    def get_summary(self):
        # 尝试从 Resource 类获取 name 作为 summary
        route = self._get_matched_route()
        if route:
            name = getattr(route.resource_class, 'name', None)
            if name:
                return str(name)
        return super().get_summary()

    def get_description(self):
        # 尝试从 Resource 类获取 docstring 作为 description
        route = self._get_matched_route()
        if route:
            doc = route.resource_class.__doc__
            if doc:
                return inspect.cleandoc(str(doc))
        return super().get_description()
