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

import type { IFieldConfig } from '@components/search-box/components/render-field-config/config';

// nl2risk_filter 接口响应结果
export interface INL2RiskFilterResponse {
  filter_conditions: Record<string, any>;
  thread_id: string;
  message: string;
}

// 条件标签项
export interface IConditionTag {
  fieldName: string;
  label: string;
  value: any;
  type: string; // datetimerange | string | select | user-selector
  config: IFieldConfig;
  removable?: boolean; // 是否可删除，默认 true
}

// 组件 Props
export interface INLSearchBoxProps {
  fieldConfig: Record<string, IFieldConfig>;
  isExport?: boolean;
  isReassignment?: boolean;
}

// 组件 Emits
export interface INLSearchBoxEmits {
  (e: 'change', value: Record<string, any>, otherValue?: any, isClear?: boolean): void;
  (e: 'export'): void;
  (e: 'batch'): void;
  (e: 'modelValueWatch', value: Record<string, any>): void;
}

// 组件 Expose
export interface INLSearchBoxExposes {
  clearValue: () => void;
  exportData: (val: string[], type: string) => void;
  initSelectedItems: (val: Array<Record<string, any>>) => void;
  getSelectedItemList: () => Array<Record<string, any>>;
}
