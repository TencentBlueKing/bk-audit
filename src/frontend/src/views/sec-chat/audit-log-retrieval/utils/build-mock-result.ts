/*
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
    10|  software distributed under the License is distributed on
  an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
  either express or implied. See the License for the
  specific language governing permissions and limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
*/
import type { RetrievalFilterCondition, RetrievalResultPayload, RetrievalResultRow } from '../../types';

const OPERATORS = ['lihua', 'audit_admin', 'zhangsan', 'wangwu', 'frodomei'];
const SYSTEMS = ['cccc', '云安全审计', '蓝盾', 'TOD 账单系统', 'BKBASE'];
const RESULTS = ['成功', '失败'];
const METHODS = ['API', 'WEB', 'CONSOLE'];
const ACCOUNT_TYPES = ['用户', '管理员', '服务账号'];

const pad = (n: number) => String(n).padStart(2, '0');

const formatTime = (index: number) => {
  const day = 20 - (index % 10);
  const hour = 8 + (index % 10);
  const minute = (index * 7) % 60;
  const second = (index * 13) % 60;
  return `2026-03-${pad(Math.max(day, 1))} ${pad(hour)}:${pad(minute)}:${pad(second)}`;
};

const parseConditions = (query: string): RetrievalFilterCondition[] => {
  const conditions: RetrievalFilterCondition[] = [];
  const text = query.replace(/^条件筛选：/, '').trim();

  // 条件筛选：字段为值，字段为值
  if (query.startsWith('条件筛选：')) {
    text.split('，').forEach((part) => {
      const matched = part.match(/^(.+?)为(.+)$/);
      if (matched) {
        conditions.push({ field: matched[1].trim(), value: matched[2].trim() });
      }
    });
    if (conditions.length) return conditions;
  }

  const timeMatch = text.match(/近\s*(\d+)\s*([天月])/);
  if (timeMatch) {
    conditions.push({ field: '操作起始时间', value: `近 ${timeMatch[1]} ${timeMatch[2]}` });
  } else {
    conditions.push({ field: '操作起始时间', value: '近 7 天' });
  }

  const actionMatch = text.match(/(删除|下载|登录|创建|修改|查询|API)\s*操作?/);
  if (actionMatch) {
    conditions.push({ field: '操作类型', value: actionMatch[1] });
  }

  const operatorMatch = text.match(/(?:查询|操作人)?\s*[「"]?([A-Za-z\u4e00-\u9fa5_]{2,20})[」"]?\s*(?:近|的)/);
  if (operatorMatch && !['查询', '条件筛选', '替换为实际用户'].includes(operatorMatch[1])) {
    conditions.unshift({ field: '操作人', value: operatorMatch[1] });
  } else if (/张三/.test(text)) {
    conditions.unshift({ field: '操作人', value: '张三' });
  }

  if (!conditions.some(item => item.field === '操作人') && !conditions.some(item => item.field === '操作类型')) {
    conditions.push({ field: '操作类型', value: '删除' });
  }

  return conditions.slice(0, 5);
};

const buildTitle = (conditions: RetrievalFilterCondition[], query: string) => {
  const operator = conditions.find(item => item.field === '操作人')?.value;
  const time = conditions.find(item => item.field === '操作起始时间')?.value || '近 7 天';
  const action = conditions.find(item => item.field === '操作类型')?.value || '操作';
  const system = conditions.find(item => item.field === '来源系统')?.value;
  if (query.startsWith('条件筛选：')) {
    const subject = operator || system || '';
    const actionPart = conditions.find(item => item.field === '操作类型') ? `${action}操作` : '操作';
    return subject ? `${subject}${time}的${actionPart}` : `${time}的${actionPart}`;
  }
  if (operator) return `${operator}${time}的${action}操作`;
  return query.replace(/^查询\s*/, '').trim() || '审计日志检索结果';
};

const buildRows = (previewCount: number, operatorHint?: string): RetrievalResultRow[] => (
  Array.from({ length: previewCount }, (_, index) => ({
    startTime: formatTime(index),
    operator: index % 5 === 2 && operatorHint ? operatorHint : OPERATORS[index % OPERATORS.length],
    accountType: ACCOUNT_TYPES[index % ACCOUNT_TYPES.length],
    system: SYSTEMS[index % SYSTEMS.length],
    result: RESULTS[index % RESULTS.length],
    method: METHODS[index % METHODS.length],
    sourceIp: `10.${12 + (index % 20)}.${8 + (index % 30)}.${21 + (index % 200)}`,
  }))
);

/** 本阶段 mock：根据查询文案拼结构化检索结果，后续再接真实 API */
export const buildMockRetrievalResult = (query: string): RetrievalResultPayload => {
  const conditions = parseConditions(query);
  const operatorHint = conditions.find(item => item.field === '操作人')?.value;
  const previewCount = 100;
  return {
    conditions,
    toolCount: 3,
    thinkSeconds: 4.5,
    title: buildTitle(conditions, query),
    totalHit: 128423,
    previewCount,
    rows: buildRows(previewCount, operatorHint === '张三' ? 'zhangsan' : operatorHint),
  };
};
