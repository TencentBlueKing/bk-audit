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
export type ChatSceneType = 'log';

export type AiUiMessageStatus = 'PROCESSING' | 'SUCCESS' | 'FAILED';

export interface SelectedSystem {
  id: string;
  name: string;
}

export interface RetrievalFilterCondition {
  field: string;
  value: string;
}

export interface RetrievalResultRow {
  startTime: string;
  operator: string;
  accountType: string;
  system: string;
  result: string;
  method: string;
  sourceIp: string;
}

export interface RetrievalResultPayload {
  conditions: RetrievalFilterCondition[];
  toolCount: number;
  thinkSeconds: number;
  title: string;
  totalHit: number;
  previewCount: number;
  rows: RetrievalResultRow[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  type: 'text' | 'select-system' | 'retrieval-guide' | 'retrieval-result';
  content?: string;
  status?: 'pending' | 'confirmed' | 'closed';
  systemIds?: string[];
  systems?: SelectedSystem[];
  result?: RetrievalResultPayload;
  /** 后端消息状态（轮询用） */
  apiStatus?: AiUiMessageStatus;
  messageType?: string;
  errorCode?: string;
  errorMessage?: string;
}

export interface Conversation {
  id: string;
  title: string;
  pinned: boolean;
  groupName?: string;
  sceneType?: ChatSceneType;
  systemIds: string[];
  systems: SelectedSystem[];
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

export interface SelectPromptPayload {
  prompt: string;
  sceneType?: ChatSceneType;
}
