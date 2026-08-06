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

from typing import Optional, Union

from bk_resource import api
from bk_resource.settings import bk_resource_settings
from blueapps.utils.logger import logger
from django.utils import timezone
from django.utils.translation import gettext

from apps.meta.handlers.iam_group import IAMGroupManager
from apps.permission.handlers.resource_types import ResourceEnum
from apps.permission.handlers.service import PermissionService
from services.web.common.monitor import ScenePermissionGrantFailedEvent
from services.web.scene.constants import (
    SCENE_PERMISSION_GRANT_MAX_RETRY,
    SCENE_ROLE_TO_IAM_V4_ROLE,
    ApplicationStatus,
    GrantStatus,
    ITSMV4TicketStatus,
    SceneRole,
)
from services.web.scene.exceptions import ScenePermissionApplicationException
from services.web.scene.models import Scene, ScenePermissionApplication


def grant_scene_role(scene: Scene, role: str, username: str, operator: Optional[str] = None) -> dict:
    """授予场景角色（V3/V4 自适应）。仅授予单人，不影响其他成员。
    :param scene: Scene 实例
    :param role: SceneRole.MANAGER / SceneRole.USER
    :param username: 被授权人
    :param operator: 操作人（用于 IAM 审计）
    :return: {"success": bool, "method": str, ...}
    """
    operator = operator or bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME

    # ---- V4：授 role ----
    if IAMGroupManager.is_v4_backend():
        role_id = SCENE_ROLE_TO_IAM_V4_ROLE[role]
        # 幂等：已有该 role 则跳过
        if username in IAMGroupManager.get_scene_role_members(role_id, str(scene.scene_id)):
            logger.info("[grant_scene_role] %s 已有 %s on scene %s，跳过", username, role_id, scene.scene_id)
            return {"success": True, "method": "v4_role_grant", "skipped": True}
        service = PermissionService(username=operator)
        service.grant_instance_permission(
            role_id=role_id,
            subject={"type": "user", "id": username},
            resources=[ResourceEnum.SCENE.create_instance(str(scene.scene_id))],
            operator=operator,
        )
        logger.info("[grant_scene_role] V4 授权成功 %s -> %s on scene %s", username, role_id, scene.scene_id)
        return {"success": True, "method": "v4_role_grant"}

    # ---- V3：加用户组成员 ----
    group_id = scene.iam_manager_group_id if role == SceneRole.MANAGER else scene.iam_viewer_group_id
    if not group_id:
        logger.warning("[grant_scene_role] V3 场景 %s 用户组未创建", scene.scene_id)
        return {"success": False, "error": gettext("场景用户组未创建")}
    IAMGroupManager.add_group_members(group_id=group_id, members=[username])
    logger.info("[grant_scene_role] V3 加组成员 %s -> group %s", username, group_id)
    return {"success": True, "method": "v3_group_add", "group_id": group_id}


def parse_itsm_ticket(ticket_data: dict) -> dict:
    """解析 ITSM 工单响应，返回结构化结果。
    :param ticket_data: ITSM API 返回的工单数据
    :return: {"status": str, "approve_result": bool, "is_terminal": bool}
    """
    status = ticket_data.get("status", "")
    approve_result = ticket_data.get("approve_result", False)
    is_terminal = status == ITSMV4TicketStatus.FINISHED
    return {
        "status": status,
        "approve_result": approve_result,
        "is_terminal": is_terminal,
    }


def parse_itsm_ticket_from_logs(logs_data: dict) -> dict:
    """从 ITSM V4 工单日志推断工单状态，返回结构化结果。
    :param logs_data: ITSM V4 TicketLogs API 返回的数据 {"items": [...]}
    :return: {"status": str, "approve_result": bool, "is_terminal": bool}
    """
    items = logs_data.get("items", [])

    # 空日志 → 流程未开始或数据异常
    if not items:
        return {
            "status": ITSMV4TicketStatus.RUNNING,
            "approve_result": False,
            "is_terminal": False,
        }

    # 检查流程是否结束
    has_end = any(item.get("action") == "end" for item in items)

    # 查找审批节点（activity_type == "APPROVE_TASK"）
    approve_result = False
    for item in items:
        if item.get("activity_type") == "APPROVE_TASK":
            approve_result = item.get("action") == "approve"
            break

    # 流程已结束
    if has_end:
        return {
            "status": ITSMV4TicketStatus.FINISHED,
            "approve_result": approve_result,
            "is_terminal": True,
        }

    # 其他情况 → 流程进行中
    return {
        "status": ITSMV4TicketStatus.RUNNING,
        "approve_result": False,
        "is_terminal": False,
    }


def apply_ticket_result(
    application: ScenePermissionApplication,
    parsed: dict,
    operator: Optional[str] = None,
    reject_reason: str = "",
) -> None:
    """根据 ITSM 工单结果更新申请状态。【轮询 / callback 共用入口】
    :param application: 申请单（调用方负责加锁/事务）
    :param parsed: 解析后的工单状态 {"status": str, "approve_result": bool, ...}
    :param operator: 授权操作人
    :param reject_reason: 拒绝理由
    """

    # ① 审批通过 → 先设审批状态，再授权
    if parsed["status"] == ITSMV4TicketStatus.FINISHED and parsed["approve_result"]:
        application.status = ApplicationStatus.APPROVED
        do_grant(application, operator=operator)
    # ② 审批驳回（finished 但未通过）→ 记录拒绝理由
    elif parsed["status"] == ITSMV4TicketStatus.FINISHED:
        application.reject_reason = reject_reason
        _set_terminal(application, ApplicationStatus.REJECTED)
    # running → 保持 PENDING，不动


def _extract_reject_reason(ticket_id: str) -> str:
    """从 ITSM V4 工单日志中提取拒绝/驳回理由。
    :param ticket_id: ITSM 工单 ID
    :return: 拒绝理由，获取失败返回空字符串
    """
    try:
        logs_data = api.bk_itsm_v4.ticket_logs(ticket_id=ticket_id)
        return _extract_reject_reason_from_logs(logs_data)
    except Exception as err:  # pylint: disable=broad-except
        logger.warning("[_extract_reject_reason] 获取工单日志失败, ticket_id=%s, error=%s", ticket_id, err)

    return ""


def _extract_reject_reason_from_logs(logs_data: dict) -> str:
    """从已获取的 ITSM V4 工单日志数据中提取拒绝/驳回理由。
    :param logs_data: ITSM V4 TicketLogs API 返回的数据 {"items": [...]}
    :return: 拒绝理由，获取失败返回空字符串
    """
    items = logs_data.get("items", [])

    # 从后往前找最近的拒绝操作
    for log_item in reversed(items):
        if log_item.get("action") == "refuse":
            # 从 extra 中提取审批意见
            for extra_item in log_item.get("extra", []):
                if extra_item.get("type") == "name_value" and extra_item.get("name") == "审批意见":
                    return str(extra_item.get("value", "")).strip()
            break

    return ""


def do_grant(application: ScenePermissionApplication, operator: Optional[str] = None) -> None:
    """执行授权。成功→grant_status=SUCCESS；失败→grant_status=FAILED(retry_count++)"""
    try:
        result = grant_scene_role(
            scene=application.scene,
            role=application.role,
            username=application.applicant,
            operator=operator,
        )
        if result.get("success"):
            application.grant_status = GrantStatus.SUCCESS
            application.grant_method = result.get("method", "")
            application.grant_error = ""
            application.retry_count = 0
            application.finished_at = timezone.now()
        else:
            application.grant_status = GrantStatus.FAILED
            application.grant_error = result.get("error", "unknown")
            application.retry_count += 1
            _check_grant_retry_exhausted(application)
    except Exception as err:  # pylint: disable=broad-except
        logger.exception("[do_grant] 申请单 %s 授权失败: %s", application.id, err)
        application.grant_status = GrantStatus.FAILED
        application.grant_error = str(err)
        application.retry_count += 1
        _check_grant_retry_exhausted(application)


def _check_grant_retry_exhausted(application: ScenePermissionApplication) -> None:
    """授权重试到上限时上报告警事件。"""
    if application.retry_count < SCENE_PERMISSION_GRANT_MAX_RETRY:
        return
    logger.error(
        "[scene_permission] 申请单 %s 授权重试已达上限(%s)，applicant=%s, scene=%s, role=%s, error=%s",
        application.id,
        application.retry_count,
        application.applicant,
        application.scene_id,
        application.role,
        application.grant_error,
    )
    try:
        event = ScenePermissionGrantFailedEvent(
            target=f"application_{application.id}",
            context={
                "application_id": str(application.id),
                "applicant": application.applicant,
                "scene_id": str(application.scene_id),
                "role": application.role,
                "grant_error": (application.grant_error or "")[:500],
            },
            extra={
                "retry_count": application.retry_count,
                "itsm_sn": application.itsm_sn,
            },
        )
        event.async_report()
    except Exception:  # pylint: disable=broad-except
        logger.exception("[scene_permission] 告警事件上报失败，申请单 %s", application.id)


def _set_terminal(application: ScenePermissionApplication, status: Union[str, ApplicationStatus]) -> None:
    application.status = status
    application.finished_at = timezone.now()


def already_has_role(scene: Scene, role: str, username: str) -> bool:
    """检查用户是否已拥有指定场景角色（V3/V4 自适应）。"""
    if IAMGroupManager.is_v4_backend():
        role_id = SCENE_ROLE_TO_IAM_V4_ROLE[role]
        return username in IAMGroupManager.get_scene_role_members(role_id, str(scene.scene_id))
    group_id = scene.iam_manager_group_id if role == SceneRole.MANAGER else scene.iam_viewer_group_id
    if not group_id:
        raise ScenePermissionApplicationException(message=gettext("场景用户组未创建，无法校验权限，请联系管理员"))
    members = IAMGroupManager.get_all_group_members(group_id=group_id)
    return username in [m["id"] for m in members if m.get("type") == "user"]
