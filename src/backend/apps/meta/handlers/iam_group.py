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

            # 确定每个动作的资源类型
            resource_type = "scene"  # 默认资源类型

            # 场景相关动作使用 scene 资源类型
            if action_id in ["view_scene", "manage_scene"]:
                resource_type = "scene"
            # 策略相关动作使用 scene 资源类型
            elif action_id in [
                "edit_strategy",
                "delete_strategy",
                "generate_strategy_risk",
            ]:
                resource_type = "strategy"
            elif action_id in ["list_strategy_v2", "create_strategy_v2"]:
                resource_type = "scene"
            # 风险相关动作使用 risk 资源类型
            elif action_id in ["list_risk_v2", "edit_risk_v2", "process_risk"]:
                resource_type = "risk"
            # 规则相关动作使用 scene 资源类型（根据动作定义）
            elif action_id in ["list_rule_v2", "create_rule_v2", "edit_rule_v2", "delete_rule_v2"]:
                resource_type = "scene"
            # 联表相关动作根据动作定义使用不同的资源类型
            elif action_id in ["list_link_table_v2", "create_link_table_v2"]:
                resource_type = "scene"
            elif action_id in ["view_link_table", "edit_link_table", "delete_link_table"]:
                resource_type = "link_table"
            # 通知组相关动作根据动作定义使用不同的资源类型
            elif action_id in ["list_notice_group_v2", "create_notice_group_v2"]:
                resource_type = "scene"
            elif action_id in ["edit_notice_group_v2", "delete_notice_group_v2"]:
                resource_type = "notice_group"
            # 套餐相关动作使用 scene 资源类型（根据动作定义）
            elif action_id in ["list_pa_v2", "create_pa_v2", "edit_pa_v2"]:
                resource_type = "scene"

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
        """
        添加用户组成员
        """
        system_id = system_id or settings.BK_IAM_SYSTEM_ID
        try:
            api.bk_iam.add_group_members(
                system_id=system_id,
                id=group_id,
                members=members,
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
    def create_scene_groups_with_members(
        cls,
        scene_id: str,
        scene_name: str,
        manager_members: list = None,
        viewer_members: list = None,
        expired_at: int = 0,
        system_id: str = None,
    ) -> dict:
        """
        创建场景用户组、授权并添加成员
        """
        # 参数验证
        if scene_name is None:
            raise TypeError("scene_name cannot be None")

        system_id = system_id or settings.BK_IAM_SYSTEM_ID
        grade_manager_id = "-"

        # 1. 构建需要创建的用户组列表
        groups = [
            {
                "name": f"{scene_name}-管理用户组",
                "description": f"{scene_name} 场景管理用户组，拥有查看和管理场景权限",
            },
            {
                "name": f"{scene_name}-使用用户组",
                "description": f"{scene_name} 场景使用用户组，拥有查看场景权限",
            },
        ]

        # 2. 创建用户组
        try:
            created_group_ids = api.bk_iam.create_grade_manager_groups(
                system_id=system_id,
                id=grade_manager_id,
                groups=groups,
            )
        except Exception as e:
            logger.error(
                "[create_scene_groups_with_members] 创建场景用户组失败, scene_name=%s, error=%s",
                scene_name,
                e,
            )
            raise

        logger.info(
            "[create_scene_groups_with_members] 创建用户组成功, groups=%s, result=%s",
            [g["name"] for g in groups],
            created_group_ids,
        )

        if not created_group_ids or len(created_group_ids) < 2:
            raise ValueError(f"创建场景用户组返回数据异常, 期望2个用户组ID, 实际返回: {created_group_ids}")

        iam_manager_group_id = created_group_ids[0]
        iam_viewer_group_id = created_group_ids[1]

        # 3. 为用户组授权
        grant_configs = [
            (iam_manager_group_id, SCENE_MANAGER_GROUP_ACTIONS, "管理用户组"),
            (iam_viewer_group_id, SCENE_VIEWER_GROUP_ACTIONS, "使用用户组"),
        ]
        granted_group_ids = []
        for group_id, group_actions, group_label in grant_configs:
            permissions = cls.build_permissions(
                actions=group_actions,
                system_id=system_id,
                scene_id=scene_id,
                scene_name=scene_name,
            )

            # 处理多资源类型权限请求
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
                            "[create_scene_groups_with_members] %s授权失败, group_id=%s, error=%s, "
                            "已创建的用户组IDs=%s, 已授权成功的用户组IDs=%s",
                            group_label,
                            group_id,
                            e,
                            created_group_ids,
                            granted_group_ids,
                        )
                        raise ValueError(
                            f"授权失败: {group_label}(group_id={group_id}), "
                            f"已创建的用户组IDs: {created_group_ids}, "
                            f"已授权成功的用户组IDs: {granted_group_ids}, "
                            f"错误: {e}"
                        ) from e
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
                        "[create_scene_groups_with_members] %s授权失败, group_id=%s, error=%s, "
                        "已创建的用户组IDs=%s, 已授权成功的用户组IDs=%s",
                        group_label,
                        group_id,
                        e,
                        created_group_ids,
                        granted_group_ids,
                    )
                    raise ValueError(
                        f"授权失败: {group_label}(group_id={group_id}), "
                        f"已创建的用户组IDs: {created_group_ids}, "
                        f"已授权成功的用户组IDs: {granted_group_ids}, "
                        f"错误: {e}"
                    ) from e

            granted_group_ids.append(group_id)
            logger.info(
                "[create_scene_groups_with_members] %s授权成功, group_id=%s, 资源类型数量=%s",
                group_label,
                group_id,
                len(permissions.get("_multi_permissions", [])) if "_multi_permissions" in permissions else 1,
            )

        # 4. 为管理用户组添加成员
        if manager_members:
            cls.add_group_members(
                group_id=iam_manager_group_id,
                members=manager_members,
                expired_at=expired_at,
                system_id=system_id,
            )

        # 5. 为使用用户组添加成员
        if viewer_members:
            cls.add_group_members(
                group_id=iam_viewer_group_id,
                members=viewer_members,
                expired_at=expired_at,
                system_id=system_id,
            )

        logger.info(
            "[create_scene_groups_with_members] 场景用户组创建完成, scene_id=%s, "
            "iam_manager_group_id=%s, iam_viewer_group_id=%s",
            scene_id,
            iam_manager_group_id,
            iam_viewer_group_id,
        )
        return {
            "iam_manager_group_id": iam_manager_group_id,
            "iam_viewer_group_id": iam_viewer_group_id,
        }

    @classmethod
    def sync_group_members(
        cls,
        group_id: Union[int, str],
        members: list,
        expired_at: int = 0,
        system_id: str = None,
    ) -> None:
        """
        同步用户组成员（先删除全部原有成员，再添加新成员）
        """
        system_id = system_id or settings.BK_IAM_SYSTEM_ID

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
