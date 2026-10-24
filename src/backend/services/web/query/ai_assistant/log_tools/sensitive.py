"""日志工具共享的敏感字段访问校验。

明细返回值和字段探索样本可复用 SearchDataParser 脱敏；查询条件和聚合结果
无法依赖逐行脱敏，因此必须在查询前按当前用户、系统和字段路径完成权限校验。
"""

from typing import Iterable, Protocol

from django.db.models import Q

from apps.meta.constants import SensitiveUserData
from apps.meta.models import SensitiveObject
from apps.meta.utils.fields import LOG
from apps.permission.handlers.service import PermissionService
from services.web.query.ai_assistant.exceptions import SensitiveFieldPermissionDenied
from services.web.query.ai_assistant.log_tools.schemas import LogFieldRef


def prepare_sensitive_query_fields(fields: Iterable[LogFieldRef]) -> tuple[LogFieldRef, ...]:
    """将请求字段转换为脱敏所需的根投影，并补齐规则匹配身份列。

    Args:
        fields: 调用方请求的字段，可包含 JSON 子路径；不会修改输入字段。
    Returns:
        按首次出现顺序保留、按根列去重的字段元组，末尾补齐缺失的身份列。
    """

    # 子路径必须从脱敏后的根对象裁剪，避免独立投影绕过整行规则处理。
    required = [LogFieldRef(raw_name=field.raw_name) if field.keys else field for field in fields]
    required.extend(LogFieldRef(raw_name=name) for name in ("system_id", "resource_type_id", "action_id"))
    unique_fields = []
    seen = set()
    for field in required:
        if field.raw_name not in seen:
            seen.add(field.raw_name)
            unique_fields.append(field)
    return tuple(unique_fields)


class _FieldPathRef(Protocol):
    """日志条件、投影和聚合字段共同具备的最小路径协议。"""

    raw_name: str
    keys: Iterable[str]


class SensitiveLogFieldPermissionService:
    """校验日志工具是否可以读取或使用指定字段路径。"""

    @classmethod
    def ensure_access(cls, *, username: str, system_id: str, fields: set[str]) -> None:
        """拒绝命中私密字段、无权敏感字段或可能包含这些字段的原始日志。"""

        if not all(cls.get_access(username=username, system_id=system_id, fields=fields).values()):
            raise SensitiveFieldPermissionDenied()

    @classmethod
    def get_access(cls, *, username: str, system_id: str, fields: set[str]) -> dict[str, bool]:
        """批量返回字段可读性，一次请求内共用规则和权限快照。

        Args:
            username: 认证链取得的用户。
            system_id: 实际查询系统。
            fields: 完整字段路径集合，保留原始路径段。
        Returns:
            每条请求路径的可读状态；私密规则无条件拒绝。
        """
        if not fields:
            return {}
        # _objects 包含私密规则；不能使用会排除私密字段的 objects。
        sensitive_objects = list(
            SensitiveObject._objects.filter(
                Q(system_id=system_id)
                | Q(system_id=SensitiveUserData.SYSTEM_ID, resource_id=SensitiveUserData.RESOURCE_ID)
            )
        )
        matched_by_path = {
            path: [
                rule
                for rule in sensitive_objects
                if path == LOG.field_name
                or any(
                    cls._field_paths_overlap(sensitive_path, path)
                    for sensitive_path in cls._sensitive_field_names(rule)
                )
            ]
            for path in fields
        }
        rule_ids = sorted({rule.id for rules in matched_by_path.values() for rule in rules if not rule.is_private})
        permissions = (
            PermissionService(username=username).get_sensitive_object_permissions(rule_ids) if rule_ids else {}
        )
        return {
            path: all(not rule.is_private and permissions.get(str(rule.id), False) for rule in rules)
            for path, rules in matched_by_path.items()
        }

    @staticmethod
    def collect_field_paths(fields: Iterable[_FieldPathRef | None]) -> set[str]:
        """统一收集参与查询语义的字段路径，避免不同 Doris 入口遗漏条件字段。"""

        return {".".join((field.raw_name, *field.keys)) for field in fields if field is not None}

    @staticmethod
    def _sensitive_field_names(sensitive_object: SensitiveObject) -> set[str]:
        """从兼容 JSON 配置中提取合法字段路径。"""

        return {
            item["field_name"]
            for item in sensitive_object.fields
            if isinstance(item, dict) and isinstance(item.get("field_name"), str)
        }

    @staticmethod
    def _field_paths_overlap(left: str, right: str) -> bool:
        """按路径段判断祖先/后代关系，避免普通字符串前缀误判。"""

        left_parts = tuple(left.split("."))
        right_parts = tuple(right.split("."))
        shared_length = min(len(left_parts), len(right_parts))
        return left_parts[:shared_length] == right_parts[:shared_length]
