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

export interface VariableItem {
  token: string;
  label: string;
  sample: string;
  insertText: string;
}

export interface VariableGroup {
  key: 'risk' | 'event' | 'ai';
  label: string;
  items: VariableItem[];
}

export const DEFAULT_RISK_FIELDS: Array<{ token: string; label: string }> = [
  { token: 'risk_id', label: '风险ID' },
  { token: 'risk_level', label: '风险等级' },
  { token: 'event_type', label: '事件类型' },
  { token: 'risk_tags', label: '风险标签' },
  { token: 'strategy_name', label: '策略名称' },
  { token: 'status', label: '状态' },
  { token: 'operator', label: '责任人' },
  { token: 'current_operator', label: '当前责任人' },
  { token: 'notice_users', label: '关注人' },
  { token: 'event_time', label: '事件时间' },
  { token: 'event_end_time', label: '事件结束时间' },
  { token: 'last_operate_time', label: '最近操作时间' },
  { token: 'risk_label', label: '风险标记' },
  { token: 'rule_id', label: '规则ID' },
  { token: 'event_content', label: '事件内容' },
  { token: 'risk_hazard', label: '风险危害' },
  { token: 'risk_guidance', label: '处理指引' },
];

const sampleOf = (sample: Record<string, string>, token: string) => {
  const value = sample?.[token];
  return value === undefined || value === null ? '' : String(value);
};

export const buildVariableGroups = (options: {
  riskFields?: Array<{ field_name?: string; display_name?: string }>;
  eventFields?: Array<{ field_name?: string; display_name?: string; prefix?: string; example?: string }>;
  aiVariables?: Array<{ name?: string; prompt_template?: string }>;
  strategyType?: string;
  sample?: Record<string, string>;
}): VariableGroup[] => {
  const sample = options.sample || {};
  const configuredRisk = (options.riskFields || []).filter(item => item?.field_name);
  const riskSource = configuredRisk.length
    ? configuredRisk.map(item => ({ token: item.field_name as string, label: item.display_name || item.field_name as string }))
    : DEFAULT_RISK_FIELDS;
  const groups: VariableGroup[] = [
    {
      key: 'risk',
      label: '风险字段',
      items: riskSource.map(item => ({
        token: item.token,
        label: item.label,
        sample: sampleOf(sample, item.token),
        insertText: `{{ risk.${item.token} }}`,
      })),
    },
  ];

  const eventItems = (options.eventFields || [])
    .filter(item => item?.field_name && item.prefix !== 'ai' && !String(item.field_name).startsWith('ai.'))
    .map((item) => {
      const token = item.prefix ? `${item.prefix}["${item.field_name}"]` : String(item.field_name);
      const insertText = `{{ ${token} }}`;
      return {
        token,
        label: item.display_name || String(item.field_name),
        sample: item.example || sampleOf(sample, String(item.field_name)),
        insertText,
      };
    });
  groups.push({ key: 'event', label: '事件字段', items: eventItems });

  if (options.strategyType === 'model') {
    const aiItems = (options.aiVariables || [])
      .filter(item => item?.name)
      .map((item) => {
        const name = String(item.name);
        const token = name.startsWith('ai.') ? name : `ai.${name}`;
        return {
          token,
          label: name.replace(/^ai\./, ''),
          sample: sampleOf(sample, token),
          insertText: `{{ ${token} }}`,
        };
      });
    if (aiItems.length) {
      groups.push({ key: 'ai', label: 'AI变量', items: aiItems });
    }
  }
  return groups;
};
