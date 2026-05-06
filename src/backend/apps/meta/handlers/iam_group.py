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

from typing import Union

from bk_resource import api
from blueapps.utils.logger import logger
from django.conf import settings

from apps.permission.handlers.actions import get_action_by_id
from apps.permission.handlers.actions.action import ActionEnum

# 场景管理用户组拥有的操作列表
SCENE_MANAGER_GROUP_ACTIONS = [
    ActionEnum.VIEW_SCENE,
    ActionEnum.MANAGE_SCENE,
    # 策略
    ActionEnum.LIST_STRATEGY,
    ActionEnum.CREATE_STRATEGY,
    ActionEnum.EDIT_STRATEGY,
    ActionEnum.DELETE_STRATEGY,
    ActionEnum.GENERATE_STRATEGY_RISK,
    # 风险
    ActionEnum.LIST_RISK,
    ActionEnum.EDIT_RISK,
    ActionEnum.PROCESS_RISK,
    # 规则
    ActionEnum.LIST_RULE,
    ActionEnum.CREATE_RULE,
    ActionEnum.EDIT_RULE,
    ActionEnum.DELETE_RULE,
    # 套餐
    ActionEnum.LIST_PA,
    ActionEnum.CREATE_PA,
    ActionEnum.EDIT_PA,
    # 通知组
    ActionEnum.LIST_NOTICE_GROUP,
    ActionEnum.CREATE_NOTICE_GROUP,
    ActionEnum.EDIT_NOTICE_GROUP_V2,
    ActionEnum.DELETE_NOTICE_GROUP_V2,
    # 联表管理
    ActionEnum.LIST_LINK_TABLE,
    ActionEnum.CREATE_LINK_TABLE,
    ActionEnum.EDIT_LINK_TABLE,
    ActionEnum.DELETE_LINK_TABL,
    ActionEnum.VIEW_LINK_TABLE,
]

# 场景使用用户组拥有的操作列表
SCENE_VIEWER_GROUP_ACTIONS = [
    ActionEnum.VIEW_SCENE,
]


class IAMGroupManager:
    """
    IAM 用户组管理
    """

    @staticmethod
    def build_permissions(
        actions: list,
        system_id: str,
        scene_id: str,
        scene_name: str,
    ) -> dict:
        """
        构建权限数据结构
        """
        actions = [{"id": action.id} for action in actions]

        # 根据动作类型分组，支持多资源类型动作
        action_groups = {}

        for action in actions:
            action_id = action["id"]

            # 从 ActionEnum 定义中获取关联的资源类型
            action_meta = get_action_by_id(action_id)
            if not action_meta.related_resource_types:
                raise ValueError(f"Action {action_id} 未定义 related_resource_types，无法构建权限")
            resource_type = action_meta.related_resource_types[0].id

            # 按资源类型分组动作
            if resource_type not in action_groups:
                action_groups[resource_type] = []
            action_groups[resource_type].append(action)

        # 构建批量资源授权结构
        if not action_groups:
            # 空动作列表时返回默认的scene类型资源
            return {
                "_multi_permissions": [
                    {
                        "actions": [],
                        "resources": [
                            {
                                "system": system_id,
                                "type": "scene",
                                "paths": [
                                    [
                                        {
                                            "system": system_id,
                                            "type": "scene",
                                            "id": scene_id,
                                            "name": scene_name,
                                        }
                                    ]
                                ],
                            }
                        ],
                    }
                ]
            }

        # 构建多资源类型权限结构
        multi_permissions = []
        for resource_type, grouped_actions in action_groups.items():
            multi_permissions.append(
                {
                    "actions": grouped_actions,
                    "resources": [
                        {
                            "system": system_id,
                            "type": resource_type,
                            "paths": [
                                [
                                    {
                                        "system": system_id,
                                        "type": resource_type,
                                        "id": scene_id,
                                        "name": scene_name,
                                    }
                                ]
                            ],
                        }
                    ],
                }
            )

        # 返回多资源类型权限结构
        return {"_multi_permissions": multi_permissions}

    @classmethod
    def get_all_group_members(
        cls,
        group_id: Union[int, str],
        page_size: int = 100,
        system_id: str = None,
    ) -> list:
        """
        分页获取用户组全部成员
        """
        system_id = system_id or settings.BK_IAM_SYSTEM_ID
        all_members = []
        page = 1
        while True:
            try:
                result = api.bk_iam.get_group_members(
                    system_id=system_id,
                    id=group_id,
                    page=page,
                    page_size=page_size,
                )
            except Exception as e:
                logger.error(
                    "[get_all_group_members] 获取用户组成员列表失败, group_id=%s, page=%s, error=%s",
                    group_id,
                    page,
                    e,
                )
                raise
            members = result.get("results", [])
            all_members.extend(members)
            total = result.get("count", 0)
            if len(all_members) >= total or not members:
                break
            page += 1
        logger.info(
            "[get_all_group_members] 获取全部成员完成, group_id=%s, total=%s",
            group_id,
            len(all_members),
        )
        return all_members

    @staticmethod
    def add_group_members(
        group_id: Union[int, str],
        members: list,
        expired_at: int = None,
        system_id: str = None,
    ) -> None:
        import time

        if expired_at is None:
            expired_at = int(time.time()) + 31536000
        system_id = system_id or settings.BK_IAM_SYSTEM_ID
        formatted_members = [{"type": "user", "id": m} for m in members]
        try:
            api.bk_iam.add_group_members(
                system_id=system_id,
                id=group_id,
                members=formatted_members,
                expired_at=expired_at,
            )
        except Exception as e:
            logger.error(
                "[add_group_members] 添加用户组成员失败, group_id=%s, members=%s, error=%s",
                group_id,
                members,
                e,
            )
            raise

    @staticmethod
    def delete_group_members(
        group_id: Union[int, str],
        member_type: str,
        member_ids: list,
        system_id: str = None,
    ) -> None:
        """
        删除用户组成员
        """
        system_id = system_id or settings.BK_IAM_SYSTEM_ID
        try:
            api.bk_iam.delete_group_members(
                system_id=system_id,
                id=group_id,
                type=member_type,
                ids=member_ids,
            )
        except Exception as e:
            logger.error(
                "[delete_group_members] 删除用户组成员失败, group_id=%s, type=%s, ids=%s, error=%s",
                group_id,
                member_type,
                member_ids,
                e,
            )
            raise

    @classmethod
    def create_single_group_with_members(
        cls,
        group_name: str,
        group_description: str,
        group_actions: list,
        members: list = None,
        scene_id: str = None,
        scene_name: str = None,
        expired_at: int = None,
        system_id: str = None,
    ) -> int:
        """
        创建单个用户组、授权并添加成员

        :return: 创建的用户组 ID
        """
        system_id = system_id or settings.BK_IAM_SYSTEM_ID
        grade_manager_id = "-"

        # 1. 创建用户组
        group_def = [{"name": group_name, "description": group_description}]
        try:
            created_group_ids = api.bk_iam.create_grade_manager_groups(
                system_id=system_id,
                id=grade_manager_id,
                groups=group_def,
            )
        except Exception as e:
            logger.error(
                "[create_single_group_with_members] 创建用户组失败, group_name=%s, error=%s",
                group_name,
                e,
            )
            raise

        if not created_group_ids or len(created_group_ids) < 1:
            raise ValueError(f"创建用户组返回数据异常, 期望1个用户组ID, 实际返回: {created_group_ids}")

        group_id = created_group_ids[0]
        logger.info(
            "[create_single_group_with_members] 创建用户组成功, group_name=%s, group_id=%s",
            group_name,
            group_id,
        )

        # 2. 为用户组授权
        permissions = cls.build_permissions(
            actions=group_actions,
            system_id=system_id,
            scene_id=scene_id,
            scene_name=scene_name,
        )

        if "_multi_permissions" in permissions:
            # 多资源类型：为每个资源类型单独调用授权接口
            for permission in permissions["_multi_permissions"]:
                try:
                    api.bk_iam.grant_group_policies(
                        system_id=system_id,
                        id=group_id,
                        actions=permission["actions"],
                        resources=permission["resources"],
                    )
                except Exception as e:
                    logger.error(
                        "[create_single_group_with_members] %s授权失败, group_id=%s, error=%s",
                        group_name,
                        group_id,
                        e,
                    )
                    raise ValueError(f"授权失败: {group_name}(group_id={group_id}), 错误: {e}") from e
        else:
            # 单资源类型：保持原有逻辑
            try:
                api.bk_iam.grant_group_policies(
                    system_id=system_id,
                    id=group_id,
                    actions=permissions["actions"],
                    resources=permissions["resources"],
                )
            except Exception as e:
                logger.error(
                    "[create_single_group_with_members] %s授权失败, group_id=%s, error=%s",
                    group_name,
                    group_id,
                    e,
                )
                raise ValueError(f"授权失败: {group_name}(group_id={group_id}), 错误: {e}") from e

        logger.info(
            "[create_single_group_with_members] %s授权成功, group_id=%s, 资源类型数量=%s",
            group_name,
            group_id,
            len(permissions.get("_multi_permissions", [])) if "_multi_permissions" in permissions else 1,
        )

        # 3. 添加成员
        if members:
            cls.add_group_members(
                group_id=group_id,
                members=members,
                expired_at=expired_at,
                system_id=system_id,
            )

        return group_id

    @classmethod
    def sync_group_members(
        cls,
        group_id: Union[int, str, None],
        members: list,
        expired_at: int = None,
        system_id: str = None,
        # 以下参数仅在 group_id 为空（用户组尚未创建）时使用
        group_name: str = None,
        group_description: str = None,
        group_actions: list = None,
        scene_id: str = None,
        scene_name: str = None,
    ) -> Union[int, None]:
        """
        同步用户组成员（先删除全部原有成员，再添加新成员）。
        如果 group_id 为空，则先创建用户组并返回新的 group_id。
        """
        system_id = system_id or settings.BK_IAM_SYSTEM_ID

        # 用户组不存在，先创建
        if not group_id:
            new_group_id = cls.create_single_group_with_members(
                group_name=group_name,
                group_description=group_description,
                group_actions=group_actions,
                members=members,
                scene_id=scene_id,
                scene_name=scene_name,
                expired_at=expired_at,
                system_id=system_id,
            )
            return new_group_id

        # 1. 分页获取当前用户组全部成员
        current_members = cls.get_all_group_members(
            group_id=group_id,
            system_id=system_id,
        )

        # 2. 按 type 分组删除原有成员
        if current_members:
            members_by_type: dict = {}
            for member in current_members:
                m_type = member.get("type", "")
                m_id = member.get("id", "")
                if m_type and m_id:
                    members_by_type.setdefault(m_type, []).append(m_id)

            for member_type, member_ids in members_by_type.items():
                cls.delete_group_members(
                    group_id=group_id,
                    member_type=member_type,
                    member_ids=member_ids,
                    system_id=system_id,
                )

        # 3. 添加新成员
        if members:
            cls.add_group_members(
                group_id=group_id,
                members=members,
                expired_at=expired_at,
                system_id=system_id,
            )

        logger.info(
            "[sync_group_members] 同步成员完成, group_id=%s, new_members_count=%s",
            group_id,
            len(members),
        )
        return None
