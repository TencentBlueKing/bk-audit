"""统一当前用户可见范围和权限判断。

查询权限与平台后台查询分开，指定负责人不具备可冒充能力。
未提供的项目授权契约由明确未就绪边界处理。
"""

from bk_resource import api
from django.conf import settings
from django.core.exceptions import PermissionDenied

from apps.feature.constants import FeatureTypeChoices
from apps.feature.handlers import FeatureHandler
from core.models import get_request_username
from services.web.bkbase.common import (
    get_bkbase_context,
    get_bkbase_version,
    pending_call,
)
from services.web.bkbase.constants import BKBaseVersion
from services.web.bkbase.exceptions import (
    BKBaseCapabilityNotReady,
    BKBaseResourceMappingError,
)


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
        raise BKBaseResourceMappingError(message="Unsupported BKBase user list response")
    return payload


def list_user_bizs(context):
    """取RT查询权限对应业务，不能使用biz.manage的默认范围。"""
    request = require_user(context)
    return _rows(
        api.bk_base_v4.user_scopes(
            action_id="result_table.query_data", show_display=True, show_admin_scopes=False, page=0, _request=request
        )
    )


def list_user_rts(context, *, bk_biz_id=None):
    """不按平台账号扩大个人可查询表范围。"""
    request = require_user(context)
    params = {"need_storage_detail": 1}
    if bk_biz_id is not None:
        params["bk_biz_id"] = [int(bk_biz_id)]
    return _rows(api.bk_base_v4.user_result_tables(**params, _request=request))


def check_user_rt(context, *, rt_id):
    """区分明确拒绝与未识别的返回，异常不伪装成有权。"""
    request = require_user(context)
    result = api.bk_base_v4.user_check(action_id="result_table.query_data", object_id=rt_id, _request=request)
    if isinstance(result, bool):
        return result
    if isinstance(result, dict) and isinstance(result.get("result"), bool):
        return result["result"]
    raise BKBaseResourceMappingError(message="Unsupported permission check response")


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
    return check_user_rt(get_bkbase_context(user=params["user_id"]), rt_id=params["object_id"])


def check_owner_result_tables(context, **params):
    """只在负责人即认证用户时用授权表集合比对。"""
    require_user(context)
    checks = params.get("permissions", [])
    if any(p.get("user_id") != context["user"] or p.get("action_id") != "result_table.query_data" for p in checks):
        raise BKBaseCapabilityNotReady("B11", "check_owner_result_tables")
    allowed = {r["result_table_id"] for r in list_user_rts(context)}
    return [{"user_id": p["user_id"], "object_id": p["object_id"], "result": p["object_id"] in allowed} for p in checks]


def get_project_data(request_data=None, **params):
    """V4关键契约待B07，V3调用保持。"""
    return pending_call("get_project_data", "B07", request_data, **params)


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
    """V4关键契约待B12，V3调用保持。"""
    return pending_call("get_role_users_list", "B12", request_data, **params)


def user_auth_batch_check(request_data=None, **params):
    """指定负责人不同于当前用户时明确等待B11。"""
    params = dict(request_data or params)
    if get_bkbase_version() == BKBaseVersion.V3:
        return api.bk_base.user_auth_batch_check(**params)
    context = get_bkbase_context(user=get_request_username())
    return check_owner_result_tables(context, **params)


def project_auth_available():
    """项目授权独立于V4模型退役，B07未关闭前后台不冒充授权成功。"""
    if get_bkbase_version() == BKBaseVersion.V4:
        return False
    return bool(FeatureHandler(FeatureTypeChoices.BKBASE_AIOPS).check() and settings.BKBASE_PROJECT_ID)
