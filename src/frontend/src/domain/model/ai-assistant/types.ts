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
  | 'USER_INTENT'
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


export type AiTimeShortcut = string | null;

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
  /** 最近一条样本的展示文案；为空时前端回退 sample_value / options */
  sample_value_display?: string | null;
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

/** 与检索页 scope 协议同名同义 */
export type AiScopeType = 'cross_scene' | 'cross_system' | 'scene' | 'system';

/** 会话/分组绑定的具体 scope；创建、移动、清空只接受 scene / system */
export type AiConcreteScopeType = 'scene' | 'system';

export interface AiConcreteScope {
  scope_type: AiConcreteScopeType;
  scope_id: string;
}

/** 侧栏、搜索等列表查询 scope；cross_* 不传 scope_id */
export interface AiScopeQuery {
  scope_type: AiScopeType;
  scope_id?: string;
}

/** 会话 scope 由后端从 Conversation 派生，input_data 不允许携带 scope */
export interface AiSystemSelectionInput {
  /** 一期限定单系统 */
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
  /** 后端识别后回写，前端只读 */
  time_shortcut?: AiTimeShortcut;
}

export type AiNlRecognitionErrorCode =
  | 'UNRECOGNIZED_INTENT'
  | 'SYSTEM_REQUIRED'
  | 'SYSTEM_UNAVAILABLE'
  | 'QUERY_NOT_RECOGNIZED'
  /** 已识别意图，但字段/操作符/条件值无法合法表达；不创建派生消息 */
  | 'INVALID_CONDITION'
  /** 新旧码并存：后端可能下发 AT_* 或历史 AI_* */
  | 'AT_OUTPUT_PARSE_FAILED'
  | 'AT_OUTPUT_INVALID'
  | 'AI_OUTPUT_PARSE_FAILED'
  | 'AI_OUTPUT_INVALID'
  | 'AI_SERVICE_ERROR'
  | 'AI_TIMEOUT'
  | 'PERMISSION_DENIED'
  | string;

/** USER_INTENT SUCCESS 时 output_data.derived_messages 单项（创建时 status 仅为快照） */
export interface AiDerivedMessageRef {
  message_uid: string;
  message_type: AiMessageType;
  status?: AiMessageStatus;
  visible?: boolean | null;
}

export interface AiNlRecognitionError {
  error_code: AiNlRecognitionErrorCode;
  error_message: string;
  candidates?: AiSystemInfo[] | null;
}

export interface AiNaturalLanguageSearchOutput {
  condition: AiSearchCondition | null;
  error?: AiNlRecognitionError | null;
}

export type AiUserIntentType =
  | 'select_system'
  | 'log_search'
  | 'unrecognized'
  | string;

/** 会话 scope 由后端从 Conversation 派生，input_data 不允许携带 scope */
export interface AiUserIntentInput {
  query_text: string;
  auto_execute?: boolean;
  /** 后端识别后回写，前端只读 */
  time_shortcut?: AiTimeShortcut;
}

export interface AiUserIntentOutput {
  intent?: AiUserIntentType;
  system_id?: string;
  message?: string;
  condition?: AiSearchCondition | null;
  error?: AiNlRecognitionError | null;
  /**
   * 意图成功后后端已创建的派生消息名单。
   * 前端应按 message_uid 分别拉取/轮询最新状态；列表内 status 仅创建快照。
   */
  derived_messages?: AiDerivedMessageRef[];
  /** 兼容旧字段；有 derived_messages 时优先用名单 */
  log_search_message_uid?: string;
  selection_message_uid?: string;
}

export interface AiLogSearchInput {
  condition: AiSearchCondition;
  time_shortcut?: AiTimeShortcut;
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

/** 会话摘要：GET /conversations/ 返回，按 updated_at 倒序，含置顶与分组内会话 */
export interface AiConversationSummary {
  uid: string;
  title: string;
  created_at?: string;
  updated_at?: string;
  /** 当前用户在该会话下所有状态的附件总数；筛选条件不缩小此计数 */
  attachment_count?: number;
  /** 按类型计数，无附件的类型为 0。报告侧栏读 AI_ANALYSIS */
  attachment_counts_by_type?: Partial<Record<AiAttachmentType, number>>;
}

export interface AiConversationListParams {
  has_attachments?: boolean;
  attachment_type?: AiAttachmentType;
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
  /** 卡片可见性；false 时前端不渲染整张卡片，缺省按 true */
  visible?: boolean | null;
  input_data?: Record<string, any>;
  output_data?: Record<string, any> | null;
  error_code?: string | null;
  error_message?: string | null;
  /** 任务耗时（秒）；PROCESSING 时为 null，SUCCESS 后有值 */
  duration_seconds?: number | null;
  started_at?: string | null;
  finished_at?: string | null;
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
  /** 节点实际绑定的具体 scope */
  scope_type?: AiConcreteScopeType;
  scope_id?: string;
}

export interface AiConversationGroupSummary {
  uid: string;
  name: string;
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
  /** 所属分组摘要；根会话为 null */
  group?: AiConversationGroupSummary | null;
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

export interface AiCreateConversationParams extends AiConcreteScope {
  title?: string;
  /** 分组内新建时直接挂入，避免建完再 move */
  group_uid?: string;
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

/** PATCH 编辑并重新执行消息（覆盖当前消息快照） */
export interface AiUpdateMessageParams {
  message_uid: string;
  input_data: AiLogSearchInput;
}

export interface AiMessageHistoryParams {
  conversation_uid: string;
  anchor_uid?: string;
  direction?: AiMessageDirection;
  include_content?: boolean;
  limit?: number;
}

export interface AiCreateConversationGroupParams extends AiConcreteScope {
  name: string;
}

export interface AiSidebarNodesParams extends AiScopeQuery {
  parent_node_type?: AiSidebarNodeType;
  parent_node_uid?: string;
  page?: number;
  page_size?: number;
}

export interface AiSidebarSearchParams extends AiScopeQuery {
  keyword: string;
  page?: number;
  page_size?: number;
}

/** 来源、目标和锚点必须属于同一具体 scope */
export interface AiSidebarMoveParams extends AiConcreteScope {
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

/** 附件业务类型；二期分析只注册 AI_ANALYSIS */
export type AiAttachmentType = 'AI_ANALYSIS' | 'AI_STATISTICS' | 'FIELD_STATISTICS' | string;

export type AiAttachmentStatus = 'PROCESSING' | 'SUCCESS' | 'FAILED';

export type AiAnalysisMode = 'DEFAULT' | 'CUSTOM';

export type AiAttachmentExportFormat = 'MARKDOWN' | 'PDF' | string;

export interface AiAttachmentFeedback {
  uid?: string;
  feedback_type?: 'LIKE' | 'DISLIKE' | string;
  [key: string]: any;
}

export interface AiAnalysisInputData {
  analysis_mode: AiAnalysisMode;
  instruction?: string;
}

/** 日志字段引用；字段目录返回后原样回传，不自行拼路径 */
export interface AiLogFieldRef {
  raw_name: string;
  /** JSON 子路径，普通字段为空数组 */
  keys: string[];
  /** 仅类型提示，不决定 statistics_kind */
  field_type?: string;
}

export type AiStatisticsKind = 'NUMERIC' | 'CATEGORICAL' | string;

/** VALUE 为真实类别，OTHER 汇总未入选 TopN 的非缺失类别，MISSING 汇总缺失值 */
export type AiStatisticsGroupKind = 'VALUE' | 'OTHER' | 'MISSING' | string;

export type AiStatisticsInterval = 'AUTO' | 'MINUTE' | 'HOUR' | 'DAY' | string;

export interface AiStatisticsFieldInfo {
  raw_name: string;
  keys: string[];
  display_name: string;
}

export interface AiStatisticsOverview {
  total_count: number;
  present_count: number;
  missing_count: number;
  /** 0～1，总数为 0 时为 null */
  present_ratio: number | null;
}

export interface AiStatisticsDistributionGroup {
  group_id: string;
  kind: AiStatisticsGroupKind;
  value_type?: 'number' | 'string' | 'boolean' | null;
  /** 保留原始标量类型与空字符串；OTHER / MISSING 为 null */
  value: string | number | boolean | null;
  count: number;
  /** 0～1，总数为 0 时为 null */
  ratio: number | null;
}

export interface AiStatisticsDistribution {
  top_n: number;
  has_other: boolean;
  groups: AiStatisticsDistributionGroup[];
}

export interface AiStatisticsCountSeries {
  group_id: string;
  /** 与 bucket_starts 等长同序，空桶为 0 */
  counts: number[];
}

export interface AiStatisticsTimeSeries {
  requested_interval: AiStatisticsInterval;
  effective_interval: AiStatisticsInterval;
  timezone: string;
  bucket_starts: string[];
  series: AiStatisticsCountSeries[];
}

export interface AiStatisticsNumericSummary {
  min: number | null;
  max: number | null;
  avg: number | null;
  /** 近似分位数算法 */
  median: number | null;
  median_is_approximate?: boolean;
  valid_count: number;
  conversion_failed_count: number;
}

/** 统计实际执行范围与预算决策，不代表分页 */
export interface AiStatisticsQuerySummary {
  total_count?: number;
  top_n?: number | null;
  has_other?: boolean;
  scope_id?: string;
  start_time?: string;
  end_time?: string;
  requested_interval?: AiStatisticsInterval | null;
  effective_interval?: AiStatisticsInterval | null;
  timezone?: string;
  complete?: boolean;
}

/** FIELD_STATISTICS 成功产物 */
export interface AiFieldStatisticsOutput {
  field: AiStatisticsFieldInfo;
  statistics_kind: AiStatisticsKind;
  overview: AiStatisticsOverview;
  distribution: AiStatisticsDistribution;
  time_series: AiStatisticsTimeSeries;
  /** 仅 NUMERIC 返回 */
  numeric_summary: AiStatisticsNumericSummary | null;
  query_summary?: AiStatisticsQuerySummary;
}

/** AI_STATISTICS 成功产物：图表配置标签内未解析原文 */
export interface AiStatisticsContentOutput {
  content: string;
}

export interface AiFieldStatisticsInputData {
  field: AiLogFieldRef;
  /** 不传用后端默认（10） */
  top_n?: number;
  interval?: AiStatisticsInterval;
}

export interface AiStatisticsInputData {
  instruction: string;
}

/**
 * 附件产物：AI_ANALYSIS 为 markdown 对象，FIELD_STATISTICS 为固定语义包，
 * AI_STATISTICS 为 { content } 原文。取 markdown 用 attachmentMarkdown 收窄。
 */
export type AiAttachmentOutputData =
  | { markdown?: string; [key: string]: any }
  | AiFieldStatisticsOutput
  | AiStatisticsContentOutput
  | any[]
  | string
  | null;

export interface AiAttachment {
  uid: string;
  source_message_uid: string;
  attachment_type: AiAttachmentType;
  status: AiAttachmentStatus;
  title?: string;
  content_updated_at?: string | null;
  input_data?: Record<string, any> | null;
  output_data?: AiAttachmentOutputData | null;
  error_code?: string | null;
  error_message?: string | null;
  supports_feedback?: boolean;
  is_stream?: boolean;
  export_formats?: AiAttachmentExportFormat[];
  feedback?: AiAttachmentFeedback | null;
  created_at?: string;
  updated_at?: string;
}

export interface AiAttachmentListItem {
  uid: string;
  attachment_type: AiAttachmentType;
  status: AiAttachmentStatus;
  title?: string;
  created_at?: string;
  content_updated_at?: string | null;
  source_message?: {
    uid: string;
    message_type?: string;
    created_at?: string;
  };
  conversation?: {
    uid: string;
    title?: string;
    created_at?: string;
    updated_at?: string;
  };
  supports_feedback?: boolean;
  export_formats?: AiAttachmentExportFormat[];
  /** 与详情一致；无错误时后端返回空字符串，失败原因不必再拉详情 */
  error_code?: string | null;
  error_message?: string | null;
}

export interface AiCreateAttachmentParams {
  message_uid: string;
  attachment_type: AiAttachmentType;
  input_data: AiAnalysisInputData | Record<string, any>;
}

export interface AiUpdateAttachmentParams {
  attachment_uid: string;
  title?: string;
  output_data?: {
    markdown: string;
    [key: string]: any;
  };
}

export interface AiAttachmentListParams {
  attachment_type?: AiAttachmentType | AiAttachmentType[];
  status?: AiAttachmentStatus | AiAttachmentStatus[];
  keyword?: string;
  conversation_uid?: string;
  source_message_uid?: string;
  /** 1–100；不传返回全部匹配附件 */
  limit?: number;
  /** content_updated_at | created_at | updated_at | title，前缀 - 倒序，可逗号分隔；默认 -content_updated_at */
  sort?: string;
}

export interface AiStreamSnapshotEvent {
  event?: string;
  stream_id?: string | null;
  data?: Record<string, any>;
}

export interface AiStreamSnapshot {
  events: AiStreamSnapshotEvent[];
  execution_id: string | null;
  latest_stream_id?: string | null;
  archive_status?: 'COMPLETE' | 'DEGRADED' | 'TRUNCATED' | string;
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
