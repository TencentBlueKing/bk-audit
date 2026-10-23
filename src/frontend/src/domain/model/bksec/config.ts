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

export interface BksecFieldMeta {
  key: string;
  name: string;
  required: boolean;
}

export interface BksecFieldMapping {
  key: string;
  name: string;
  value: string;
  required: boolean;
}

export interface BksecConfigPayload {
  enabled: boolean;
  risk_type_id?: string;
  risk_type_name: string;
  field_mappings: BksecFieldMapping[];
}

export interface BksecFormState {
  bksecEnabled: boolean;
  bksecRiskTypeId: string | null;
  bksecRiskTypeName: string;
  bksecFieldValues: Record<string, string>;
  bksecFieldMeta: BksecFieldMeta[];
}

const emptyForm = (): BksecFormState => ({
  bksecEnabled: false,
  bksecRiskTypeId: null,
  bksecRiskTypeName: '',
  bksecFieldValues: {},
  bksecFieldMeta: [],
});

const toId = (value: unknown): string | null => {
  if (value === undefined || value === null || value === '') return null;
  return String(value);
};

/** 表单状态转协议。只输出约定字段，不带详情派生的 target / operator 等。 */
export const buildBksecConfig = (params: Record<string, any> = {}): BksecConfigPayload => {
  const values = (params.bksecFieldValues || {}) as Record<string, string>;
  const meta = Array.isArray(params.bksecFieldMeta) ? params.bksecFieldMeta as BksecFieldMeta[] : [];
  const fieldMappings = meta.length
    ? meta.filter(item => item?.key).map(item => ({
      key: String(item.key),
      name: item.name || '',
      value: values[item.key] ?? '',
      required: !!item.required,
    }))
    : Object.entries(values).map(([key, value]) => ({
      key,
      name: '',
      value: value ?? '',
      required: false,
    }));
  const config: BksecConfigPayload = {
    enabled: !!params.bksecEnabled,
    risk_type_name: params.bksecRiskTypeName || '',
    field_mappings: fieldMappings,
  };
  const riskTypeId = toId(params.bksecRiskTypeId);
  if (riskTypeId) config.risk_type_id = riskTypeId;
  return config;
};

/** 详情或旧字段回填表单。派生字段不进入表单。 */
export const readBksecFormState = (detail: Record<string, any> = {}): BksecFormState => {
  const config = detail.bksec_config;
  if (config && typeof config === 'object') {
    const mappings = Array.isArray(config.field_mappings) ? config.field_mappings : [];
    const fieldValues: Record<string, string> = {};
    const fieldMeta: BksecFieldMeta[] = [];
    mappings.forEach((item: Record<string, any>) => {
      if (!item?.key) return;
      const key = String(item.key);
      fieldValues[key] = item.value ?? '';
      fieldMeta.push({
        key,
        name: item.name || '',
        required: !!item.required,
      });
    });
    return {
      bksecEnabled: !!config.enabled,
      bksecRiskTypeId: toId(config.risk_type_id),
      bksecRiskTypeName: config.risk_type_name || '',
      bksecFieldValues: fieldValues,
      bksecFieldMeta: fieldMeta,
    };
  }
  if (
    detail.bksecEnabled === undefined
    && detail.bksec_enabled === undefined
    && detail.bksecRiskTypeId === undefined
    && detail.bksec_risk_type_id === undefined
    && detail.bksecFieldValues === undefined
    && detail.bksec_field_values === undefined
  ) {
    return emptyForm();
  }
  return {
    bksecEnabled: !!(detail.bksecEnabled ?? detail.bksec_enabled),
    bksecRiskTypeId: toId(detail.bksecRiskTypeId ?? detail.bksec_risk_type_id),
    bksecRiskTypeName: detail.bksecRiskTypeName || '',
    bksecFieldValues: { ...(detail.bksecFieldValues ?? detail.bksec_field_values ?? {}) },
    bksecFieldMeta: Array.isArray(detail.bksecFieldMeta) ? detail.bksecFieldMeta : [],
  };
};
