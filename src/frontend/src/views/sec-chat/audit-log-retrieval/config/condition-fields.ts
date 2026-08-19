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
import dayjs from 'dayjs';

import type { IFieldConfig } from '@components/search-box/components/render-field-config/config';

import type { SelectedSystem } from '../../types';

const toOptions = (names: string[]) => names.map(name => ({ id: name, name }));

export const DATETIME_SHORTCUT_LABEL_MAP: Record<string, string> = {
  'now-1d': '近1天',
  'now-3d': '近3天',
  'now-7d': '近7天',
  'now-14d': '近14天',
  'now-1M': '近1月',
  'now-3M': '近3月',
  'now-6M': '近6月',
  'now-12M': '近12月',
};

export const COMMON_FIELD_KEYS = [
  'datetime',
  'username',
  'user_identify_type',
  'system_id',
  'result_code',
  'access_type',
  'access_source_ip',
  'event_id',
  'request_id',
];

export const EXTEND_FIELD_KEYS = [
  'request_path',
  'http_method',
  'ins_cu_content',
  'pipeline_id',
  'pipeline_name',
  'project_id',
  'build_number',
  'trigger_type',
  'risk_level',
  'alarm_strategy',
  'resource_type',
  'action_name',
  'bill_period',
  'cost_subject',
];

export const FIELD_LABEL_TO_KEY: Record<string, string> = {
  操作起始时间: 'datetime',
  操作人: 'username',
  操作人账号类型: 'user_identify_type',
  来源系统: 'system_id',
  操作结果: 'result_code',
  操作途径: 'access_type',
  来源IP: 'access_source_ip',
  事件ID: 'event_id',
  请求ID: 'request_id',
  请求路径: 'request_path',
  请求方法: 'http_method',
  ins_cu_content: 'ins_cu_content',
  蓝盾流水线ID: 'pipeline_id',
  蓝盾流水线名称: 'pipeline_name',
  项目ID: 'project_id',
  构建号: 'build_number',
  触发方式: 'trigger_type',
  风险等级: 'risk_level',
  告警策略: 'alarm_strategy',
  资源类型: 'resource_type',
  操作动作: 'action_name',
  账单周期: 'bill_period',
  费用科目: 'cost_subject',
};

const FALLBACK_SYSTEMS: SelectedSystem[] = [
  { id: 'cetus_tk', name: 'cetus_tk' },
  { id: 'bk_ci', name: '蓝盾' },
  { id: 'cloud_audit', name: '云安全审计' },
  { id: 'iam', name: '权限中心' },
  { id: 'tod_bill', name: 'TOD账单系统' },
];

export const createDefaultDatetime = () => ([
  dayjs(Date.now() - (86400000 * 182)).format('YYYY-MM-DD HH:mm:ss'),
  dayjs().format('YYYY-MM-DD HH:mm:ss'),
]);

export const createDefaultDatetimeOrigin = () => ([
  'now-6M',
  'now',
]);

export const createConditionFieldConfig = (systems: SelectedSystem[] = []): Record<string, IFieldConfig> => {
  const systemOptions = (systems.length ? systems : FALLBACK_SYSTEMS).map(item => ({
    id: item.id,
    name: item.name,
  }));

  return {
    datetime: {
      label: '操作起始时间',
      type: 'datetimerange',
      required: true,
    },
    username: {
      label: '操作人',
      type: 'user-selector',
      required: false,
    },
    user_identify_type: {
      label: '操作人账号类型',
      type: 'select',
      required: false,
      service: () => Promise.resolve(toOptions(['个人账号', '平台账号', '服务账号'])),
    },
    system_id: {
      label: '来源系统',
      type: 'select',
      required: false,
      service: () => Promise.resolve(systemOptions),
      formatLabel: item => `${item.name}(${item.id})`,
    },
    result_code: {
      label: '操作结果',
      type: 'select',
      required: false,
      service: () => Promise.resolve(toOptions(['成功', '失败'])),
    },
    access_type: {
      label: '操作途径',
      type: 'select',
      required: false,
      service: () => Promise.resolve(toOptions(['API', 'WEB', 'CONSOLE'])),
    },
    access_source_ip: {
      label: '来源IP',
      type: 'string',
      required: false,
    },
    event_id: {
      label: '事件ID',
      type: 'string',
      required: false,
    },
    request_id: {
      label: '请求ID',
      type: 'string',
      required: false,
    },
    request_path: {
      label: '请求路径',
      type: 'string',
      required: false,
    },
    http_method: {
      label: '请求方法',
      type: 'select',
      required: false,
      multiple: false,
      service: () => Promise.resolve(toOptions(['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])),
    },
    ins_cu_content: {
      label: 'ins_cu_content',
      type: 'string',
      required: false,
    },
    pipeline_id: {
      label: '蓝盾流水线ID',
      type: 'string',
      required: false,
    },
    pipeline_name: {
      label: '蓝盾流水线名称',
      type: 'string',
      required: false,
    },
    project_id: {
      label: '项目ID',
      type: 'string',
      required: false,
    },
    build_number: {
      label: '构建号',
      type: 'string',
      required: false,
    },
    trigger_type: {
      label: '触发方式',
      type: 'string',
      required: false,
    },
    risk_level: {
      label: '风险等级',
      type: 'select',
      required: false,
      multiple: false,
      service: () => Promise.resolve(toOptions(['高', '中', '低'])),
    },
    alarm_strategy: {
      label: '告警策略',
      type: 'string',
      required: false,
    },
    resource_type: {
      label: '资源类型',
      type: 'string',
      required: false,
    },
    action_name: {
      label: '操作动作',
      type: 'string',
      required: false,
    },
    bill_period: {
      label: '账单周期',
      type: 'string',
      required: false,
    },
    cost_subject: {
      label: '费用科目',
      type: 'string',
      required: false,
    },
  };
};
