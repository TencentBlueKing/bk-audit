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
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import logging

from core.render import jinja2_environment

logger = logging.getLogger("celery")


def render_value(template: str, context: dict) -> str:
    """
    渲染字段值模板（支持字符串和风险变量/事件变量混写）
    - 风险变量：{{ risk.risk_id }}、{{ risk.operator }}
    - 事件变量：{{ event.username }}，取最后一条事件的字段值
    """
    if not isinstance(template, str) or "{{" not in template:
        return template if isinstance(template, str) else ""
    env = jinja2_environment(autoescape=False)
    try:
        return env.from_string(template).render(**context).strip()
    except Exception as err:  # NOCC:broad-except(渲染失败需明确可见)
        logger.exception("[BkSecRender] Render failed, template=%s err=%s", template, err)
        raise
