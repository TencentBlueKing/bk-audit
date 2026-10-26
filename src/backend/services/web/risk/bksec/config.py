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

from typing import List

from django.utils.translation import gettext
from drf_pydantic import BaseModel
from pydantic import Field, field_validator, model_validator

from services.web.risk.bksec.constants import (
    BKSEC_FIELD_INITIAL_OWNER,
    BKSEC_FIELD_RISK_ASSET,
    BKSEC_FIELD_TARGET_TYPE,
    BKSEC_REQUIRED_FIELD_KEYS,
)


class BkSecFieldMapping(BaseModel):
    """
    BKSEC 工单字段映射项

    value 支持文字与变量混排，语法与事件调查报告一致：
    - 风险变量：{{ risk.risk_id }}、{{ risk.operator }}
    - 事件变量：{{ event.username }}（默认取最后一条事件）、{{ count(event.event_id) }}
    """

    key: str = Field("", description="BKSEC 字段 key")
    name: str = Field("", description="BKSEC 字段名称")
    value: str = Field("", description="字段值模板")
    required: bool = Field(False, description="是否必填")


class BkSecConfig(BaseModel):
    """
    策略 BKSEC 安全工单配置（存储于 Strategy.bksec_config）
    """

    enabled: bool = Field(False, description="是否启用 BKSEC 安全工单")
    risk_type_id: str = Field("", description="BKSEC 风险类型 ID")
    risk_type_name: str = Field("", description="BKSEC 风险类型名称")
    # 三个独立入参模板：SOPS 插件 ${target}/${target_type}/${operator} 的取值来源，
    target: str = Field("", description="BKSEC 风险资产信息模板（${target}）")
    target_type: str = Field("", description="BKSEC 目标资产类型模板（${target_type}）")
    operator: str = Field("", description="BKSEC 初始责任人模板（${operator}）")
    source_type: str = Field("bk-audit", description="BKSEC 数据源类型（固定为 bk-audit）")
    field_mappings: List[BkSecFieldMapping] = Field(default_factory=list, description="字段映射列表")

    @field_validator("field_mappings")
    @classmethod
    def _dedupe_mappings(cls, values: List[BkSecFieldMapping]) -> List[BkSecFieldMapping]:
        deduped = {}
        for v in values:
            if v.key:
                deduped[v.key] = v
        return list(deduped.values())

    @model_validator(mode="after")
    def _sync_sops_params(self):
        # target/target_type/operator 三个独立字段作为 SOPS 独立入参模板
        # 前端支持全部从field_mappings传入
        if not self.target:
            self.target = self.get_field_mapping(BKSEC_FIELD_RISK_ASSET).value
        if not self.target_type:
            self.target_type = self.get_field_mapping(BKSEC_FIELD_TARGET_TYPE).value
        if not self.operator:
            self.operator = self.get_field_mapping(BKSEC_FIELD_INITIAL_OWNER).value
        return self

    def get_field_mapping(self, key: str) -> BkSecFieldMapping:
        for m in self.field_mappings:
            if m.key == key:
                return m
        return BkSecFieldMapping(key=key)

    def validate_for_submit(self) -> None:
        """
        正式提交校验：
           1. 启用时风险类型必选
           2. 必填字段非空(operator/target/target_type)

        草稿保存不调用本方法（允许配置不完整）。
        """
        if not self.enabled:
            return
        if not self.risk_type_id:
            raise ValueError(gettext("启用 BKSEC 安全工单时必须选择风险类型"))
        for key in BKSEC_REQUIRED_FIELD_KEYS:
            value = getattr(self, key, "") or ""
            if not value.strip():
                raise ValueError(gettext("BKSEC 安全工单必填参数未配置：%s") % key)
