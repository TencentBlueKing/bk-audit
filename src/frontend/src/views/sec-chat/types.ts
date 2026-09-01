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
import type { AiSearchCondition } from '@model/ai-assistant/types';

export type ChatSceneType = 'log';

export type AiUiMessageStatus = 'PROCESSING' | 'SUCCESS' | 'FAILED';

export interface SelectedSystem {
  id: string;
  name: string;
}

export interface SystemFieldOption {
  id: string;
  name: string;
}

/** 引导卡 / 条件筛选用的字段行（来自 SYSTEM_SELECTION） */
export interface SystemFieldRow {
  rawName: string;
  keys: string[];
  displayName: string;
  nlName: string;
  description: string;
  allowOperators: string[];
  fieldType?: string;
  options?: SystemFieldOption[];
  /** 是否为扩展字段（keys 非空） */
  isExtension?: boolean;
  sampleValue?: any;
  systemId?: string;
  systemName?: string;
}

/** 扩展字段条件值（含操作符） */
export interface LogFieldConditionValue {
  operator: string;
  value: string;
}

export interface RetrievalFilterCondition {
  field: string;
  value: string;
}

export interface RetrievalResultColumn {
  rawName: string;
  displayName: string;
  description?: string;
}

export interface RetrievalResultPayload {
  conditions: RetrievalFilterCondition[];
  /** 原始结构化条件，供二次编辑后重新检索 */
  rawCondition?: AiSearchCondition;
  toolCount: number;
  thinkSeconds: number;
  title: string;
  totalHit: number;
  previewCount: number;
  /** 是否需要展示「仅预览前 N 条」文案 */
  showPreviewHint: boolean;
  columns: RetrievalResultColumn[];
  /** 行数据：key 为 column.rawName */
  rows: Record<string, any>[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  type: 'text' | 'select-system' | 'retrieval-guide' | 'retrieval-result';
  content?: string;
  status?: 'pending' | 'confirmed' | 'closed';
  systemIds?: string[];
  systems?: SelectedSystem[];
  /** SYSTEM_SELECTION 推荐问法 */
  commonOperations?: string[];
  historicalOperations?: string[];
  standardFields?: SystemFieldRow[];
  extensionFields?: SystemFieldRow[];
  result?: RetrievalResultPayload;
  /** 后端消息状态（轮询用） */
  apiStatus?: AiUiMessageStatus;
  messageType?: string;
  errorCode?: string;
  errorMessage?: string;
  /** NL 识别失败（SUCCESS + output_data.error） */
  recognitionError?: {
    code: string;
    message: string;
  };
  parentMessageUid?: string | null;
  /** 条件修改后重新检索的消息，需在列表展示（区别于条件卡内嵌检索） */
  showInMessageList?: boolean;
}

export interface Conversation {
  id: string;
  title: string;
  pinned: boolean;
  groupName?: string;
  sceneType?: ChatSceneType;
  systemIds: string[];
  systems: SelectedSystem[];
  /** 最近成功 SYSTEM_SELECTION 的字段上下文 */
  standardFields?: SystemFieldRow[];
  extensionFields?: SystemFieldRow[];
  commonOperations?: string[];
  historicalOperations?: string[];
  messages: ChatMessage[];
  createdAt: number;
  /** 本地草稿：确认系统前尚未落库 */
  isDraft?: boolean;
  /**
   * 是否已完成过消息历史拉取。
   * 用于区分「从未拉取」与「拉取过但列表为空」，避免空会话反复请求。
   */
  messagesHydrated?: boolean;
  /** 当前有效 SYSTEM_SELECTION 消息 UID */
  selectedSystemMessageUid?: string | null;
  messageFirstUid?: string | null;
  messageLastUid?: string | null;
  hasBeforeMessages?: boolean;
  hasAfterMessages?: boolean;
}

export interface Group {
  id: string;
  name: string;
  conversationCount?: number;
  /** 是否已拉取过该分组下的会话列表 */
  childrenLoaded?: boolean;
  /** 分组子节点加载中 */
  childrenLoading?: boolean;
}

/** 侧栏根层节点顺序项（与后端 nodes/ 返回顺序一致） */
export type RootSidebarItem =
  | { kind: 'conversation'; id: string }
  | { kind: 'group'; id: string };

/** 根层拖拽排序锚点 */
export interface RootReorderPayload {
  beforeId?: string;
  beforeKind?: 'group' | 'conversation';
  toEnd?: boolean;
}

export interface SelectPromptPayload {
  prompt: string;
  sceneType?: ChatSceneType;
}
