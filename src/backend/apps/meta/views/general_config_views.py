from bk_resource import resource
from bk_resource.viewsets import ResourceRoute, ResourceViewSet

from core.permissions import IsCreator


class GeneralConfigViewSet(ResourceViewSet):
    def get_permissions(self):
        return [IsCreator()]

    resource_routes = [
        ResourceRoute(
            "POST",
            resource.meta.create_general_config,
        ),
        ResourceRoute("GET", resource.meta.list_general_config),
        ResourceRoute("PUT", resource.meta.update_general_config, pk_field="id"),
        ResourceRoute("DELETE", resource.meta.delete_general_config, pk_field="id"),
    ]
