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
import type {
  AiConversation,
  AiCreateConversationParams,
  AiCreateMessageParams,
  AiExportConfig,
  AiMessageHistoryParams,
  AiSidebarMoveParams,
  AiSidebarNode,
  AiSidebarNodePage,
  AiSidebarNodesParams,
  AiSidebarPinParams,
} from '@model/ai-assistant/types';

import AiAssistantManageSource from '../source/ai-assistant-manage';

const normalizeNodeList = (data: AiSidebarNode[] | AiSidebarNodePage | undefined | null): AiSidebarNode[] => {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  return data.results || [];
};

const normalizeNodePage = (data: AiSidebarNode[] | AiSidebarNodePage | undefined | null): AiSidebarNodePage => {
  if (!data) {
    return {
      results: [],
      page: 1,
      page_size: 0,
      num_pages: 0,
      total: 0,
    };
  }
  if (Array.isArray(data)) {
    return {
      results: data,
      page: 1,
      page_size: data.length,
      num_pages: 1,
      total: data.length,
    };
  }
  return {
    ...data,
    results: data.results || [],
  };
};

export default {
  // ---------- 会话分组 ----------

  createConversationGroup(params: { name: string }) {
    return AiAssistantManageSource.createConversationGroup(params)
      .then(({ data }) => data);
  },

  updateConversationGroup(params: { group_uid: string; name: string }) {
    return AiAssistantManageSource.updateConversationGroup(params)
      .then(({ data }) => data);
  },

  deleteConversationGroup(params: { group_uid: string }) {
    return AiAssistantManageSource.deleteConversationGroup(params)
      .then(({ data }) => data);
  },

  // ---------- 会话 ----------

  createConversation(params: AiCreateConversationParams) {
    return AiAssistantManageSource.createConversation(params)
      .then(({ data }) => data as AiConversation);
  },

  fetchConversation(params: { conversation_uid: string }) {
    return AiAssistantManageSource.getConversation(params)
      .then(({ data }) => data);
  },

  updateConversation(params: { conversation_uid: string; title: string }) {
    return AiAssistantManageSource.updateConversation(params)
      .then(({ data }) => data);
  },

  deleteConversation(params: { conversation_uid: string }) {
    return AiAssistantManageSource.deleteConversation(params)
      .then(({ data }) => data);
  },

  clearConversations() {
    return AiAssistantManageSource.clearConversations()
      .then(({ data }) => data);
  },

  // ---------- 侧栏 ----------

  fetchPinnedNodes() {
    return AiAssistantManageSource.getPinnedNodes()
      .then(({ data }) => normalizeNodeList(data));
  },

  fetchSidebarNodes(params: AiSidebarNodesParams = {}) {
    return AiAssistantManageSource.getSidebarNodes(params)
      .then(({ data }) => normalizeNodePage(data));
  },

  searchSidebar(params: { keyword: string }) {
    return AiAssistantManageSource.searchSidebar(params)
      .then(({ data }) => normalizeNodeList(data));
  },

  moveSidebarNode(params: AiSidebarMoveParams) {
    return AiAssistantManageSource.moveSidebarNode(params)
      .then(({ data }) => data);
  },

  pinSidebarNode(params: AiSidebarPinParams) {
    return AiAssistantManageSource.pinSidebarNode(params)
      .then(({ data }) => data);
  },

  // ---------- 消息 ----------

  createMessage(params: AiCreateMessageParams) {
    return AiAssistantManageSource.createMessage(params)
      .then(({ data }) => data);
  },

  fetchMessageHistory(params: AiMessageHistoryParams) {
    return AiAssistantManageSource.getMessageHistory(params)
      .then(({ data }) => data);
  },

  fetchMessage(params: { message_uid: string }) {
    return AiAssistantManageSource.getMessage(params)
      .then(({ data }) => data);
  },

  retryMessage(params: { message_uid: string }) {
    return AiAssistantManageSource.retryMessage(params)
      .then(({ data }) => data);
  },

  /**
   * 预览导出（xlsx blob，中间件会触发下载）
   */
  previewExport(
    params: { message_uid: string; export_config?: AiExportConfig },
    options?: { catchError?: boolean },
  ) {
    return AiAssistantManageSource.previewExport(params, {
      catchError: options?.catchError,
    })
      .then(({ data }) => data);
  },

  /**
   * 全量异步导出
   */
  fullExport(
    params: { message_uid: string; export_config?: AiExportConfig },
    options?: { catchError?: boolean },
  ) {
    return AiAssistantManageSource.fullExport(params, {
      catchError: options?.catchError,
    })
      .then(({ data }) => data);
  },
};
