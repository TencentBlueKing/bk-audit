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

import BksecRiskTypeField from './risk-type-field';

export default class BksecRiskType {
  id: string;
  name: string;
  isFormal: boolean;
  fields: BksecRiskTypeField[];
  constructor(payload: {
    id?: string | number;
    name?: string;
    risk_type_id?: string | number;
    risk_type_name?: string;
    is_formal?: boolean;
    fields?: Array<Record<string, any>>;
  } = {}) {
    this.id = String(payload.risk_type_id ?? payload.id ?? '');
    this.name = payload.risk_type_name ?? payload.name ?? '';
    this.isFormal = payload.is_formal !== false;
    const fields = (payload.fields || []).map(item => new BksecRiskTypeField(item));
    // 必填字段排在前面，同一组内保持接口原顺序
    fields.sort((left, right) => Number(right.required) - Number(left.required));
    this.fields = fields;
  }

  get label() {
    return `${this.name}(${this.id})`;
  }
}
