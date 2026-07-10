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
import type { OutputFields } from './tool-detail';

export interface ToolInputVariable {
  raw_name: string;
  display_name: string;
  description: string;
  required: boolean;
  field_category: string;
  default_value?: unknown;
  raw_default_value?: unknown;
  is_default_value?: boolean;
  choices?: Array<{
    key: string;
    name: string;
  }>;
}

export interface ToolReferencedTable {
  table_name: string | null;
  alias: string | null;
  permission: {
    result: boolean;
  };
}

export interface ToolOutputConfig {
  enable_grouping: boolean;
  groups: Array<{
    name: string;
    output_fields: unknown[];
  }>;
  enable_pagination?: boolean;
  pagination_config?: unknown[];
  result_schema?: unknown;
}

export interface DefaultValueOverrides {
  scenes?: Record<string, Record<string, unknown>>;
  systems?: Record<string, Record<string, unknown>>;
}

export interface ToolConfigPayload {
  property?: {
    scene_id?: number | string;
  };
  referenced_tables?: ToolReferencedTable[];
  input_variable?: ToolInputVariable[];
  output_fields?: OutputFields[];
  output_config?: ToolOutputConfig;
  sql?: string;
  uid?: string;
  api_config?: Record<string, unknown>;
  default_value_overrides?: DefaultValueOverrides;
  updated_at?: string;
  updated_by?: string;
  updated_time?: string;
}

export interface VisibilityPayload {
  visibility_type: 'all_visible' | 'all_scenes' | 'all_systems' | 'specific_scenes' | 'specific_systems' | 'scenes_and_systems';
  scene_ids: number[];
  system_ids: string[];
}

/** 场景级工具创建请求体 */
export interface SceneToolWritePayload {
  uid?: string;
  name: string;
  tags: string[];
  description: string;
  tool_type: string;
  data_search_config_type: string;
  config: ToolConfigPayload;
  scene_id?: number | string;
  updated_time?: string | null;
}

/** 场景级工具更新请求体 */
export interface UpdateSceneToolPayload extends SceneToolWritePayload {
  uid: string;
}

/** 平台级工具创建请求体 */
export interface CreatePlatformToolPayload {
  name: string;
  tags: string[];
  description: string;
  tool_type: string;
  data_search_config_type: string;
  namespace: string;
  status?: string;
  version?: number;
  config: ToolConfigPayload;
  visibility?: VisibilityPayload;
}

/** 平台级工具创建/更新请求体（提交组装结果） */
export type PlatformToolSubmitPayload = CreatePlatformToolPayload | UpdatePlatformToolPayload;

/** 平台级工具更新请求体 */
export interface UpdatePlatformToolPayload {
  uid: string;
  name?: string;
  tags?: string[];
  description?: string;
  tool_type?: string;
  data_search_config_type?: string;
  namespace?: string;
  config?: ToolConfigPayload;
  visibility?: VisibilityPayload;
}

export interface ParseSqlParams {
  sql: string;
  dialect: string;
  with_permission: boolean;
}

export interface EditModelParseSqlParams extends ParseSqlParams {
  uid: string;
}

export interface ToolExecuteVariable {
  raw_name: string;
  value: unknown;
}

export interface ToolExecuteParams {
  tool_variables?: ToolExecuteVariable[];
  page?: number;
  page_size?: number;
  data_source_name?: string;
  params?: Record<string, unknown>;
}

/** 风险详情等场景下钻工具时附带的上下文参数 */
export interface ToolRiskContextParams {
  caller_resource_type?: string;
  caller_resource_id?: string | number;
  drill_field?: string;
  event_start_time?: string;
  event_end_time?: string;
}

export interface ToolExecutePayload extends ToolRiskContextParams {
  uid: string;
  params: ToolExecuteParams;
}

export interface ToolDebugConfig {
  api_config?: Record<string, unknown>;
  input_variable?: ToolInputVariable[];
  output_config?: Pick<ToolOutputConfig, 'enable_grouping' | 'groups'>;
}

export interface ToolDebugParams {
  tool_variables?: ToolExecuteVariable[];
}

export interface ToolDebugPayload {
  tool_type: string;
  config: ToolDebugConfig;
  params: ToolDebugParams;
}
