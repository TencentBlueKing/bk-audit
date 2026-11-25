"""集中处理版本及可信调用上下文。

上下文只在调用内存中传递，不作为持久化认证数据。
V4资源参数按使用场景检查，避免影响默认V3部署。
"""
import hashlib
import json
import re
from contextlib import contextmanager
from copy import deepcopy
from http import HTTPStatus

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from blueapps.utils.request_provider import get_local_request
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.db import transaction

from api.bk_base_v4.tenant import get_bkbase_v4_tenant
from core.exceptions import LockError
from core.utils.lock import RedisLock
from services.web.bkbase.constants import BKBaseVersion, TaskState
from services.web.bkbase.exceptions import (
    BKBaseCapabilityNotReady,
    BKBaseResourceMappingError,
)


def get_bkbase_version():
    """返回部署所选版本，拒绝错误配置及隐式降级。"""
    version = getattr(settings, "BKBASE_API_VERSION", BKBaseVersion.V3)
    if version not in BKBaseVersion.values:
        raise ImproperlyConfigured("BKBASE_API_VERSION must be v3 or v4")
    return version


def get_bkbase_context(*, user=None):
    """取得平台或当前已认证用户上下文，不支持冒充指定用户。"""
    version = get_bkbase_version()
    namespaces = getattr(settings, "BKBASE_V4_RESULT_TABLE_NAMESPACES", {}) if version == BKBaseVersion.V4 else {}
    if isinstance(namespaces, str):
        try:
            namespaces = json.loads(namespaces)
        except (TypeError, ValueError) as error:
            raise ImproperlyConfigured("Invalid BKBASE_V4_RESULT_TABLE_NAMESPACES") from error
    if not isinstance(namespaces, dict):
        raise ImproperlyConfigured("BKBASE_V4_RESULT_TABLE_NAMESPACES must be an object")
    request = get_local_request()
    if user is not None:
        actual = getattr(request, "user", None)
        username = getattr(actual, "bk_username", None) or getattr(actual, "username", None)
        if not user or username != user:
            raise PermissionDenied("BKBase user context must match the authenticated user")
    return {
        "version": version,
        "rt_namespaces": namespaces,
        "tenant": get_bkbase_v4_tenant() if version == BKBaseVersion.V4 else getattr(settings, "BKBASE_V4_TENANT", ""),
        "namespace": getattr(settings, "BKBASE_V4_NAMESPACE", ""),
        "mcp_project_id": getattr(settings, "BKBASE_V4_MCP_PROJECT_ID", ""),
        "user": user,
        "request": request if user is not None else None,
    }


def resource_params(context, ref=None, *, kind=None):
    """只操作当前租户的显式资源引用，namespace不从业务数字ID推断。"""
    ref = ref or context
    if not context.get("tenant") or ref.get("tenant") != context["tenant"]:
        raise BKBaseResourceMappingError(message="Missing or mismatched tenant reference")
    if not ref.get("namespace") or (ref is not context and not ref.get("name")):
        raise BKBaseResourceMappingError(message="Incomplete resource reference")
    if kind and ref.get("kind") != kind:
        raise BKBaseResourceMappingError(message=f"Expected {kind} reference")
    return {key: ref[key] for key in ("tenant", "namespace", "name") if key in ref}


def operation_result(resource, ref, action):
    """按资源协议转换观察状态；DataStorage 的 Ok 表示当前配置已生效。"""
    status = resource.get("status") or {}
    state = resource.get("spec", {}).get("current_status")
    if isinstance(state, str):
        state = state.lower()
    if ref.get("kind") == "DataStorage":
        annotations = (resource.get("metadata") or {}).get("annotations") or {}
        state = TaskState.STOPPED if annotations.get("task_stopped") == "true" else TaskState.RUNNING
    if status.get("phase") == "Failed":
        state = TaskState.FAILED
    elif status.get("phase") != "Ok" or state not in TaskState.values:
        state = None
    return {
        "ref": ref,
        "requested_action": action,
        "accepted": True,
        "resource_phase": status.get("phase"),
        "task_state": state,
        "message": status.get("message", ""),
        "retryable": status.get("phase") != "Failed",
    }


def reference(resource, context, kind):
    """从已取得的资源身份建立引用，kind必须匹配。"""
    metadata = resource.get("metadata", {})
    if resource.get("kind") != kind or not metadata.get("name"):
        raise BKBaseResourceMappingError(message=f"Invalid {kind} resource")
    ref = {
        "kind": kind,
        "tenant": metadata.get("tenant", context["tenant"]),
        "namespace": metadata.get("namespace", context["namespace"]),
        "name": metadata["name"],
    }
    resource_params(context, ref, kind=kind)
    return ref


def build_resource_name(readable: str, token: str, *, max_length: int, suffix: str = "") -> str:
    """保留完整固定标识与后缀，只截短并规范化可读部分。"""
    if not isinstance(max_length, int) or isinstance(max_length, bool) or max_length <= 0:
        raise ValueError("max_length must be a positive integer")
    if not isinstance(readable, str):
        raise ValueError("readable must be a string")
    if not isinstance(token, str) or not token or re.fullmatch(r"[A-Za-z0-9_-]+", token) is None:
        raise ValueError("token must contain only resource name characters")
    if not isinstance(suffix, str) or re.fullmatch(r"[A-Za-z0-9_-]*", suffix) is None:
        raise ValueError("suffix must contain only resource name characters")

    readable_length = max_length - 1 - len(token) - len(suffix)
    if readable_length < 1:
        raise ValueError("max_length cannot fit a readable part and fixed resource name parts")

    normalized = re.sub(r"[^A-Za-z0-9_-]", "_", readable)
    if not re.search(r"[A-Za-z0-9]", normalized):
        normalized = "resource"
    if normalized.startswith("-"):
        normalized = "_" + normalized[1:]
    return f"{normalized[:readable_length]}_{token}{suffix}"


def stable_name(prefix, *parts):
    """稳定资源名保留摘要，截断不会导致不同业务资源同名。"""
    text = "_".join(str(p) for p in parts)
    digest = hashlib.sha256(text.encode()).hexdigest()[:12]
    readable = re.sub(r"[^A-Za-z0-9_-]", "_", text)
    return build_resource_name(f"{prefix}_{readable}", digest, max_length=58)


@contextmanager
def resource_lock(context, ref):
    """复用项目Redis锁，串行化同一资源的审计侧完整PUT。"""
    params = resource_params(context, ref)
    key = (
        "bkbase_v4:"
        + hashlib.sha256(json.dumps({**params, "kind": ref.get("kind")}, sort_keys=True).encode()).hexdigest()
    )
    lock = RedisLock(key, ttl=300)
    if not lock.acquire(0.1):
        raise LockError(message="BKBase resource operation is already in progress")
    try:
        yield
    finally:
        lock.release()


@contextmanager
def snapshot_lock(system_id, resource_type_id):
    """互斥同一快照的启停、重放和资产维护；应先于资源锁获取。"""
    if not all(isinstance(value, str) and value for value in (system_id, resource_type_id)):
        raise BKBaseResourceMappingError(message="Missing snapshot identity")
    digest = hashlib.sha256(json.dumps([system_id, resource_type_id], ensure_ascii=False).encode()).hexdigest()
    lock = RedisLock("bkbase_v4:snapshot:" + digest, ttl=300)
    if not lock.acquire(0.1):
        raise LockError(message="Snapshot operation is already in progress")
    try:
        yield
    finally:
        lock.release()


def get_resource_or_none(resource, **params):
    """只有明确HTTP404或已文档化的资源不存在错误才视为不存在，鉴权/超时等错误不能触发重建。"""
    try:
        return resource(**params)
    except APIRequestError as error:
        if getattr(error, "http_status", None) == HTTPStatus.NOT_FOUND or getattr(error, "resource_not_found", False):
            return None
        raise


def update_owner_binding(owner, patch, *, remove=()):
    """短事务合并所属资源引用，不覆盖其他并发操作新增的绑定。"""
    with transaction.atomic():
        current = type(owner).objects.select_for_update().get(pk=owner.pk)
        binding = deepcopy(current.bkbase_v4_resources or {})
        for key, value in patch.items():
            if key in ("storages", "physical_targets"):
                if key == "physical_targets" and any(
                    binding.get(key, {}).get(purpose) not in (None, target) for purpose, target in value.items()
                ):
                    raise BKBaseResourceMappingError(message="V4 storage destination conflicts with its saved target")
                binding.setdefault(key, {}).update(deepcopy(value))
            else:
                binding[key] = deepcopy(value)
        for key in remove:
            binding.pop(key, None)
        current.bkbase_v4_resources = binding
        current.save(update_fields=["bkbase_v4_resources"])
    owner.bkbase_v4_resources = binding
    return binding


def pending_call(name, blocker_id, request_data=None, **params):
    """保留未迁移能力的V3行为；V4明确待办，不伪造空结果或回退。"""
    if get_bkbase_version() == BKBaseVersion.V4:
        raise BKBaseCapabilityNotReady(blocker_id, name)
    return getattr(api.bk_base, name)(**dict(request_data or params))


def legacy_call(name, request_data=None, **params):
    """逐节点等旧原语仅供V3流程调用，V4必须走完整能力入口。"""
    if get_bkbase_version() == BKBaseVersion.V4:
        raise BKBaseResourceMappingError(message=f"{name} requires the V4 business workflow and explicit bindings")
    return getattr(api.bk_base, name)(**dict(request_data or params))


def legacy_bulk(name, requests, *, ignore_exceptions=False):
    """保留V3批量语义，禁止V4执行遗留原语。"""
    if get_bkbase_version() == BKBaseVersion.V4:
        raise BKBaseResourceMappingError(message=f"{name} must use the V4 business workflow")
    return getattr(api.bk_base, name).bulk_request(requests, ignore_exceptions=ignore_exceptions)
