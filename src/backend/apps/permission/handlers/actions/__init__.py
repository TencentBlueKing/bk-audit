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

from django.utils.translation import gettext

from apps.permission.exceptions import ActionNotExistError
from apps.permission.handlers.actions.action import ActionEnum
from apps.permission.handlers.actions.base import ActionMeta

_all_actions = {action.id: action for action in ActionEnum.__dict__.values() if isinstance(action, ActionMeta)}


def get_action_by_id(action_id: Union[str, ActionMeta]) -> ActionMeta:
    """
    根据动作ID获取动作实例
    """
    if isinstance(action_id, ActionMeta):
        # 如果已经是实例，则直接返回
        return action_id

    if action_id not in _all_actions:
        raise ActionNotExistError(message=gettext("动作ID不存在：%(action_id)s") % {"action_id": action_id})

    return _all_actions[action_id]
