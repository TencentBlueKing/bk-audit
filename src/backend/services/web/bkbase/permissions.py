"""区分平台可用表与个人权限，统一权限判断。

指定负责人通过应用认证检查 RT 权限，实际 Query 仍使用平台账号。
个人列表继续使用真实用户身份；未提供的授权写操作保持冻结。
"""

import re

from bk_resource import api, resource
from blueapps.utils.request_provider import get_request_username
from django.conf import settings
from django.core.exceptions import PermissionDenied

from api.bk_base.constants import UserAuthActionEnum
from api.bk_base_v4.constants import AuthAction
from apps.feature.constants import FeatureTypeChoices
from apps.feature.handlers import FeatureHandler
from apps.meta.constants import SpaceType
from services.web.bkbase import metadata
from services.web.bkbase.common import (
    get_bkbase_context,
    get_bkbase_version,
    legacy_call,
    pending_call,
)
from services.web.bkbase.constants import BKBaseVersion
from services.web.bkbase.exceptions import BKBaseResourceMappingError


def require_user(context):
    """个人操作只接受与真实请求匹配的用户。"""
    request = context.get("request")
    actual = getattr(request, "user", None)
    username = getattr(actual, "bk_username", None) or getattr(actual, "username", None)
    if not context.get("user") or username != context["user"] or not getattr(actual, "is_authenticated", False):
        raise PermissionDenied("BKBase personal operation requires its authenticated user")
    return request


def _rows(payload):
    if not isinstance(payload, list) or not all(isinstance(x, dict) for x in payload):
        raise BKBaseResourceMappingError(message="Unsupported BKBase list response")
    return payload


def _projects(context, request, *, include_alias=False):
    """按固定身份枚举项目，可从同一次响应保留别名；标识始终为真实namespace。"""
    tenant = context.get("tenant")
    if not isinstance(tenant, str) or not tenant:
        raise BKBaseResourceMappingError(message="Missing project tenant")
    projects = {}
    rows = (
        api.bk_base_v4.user_namespaces_list(tenant=tenant, _request=request)
        if request is not None
        else api.bk_base_v4.namespaces_list(tenant=tenant)
    )
    for row in _rows(rows):
        meta, spec = row.get("metadata"), row.get("spec")
        if (
            row.get("kind") != "Namespace"
            or not isinstance(meta, dict)
            or meta.get("tenant") != tenant
            or meta.get("namespace") != "bkbase"
            or not isinstance(meta.get("name"), str)
            or not meta["name"]
            or not isinstance(spec, dict)
            or spec.get("name") not in (None, meta["name"])
        ):
            raise BKBaseResourceMappingError(message="Invalid Namespace identity")
        status = row.get("status")
        if status is not None and not isinstance(status, dict):
            raise BKBaseResourceMappingError(message="Invalid Namespace status")
        if (status or {}).get("phase") != "Terminating":
            name = meta["name"]
            alias = spec.get("alias")
            alias = alias.strip() if isinstance(alias, str) else ""
            projects[name] = f"{alias}（{name}）" if alias and alias != name else name
    if include_alias:
        return [{"namespace": name, "label": projects[name]} for name in sorted(projects)]
    return sorted(projects)


def _business_id(value):
    """业务号只接受数字，拒绝布尔值和无法表达业务的投影。"""
    if isinstance(value, bool) or not re.fullmatch(r"[0-9]+", str(value)):
        raise BKBaseResourceMappingError(message="Invalid business ID")
    return int(value)


@metadata.list_read_scope()
def _list_rts(context, *, request=None, bk_biz_id=None):
    """复用完整项目/分页遍历，严格query=True并按租户逻辑RT去重。"""
    selected_biz = _business_id(bk_biz_id) if bk_biz_id is not None else None
    projects = _projects(context, request)
    batches = metadata.list_project_datasets(
        context,
        projects,
        dataset_name=f"{selected_biz}_" if selected_biz is not None else None,
        user_request=request,
    )
    return _queryable_tables(batches, selected_biz=selected_biz)


def _queryable_tables(batches, *, selected_biz=None):
    """统一 Dataset query 权限校验、逻辑 ID 去重及旧业务投影。"""
    tables = {}
    for rows in batches:
        for row in _rows(rows):
            grant = row.get("permissions")
            if not isinstance(grant, dict) or grant.get("query") is not True:
                continue
            rt_id, storage = row.get("dataset_name"), row.get("storage_type")
            if not isinstance(rt_id, str) or not re.fullmatch(r"[0-9]+_[A-Za-z0-9_]+", rt_id):
                raise BKBaseResourceMappingError(message="Invalid queryable Dataset logical ID")
            biz_id = int(rt_id.split("_", 1)[0])
            if selected_biz is not None and biz_id != selected_biz:
                continue
            alias = row.get("dataset_alias") or rt_id
            if not isinstance(alias, str) or not isinstance(storage, str):
                raise BKBaseResourceMappingError(message="Invalid queryable Dataset projection")
            table = tables.setdefault(
                rt_id, {"result_table_id": rt_id, "result_table_name": alias, "bk_biz_id": biz_id, "storages": {}}
            )
            if storage:
                table["storages"][storage] = {"storage_type": storage}
    return sorted(tables.values(), key=lambda row: (row["bk_biz_id"], row["result_table_id"]))


@metadata.list_read_scope()
def list_projects(context=None, *, include_alias=False):
    """平台身份仅枚举项目目录，不读取任何 Dataset 或 Binding。"""
    context = context or get_bkbase_context()
    if context["version"] != BKBaseVersion.V4:
        raise BKBaseResourceMappingError(message="Project lazy loading requires BKBase V4")
    return _projects(context, None, include_alias=include_alias)


@metadata.list_read_scope()
def list_user_projects(context=None, *, include_alias=False):
    """只用当前认证用户读取个人项目目录，不扫描 Dataset 或 Binding。"""
    context = context or get_bkbase_context(user=get_request_username() or "")
    if context["version"] != BKBaseVersion.V4:
        raise BKBaseResourceMappingError(message="Project lazy loading requires BKBase V4")
    return _projects(context, require_user(context), include_alias=include_alias)


@metadata.list_read_scope()
def list_user_namespace_result_tables(namespace, *, context=None):
    """同一用户目录核权后，完整分页读取一个真实项目，禁止平台或全量回退。"""
    context = context or get_bkbase_context(user=get_request_username() or "")
    if (
        context["version"] != BKBaseVersion.V4
        or not isinstance(namespace, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]+", namespace)
    ):
        raise BKBaseResourceMappingError(message="An explicit V4 namespace is required")
    request = require_user(context)
    if namespace not in _projects(context, request):
        raise PermissionDenied("BKBase project is not accessible to the authenticated user")
    return _queryable_tables(metadata.list_project_datasets(context, [namespace], user_request=request))


@metadata.list_read_scope()
def list_namespace_result_tables(namespace, *, context=None):
    """严格读取一个显式项目的完整可查询表集合，不回退租户全量。"""
    context = context or get_bkbase_context()
    if (
        context["version"] != BKBaseVersion.V4
        or not isinstance(namespace, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]+", namespace)
    ):
        raise BKBaseResourceMappingError(message="An explicit V4 namespace is required")
    return _queryable_tables(metadata.list_project_datasets(context, [namespace]))


@metadata.list_read_scope()
def list_queryable_result_tables(result_table_ids, *, context=None, skip_missing=False):
    """有限逻辑 ID 按正式项目精确核权；候选列表可跳过明确缺失的RT，权限读取失败仍上抛。"""
    context = {**(context or get_bkbase_context()), "_result_table_info": {}}
    if context["version"] != BKBaseVersion.V4:
        raise BKBaseResourceMappingError(message="Finite Dataset reads require BKBase V4")

    def read(rt_id):
        ref = (
            metadata.read_candidate_or_none(metadata.get_result_table_ref, context=context, result_table_id=rt_id)
            if skip_missing
            else metadata.get_result_table_ref(context, rt_id)
        )
        if ref is None:
            metadata._unavailable_candidate(rt_id, "formal_unavailable")
            return []
        rows = metadata.list_datasets({**context, "namespace": ref["namespace"]}, dataset_name=rt_id)
        exact = [row for row in _rows(rows) if row.get("dataset_name") == rt_id]
        return _queryable_tables([exact])

    batches = metadata.bounded_read_map(read, list(dict.fromkeys(result_table_ids)))
    return [row for batch in batches for row in batch]


def list_user_rts(context, *, bk_biz_id=None):
    """个人列表只能使用与真实请求匹配的用户身份。"""
    return _list_rts(context, request=require_user(context), bk_biz_id=bk_biz_id)


def list_user_bizs(context):
    """业务菜单取可查询表的业务集合，业务名称沿用已有空间接口。"""
    biz_ids = {row["bk_biz_id"] for row in list_user_rts(context)}
    if not biz_ids:
        return []
    names = {}
    for space in _rows(resource.meta.get_spaces_mine()):
        if space.get("space_type_id") != SpaceType.BIZ.value:
            continue
        biz_id = _business_id(space.get("id"))
        if not isinstance(space.get("name"), str):
            raise BKBaseResourceMappingError(message="Invalid business name projection")
        names[biz_id] = space["name"]
    return [{"bk_biz_id": biz_id, "bk_biz_name": names.get(biz_id, str(biz_id))} for biz_id in sorted(biz_ids)]


def check_user_rt(context, *, rt_id):
    """只检查当前请求用户的完整可查询表集合；读取失败不得提前返回允许。"""
    return any(row["result_table_id"] == rt_id for row in list_user_rts(context))


def get_bizs_list(**params):
    """兼容原业务菜单调用，当前用户身份集中校验。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return api.bk_base.get_bizs_list(**params)
    return list_user_bizs(get_bkbase_context(user=params.get("bk_username")))


def get_mine_result_tables(request_data=None, **params):
    """兼容业务按单业务查询个人结果表。"""
    params = dict(request_data or params)
    if get_bkbase_version() == BKBaseVersion.V3:
        return api.bk_base.get_mine_result_tables(**params)
    return list_user_rts(get_bkbase_context(user=params.get("bk_username")), bk_biz_id=params.get("bk_biz_id"))


def user_auth_check(**params):
    """V3保留指定用户检查，V4只支持当前已认证用户。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return api.bk_base.user_auth_check(**params)
    action = params.get("action_id", "result_table.query_data")
    if getattr(action, "value", action) != "result_table.query_data":
        raise BKBaseResourceMappingError(message="Only current-user query permission is supported")
    return check_user_rt(get_bkbase_context(user=params["user_id"]), rt_id=params["object_id"])


def check_owner_result_tables(context, **params):
    """核负责人授权及获准 RT 的正式身份，完整返回旧协议；未返回的 RT 拒绝。"""
    requested = params.get("permissions")
    if not isinstance(requested, list):
        raise BKBaseResourceMappingError(message="Expected an owner permission list")
    groups = {}
    for item in requested:
        if not isinstance(item, dict):
            raise BKBaseResourceMappingError(message="Invalid owner permission request")
        owner, rt_id = item.get("user_id"), item.get("object_id")
        action = item.get("action_id", UserAuthActionEnum.RT_QUERY)
        if (
            not isinstance(owner, str)
            or not owner.strip()
            or not isinstance(rt_id, str)
            or not re.fullmatch(r"[0-9]+_[A-Za-z0-9_]+", rt_id)
            or action != UserAuthActionEnum.RT_QUERY
        ):
            raise BKBaseResourceMappingError(message="Only explicit owner RT query checks are supported")
        groups.setdefault(owner, {})[rt_id] = None
    checked = {}
    for owner, tables in groups.items():
        rows = _rows(
            api.bk_base_v4.direct_auth_by_resources(
                tenant=None,
                namespace=None,
                user_id=owner,
                action_id=AuthAction.QUERY_DATASET,
                resource_ids=list(tables),
                parent_resource_type=None,
                parent_resource_id=None,
            )
        )
        grants = {}
        for row in rows:
            rt_id, allowed = row.get("resource_id"), row.get("allowed")
            if not isinstance(rt_id, str) or rt_id not in tables or rt_id in grants or not isinstance(allowed, bool):
                raise BKBaseResourceMappingError(message="Invalid or ambiguous owner RT permission result")
            grants[rt_id] = allowed
        for rt_id in tables:
            checked[owner, rt_id] = grants.get(rt_id, False)
    verified = set()
    for (_, rt_id), allowed in checked.items():
        if allowed is True and rt_id not in verified:
            # auth（含admin豁免）不保证资源存在；仅在本次调用内去重正式读取。
            metadata.get_result_table_ref(context, rt_id)
            verified.add(rt_id)
    return [
        {
            "user_id": item["user_id"],
            "object_id": item["object_id"],
            "result": checked[item["user_id"], item["object_id"]],
        }
        for item in requested
    ]


def get_project_data(request_data=None, **params):
    """V4使用配置平台账号的可查询集合承接项目授权，V3按旧项目读取。"""
    params = dict(request_data or params)
    if get_bkbase_version() == BKBaseVersion.V3:
        return api.bk_base.get_project_data(**params)
    return _list_rts(get_bkbase_context())


def project_data_batch_check(request_data=None, **params):
    """V4关键契约待B07，V3调用保持。"""
    return pending_call("project_data_batch_check", "B07", request_data, **params)


def project_data_batch_add(request_data=None, **params):
    """V4关键契约待B07，V3调用保持。"""
    return pending_call("project_data_batch_add", "B07", request_data, **params)


def auth_tickets(request_data=None, **params):
    """V4关键契约待B07，V3调用保持。"""
    return pending_call("auth_tickets", "B07", request_data, **params)


def get_role_users_list(request_data=None, **params):
    """V4角色名单展示暂返回空，不作为授权依据；V3保留原行为。"""
    if get_bkbase_version() == BKBaseVersion.V4:
        return []
    return legacy_call("get_role_users_list", request_data, **params)


def user_auth_batch_check(request_data=None, **params):
    """V4统一使用应用检查指定负责人，V3保留原接口与空集合语义。"""
    params = dict(request_data or params)
    if get_bkbase_version() == BKBaseVersion.V3:
        return api.bk_base.user_auth_batch_check(**params)
    context = get_bkbase_context()
    return check_owner_result_tables(context, **params)


def project_auth_available():
    """V4 不需要后台补项目授权；V3 保持原开关。"""
    if get_bkbase_version() == BKBaseVersion.V4:
        return False
    return bool(FeatureHandler(FeatureTypeChoices.BKBASE_AIOPS).check() and settings.BKBASE_PROJECT_ID)
