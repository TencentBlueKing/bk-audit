/*
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
*/
export default class RiskRule {
  id: string;
  auto_id: string;
  created_at: string;
  created_by: string;
  updated_at: string;
  updated_by: string;
  is_deleted: boolean;
  rule_id: string;
  version: number;
  name: string;
  scope: Array<{
    field: string,
    value: string,
    operator: string
  }>;
  pa_id: string;
  pa_params: Record<string, any>;
  auto_close_risk: boolean;
  priority_index: number;// 优先指数
  is_enabled: boolean;

  constructor(payload = {} as RiskRule) {
    this.id = payload.id;
    this.auto_id = payload.auto_id;
    this.created_at = payload.created_at;
    this.created_by = payload.created_by;
    this.updated_at = payload.updated_at;
    this.updated_by = payload.updated_by;
    this.is_deleted = payload.is_deleted;
    this.rule_id = payload.rule_id;
    this.version = payload.version;
    this.name = payload.name;
    this.scope = payload.scope;
    this.pa_id = payload.pa_id;
    this.pa_params = payload.pa_params;
    this.auto_close_risk = payload.auto_close_risk;
    this.priority_index = payload.priority_index;
    this.is_enabled = payload.is_enabled;
  }
}
