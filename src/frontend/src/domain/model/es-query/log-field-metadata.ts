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
import type { AiLogFieldRef } from '@model/ai-assistant/types';

/** 根字段为 BASIC，JSON 子字段为 EXTENDED */
export type LogFieldCategory = 'BASIC' | 'EXTENDED' | string;

export interface LogFieldMetadataItem {
  /** 可直接回传给统计附件的字段引用 */
  field: AiLogFieldRef;
  category: LogFieldCategory;
  display_name: string;
  description: string;
  type_source: string;
  observed_types: string[];
  allow_operators: string[];
  options?: any[] | null;
  /** 可继续展开下一层；与可统计互相独立 */
  is_expandable: boolean;
  statistics_supported: boolean;
  statistics_kind?: string | null;
  /** 不可直接统计的稳定原因 */
  unsupported_reason?: string | null;
  allowed_metrics: string[];
  sample_values: any[];
  sampled_non_null_count: number;
  coverage: number;
}

export interface LogFieldSampleSummary {
  /** 根字段目录为 false，此时 sampled_count=0 不代表没有日志 */
  sampling_performed: boolean;
  sampled_count: number;
  returned_field_count: number;
  /** 因字段数或预算只返回部分结果 */
  truncated: boolean;
}

export interface LogFieldMetadataResult {
  fields: LogFieldMetadataItem[];
  sample_summary: LogFieldSampleSummary;
}
