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

import RiskManageService from '@service/risk-manage';
import StrategyManageService from '@service/strategy-manage';

import type { IFieldConfig } from '@components/search-box/components/render-field-config/config';

export default {
  risk_id: {
    label: '风险ID',
    type: 'string',
    required: false,
  },
  strategy_id: {
    label: '风险命中策略',
    type: 'select',
    required: false,
    service: StrategyManageService.fetchScopedStrategyList,
    labelName: 'label',
    valName: 'value',
    defaultParams: {
      risk_view_type: 'processed',
      start_time: dayjs(Date.now() - (86400000 * 182)).format('YYYY-MM-DD HH:mm:ss'),
      end_time: dayjs().format('YYYY-MM-DD HH:mm:ss'),
    },
  },
  tags: {
    label: '风险标签',
    type: 'select',
    required: false,
    service: RiskManageService.fetchRiskTags,
    defaultParams: {
      risk_view_type: 'processed',
      start_time: dayjs(Date.now() - (86400000 * 182)).format('YYYY-MM-DD HH:mm:ss'),
      end_time: dayjs().format('YYYY-MM-DD HH:mm:ss'),
    },
  },
  datetime: {
    label: '首次发现时间',
    type: 'datetimerange',
    required: false,
  },
  operator: {
    label: '责任人',
    type: 'user-selector',
    required: false,
  },
  status: {
    label: '处理状态',
    type: 'select',
    required: false,
    service: RiskManageService.fetchRiskStatusCommon,
    filterList: ['new'],
  },
  current_operator: {
    label: '当前处理人',
    type: 'user-selector',
    required: false,
  },
  event_content: {
    label: '风险描述',
    type: 'string',
    required: false,
  },
  risk_level: {
    label: '风险等级',
    type: 'select',
    required: false,
    labelName: 'label',
    valName: 'value',
    service: () => Promise.resolve(StrategyManageService.fetchStrategyCommon().then(data => data.risk_level)),
  },
  title: {
    label: '风险标题',
    type: 'string',
    required: false,
  },
  notice_users: {
    label: '关注人',
    type: 'user-selector',
    required: false,
  },
} as Record<string, IFieldConfig>;
