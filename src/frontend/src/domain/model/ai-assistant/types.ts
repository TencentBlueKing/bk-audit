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

/** 消息业务状态 */
export type AiMessageStatus = 'PROCESSING' | 'SUCCESS' | 'FAILED';

/** 消息类型 */
export type AiMessageType =
  | 'SYSTEM_SELECTION'
  | 'NATURAL_LANGUAGE_SEARCH'
  | 'LOG_SEARCH'
  | string;

/** 侧栏节点类型 */
export type AiSidebarNodeType = 'GROUP' | 'CONVERSATION';

/** 消息历史翻页方向 */
export type AiMessageDirection = 'BEFORE' | 'AFTER';

/** 检索条件字段 */
export interface AiConditionField {
  raw_name: string;
  field_type?: string;
  keys: string[];
}

/** 单条筛选条件（与 NL output / LOG input 同构） */
export interface AiConditionItem {
  field: AiConditionField;
  operator: string;
  filters: any[];
}

/** 统一检索 condition */
export interface AiSearchCondition {
  scope_type: 'system' | string;
  scope_id: string;
  start_time: string;
  end_time: string;
  conditions?: AiConditionItem[];
}

/** SYSTEM_SELECTION 字段项 */
export interface AiSystemFieldItem {
  raw_name: string;
  keys: string[];
  display_name: string;
  nl_name: string;
  description: string;
  allow_operators: string[];
  field_type?: string;
  options?: Array<{ id: string; name: string }> | null;
  sample_value?: any;
}

/** SYSTEM_SELECTION 系统项 */
export interface AiSystemInfo {
  system_id: string;
  name: string;
  standard_fields?: AiSystemFieldItem[];
  extension_fields?: AiSystemFieldItem[];
}

export interface AiOperationHint {
  query_text: string;
}

export interface AiSystemSelectionInput {
  system_ids: string[];
}

export interface AiSystemSelectionOutput {
  systems: AiSystemInfo[];
  common_operations?: AiOperationHint[];
  historical_operations?: AiOperationHint[];
}

export interface AiNaturalLanguageSearchInput {
  query_text: string;
  auto_execute?: boolean;
}

export type AiNlRecognitionErrorCode =
  | 'QUERY_NOT_RECOGNIZED'
  | 'AI_OUTPUT_PARSE_FAILED'
  | 'AI_OUTPUT_INVALID'
  | 'AI_SERVICE_ERROR'
  | 'AI_TIMEOUT'
  | 'PERMISSION_DENIED'
  | string;

export interface AiNlRecognitionError {
  error_code: AiNlRecognitionErrorCode;
  error_message: string;
}

export interface AiNaturalLanguageSearchOutput {
  condition: AiSearchCondition | null;
  error?: AiNlRecognitionError | null;
}

export interface AiLogSearchInput {
  condition: AiSearchCondition;
}

export interface AiLogSearchColumn {
  raw_name: string;
  display_name: string;
  description?: string;
}

export interface AiLogSearchQuerySummary {
  scope_type?: string;
  scope_id?: string;
  time_range?: {
    start_time?: string;
    end_time?: string;
  };
  condition_count?: number;
  source?: 'natural_language' | 'field_condition' | string;
  took_ms?: number;
  executed_at?: string;
}

export interface AiLogSearchOutput {
  total: number;
  columns: AiLogSearchColumn[];
  samples: Record<string, any>[];
  query_summary?: AiLogSearchQuerySummary;
}

export interface AiConversationGroup {
  uid: string;
  name: string;
  created_at?: string;
  updated_at?: string;
}

export interface AiConversation {
  uid: string;
  title: string;
  created_at: string;
  updated_at: string;
  initial_message?: AiMessage;
}

export interface AiMessage {
  uid: string;
  conversation_uid: string;
  parent_message_uid?: string | null;
  message_type: AiMessageType;
  status: AiMessageStatus;
  input_data?: Record<string, any>;
  output_data?: Record<string, any> | null;
  error_code?: string | null;
  error_message?: string | null;
  created_at?: string;
  updated_at?: string;
  supports_feedback?: boolean;
  feedback?: Record<string, any> | null;
  attachments?: any[];
}

export interface AiMessageWindow {
  first_uid: string | null;
  last_uid: string | null;
  has_before: boolean;
  has_after: boolean;
  results: AiMessage[];
}

export interface AiSidebarNodeBase {
  node_type: AiSidebarNodeType;
  node_uid: string;
}

/** 侧栏分组节点（字段以联调文档为准，未给到的字段保持可选） */
export interface AiSidebarGroupNode extends AiSidebarNodeBase {
  node_type: 'GROUP';
  name: string;
  conversation_count?: number;
}

/** 侧栏会话节点 */
export interface AiSidebarConversationNode extends AiSidebarNodeBase {
  node_type: 'CONVERSATION';
  title: string;
  pinned?: boolean;
  group_uid?: string | null;
  group_name?: string | null;
  updated_at?: string;
  created_at?: string;
}

export type AiSidebarNode = AiSidebarGroupNode | AiSidebarConversationNode;

export interface AiSidebarNodePage {
  results: AiSidebarNode[];
  page?: number;
  page_size?: number;
  num_pages?: number;
  total?: number;
}

export interface AiCreateConversationParams {
  title?: string;
  initial_message?: {
    message_type: AiMessageType;
    input_data?: Record<string, any>;
  };
}

export interface AiCreateMessageParams {
  conversation_uid: string;
  message_type: AiMessageType;
  /** NATURAL_LANGUAGE_SEARCH / LOG_SEARCH 可不传，由后端挂最近成功 SYSTEM_SELECTION */
  parent_message_uid?: string | null;
  input_data?: Record<string, any>;
}

export interface AiMessageHistoryParams {
  conversation_uid: string;
  anchor_uid?: string;
  direction?: AiMessageDirection;
  include_content?: boolean;
  limit?: number;
}

export interface AiSidebarNodesParams {
  parent_node_type?: AiSidebarNodeType;
  parent_node_uid?: string;
  page?: number;
  page_size?: number;
}

export interface AiSidebarMoveParams {
  source_node_type: AiSidebarNodeType;
  source_node_uid: string;
  /** 省略表示移到根容器 */
  target_node_type?: AiSidebarNodeType;
  target_node_uid?: string;
  /** 与 after_* 不可同时传；省略且未传 after_* 时表示放到目标容器最前 */
  before_node_type?: AiSidebarNodeType;
  before_node_uid?: string;
  /** 与 before_* 不可同时传；锚点已在容器物理末尾时，source 进入容器末尾 */
  after_node_type?: AiSidebarNodeType;
  after_node_uid?: string;
}

/**
 * 设置/取消置顶。
 * 文档曾写「不改变原分组及列表顺序」，实际接口会把置顶会话从分组/普通列表移除并进入 pinned/；
 * 前端以实际返回为准展示。
 */
export interface AiSidebarPinParams {
  node_type: 'CONVERSATION';
  node_uid: string;
  is_pinned: boolean;
}

/** 全量导出字段范围 */
export type AiExportFieldScope = 'all' | 'standard' | 'ai_standard' | 'snapshot' | 'specified';

export interface AiExportField {
  raw_name: string;
  display_name?: string;
  keys?: string[];
}

export interface AiExportConfig {
  field_scope: AiExportFieldScope;
  /** 为 true 时后端将扩展字段平铺为独立列 */
  flatten_extension?: boolean;
  fields?: AiExportField[];
}

/** POST .../full-export/ 响应 */
export interface AiFullExportResult {
  export_task_id: number;
  status: string;
  /** 兼容任务模型原样返回 */
  id?: number;
  /** 异步导出提示文案（如邮件通知说明） */
  message?: string;
}

/** 导出任务详情（collector_query_task） */
export interface AiExportTaskDetail {
  id: number;
  status: string;
  name?: string;
  error_msg?: string | null;
  total?: number;
  current_records?: number;
  result?: Record<string, any> | null;
}
