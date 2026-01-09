import inspect

from drf_spectacular.openapi import AutoSchema


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

    def get_request_serializer(self):
        view = self.view
        if hasattr(view, 'resource_routes'):
            for route in view.resource_routes:
                if view.action == self._get_action_for_route(route):
                    # bk_resource 的 RequestSerializer 可能是 None，此时回退到默认行为
                    return route.resource_class.RequestSerializer or super().get_request_serializer()
        return super().get_request_serializer()

    def get_response_serializers(self):
        view = self.view
        if hasattr(view, 'resource_routes'):
            for route in view.resource_routes:
                if view.action == self._get_action_for_route(route):
                    # 优先使用 ResponseSerializer，其次是 serializer_class
                    serializer = route.resource_class.ResponseSerializer or route.resource_class.serializer_class
                    if serializer:
                        return serializer
        return super().get_response_serializers()

    def get_override_parameters(self):
        params = super().get_override_parameters()
        view = self.view
        if hasattr(view, 'resource_routes'):
            for route in view.resource_routes:
                if view.action == self._get_action_for_route(route):
                    if route.method.upper() == "GET":
                        serializer = route.resource_class.RequestSerializer
                        if serializer:
                            params.append(serializer)
        return params

    def get_tags(self):
        # 尝试从 Resource 类获取 tags
        view = self.view
        tags = super().get_tags()
        if hasattr(view, 'resource_routes'):
            for route in view.resource_routes:
                if view.action == self._get_action_for_route(route):
                    resource_tags = getattr(route.resource_class, 'tags', [])
                    if resource_tags:
                        return resource_tags
        return tags

    def get_summary(self):
        # 尝试从 Resource 类获取 name 作为 summary
        view = self.view
        if hasattr(view, 'resource_routes'):
            for route in view.resource_routes:
                if view.action == self._get_action_for_route(route):
                    name = getattr(route.resource_class, 'name', None)
                    if name:
                        return str(name)
        return super().get_summary()

    def get_description(self):
        # 尝试从 Resource 类获取 docstring 作为 description
        view = self.view
        if hasattr(view, 'resource_routes'):
            for route in view.resource_routes:
                if view.action == self._get_action_for_route(route):
                    doc = route.resource_class.__doc__
                    if doc:
                        return inspect.cleandoc(str(doc))
        return super().get_description()
