"""日志查询结果的统一脱敏转换。

日志 Service 与 Resource 共同复用该转换，但 Service 不再依赖
``resources`` package 的初始化顺序。权限查询和脱敏行为保持既有实现。
"""

from typing import List

from apps.meta.models import SensitiveObject
from apps.permission.handlers.service import PermissionService
from core.models import get_request_username
from services.web.query.utils.formatter import HitsFormatter


class SearchDataParser:
    """按当前用户敏感字段权限脱敏日志命中。"""

    @staticmethod
    def _permission_service(username: str) -> PermissionService:
        return PermissionService(username=username)

    @staticmethod
    def _request_username() -> str:
        return get_request_username()

    @classmethod
    def mark_sensitive_permissions(cls, sensitive_objs: List[SensitiveObject], username: str) -> None:
        """标记敏感对象权限，隐藏不同权限模型的底层差异。"""

        if not username:
            for sensitive_obj in sensitive_objs:
                setattr(sensitive_obj, "_has_permission", False)
            return

        permissions = cls._permission_service(username).get_sensitive_object_permissions(
            [sensitive_obj.id for sensitive_obj in sensitive_objs]
        )
        for sensitive_obj in sensitive_objs:
            setattr(sensitive_obj, "_has_permission", permissions.get(str(sensitive_obj.id), False))

    def parse_data(self, data: List[dict], username: str = None) -> list:
        """按显式身份或当前请求身份返回脱敏后的日志列表。"""

        private_sensitive_objs = list(SensitiveObject._objects.filter(is_private=True))
        sensitive_objs = list(SensitiveObject.objects.all())
        if sensitive_objs:
            self.mark_sensitive_permissions(sensitive_objs, username or self._request_username())
        return [HitsFormatter(value, [*sensitive_objs, *private_sensitive_objs]).value for value in data]
