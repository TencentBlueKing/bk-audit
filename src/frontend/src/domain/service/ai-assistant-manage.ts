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
import type { CancelTokenSource } from 'axios';

import type {
  AiAttachmentExportFormat,
  AiAttachmentListParams,
  AiConcreteScope,
  AiConversation,
  AiConversationListParams,
  AiCreateAttachmentParams,
  AiCreateConversationGroupParams,
  AiCreateConversationParams,
  AiCreateMessageParams,
  AiExportConfig,
  AiMessageHistoryParams,
  AiScopeQuery,
  AiSidebarMoveParams,
  AiSidebarNode,
  AiSidebarNodePage,
  AiSidebarNodesParams,
  AiSidebarPinParams,
  AiSidebarSearchParams,
  AiUpdateAttachmentParams,
  AiUpdateMessageParams,
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

  createConversationGroup(params: AiCreateConversationGroupParams) {
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

  fetchConversationList(
    params: AiConversationListParams = {},
    options?: { catchError?: boolean },
  ) {
    return AiAssistantManageSource.getConversationList(params, {
      catchError: options?.catchError,
    })
      .then(({ data }) => (Array.isArray(data) ? data : []));
  },

  fetchConversation(params: { conversation_uid: string }, options?: { silent?: boolean }) {
    return AiAssistantManageSource.getConversation(params, { silent: options?.silent })
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

  clearConversations(params: AiConcreteScope) {
    return AiAssistantManageSource.clearConversations(params)
      .then(({ data }) => data);
  },

  // ---------- 侧栏 ----------

  fetchPinnedNodes(params: AiScopeQuery) {
    return AiAssistantManageSource.getPinnedNodes(params)
      .then(({ data }) => normalizeNodeList(data));
  },

  fetchSidebarNodes(params: AiSidebarNodesParams, options?: { silent?: boolean }) {
    return AiAssistantManageSource.getSidebarNodes(params, { silent: options?.silent })
      .then(({ data }) => normalizeNodePage(data));
  },

  searchSidebar(params: AiSidebarSearchParams) {
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

  /** 编辑并重新执行消息（覆盖当前消息快照） */
  updateMessage(params: AiUpdateMessageParams) {
    return AiAssistantManageSource.updateMessage(params)
      .then(({ data }) => data);
  },

  fetchMessageHistory(params: AiMessageHistoryParams, options?: { silent?: boolean }) {
    return AiAssistantManageSource.getMessageHistory(params, { silent: options?.silent })
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
      .then(({ data }) => {
        // 同步直出为 xlsx Blob（响应拦截器已自动触发浏览器下载）；
        // 降级/异步为 JSON Blob，解析回业务结构（拦截器对 json blob 不触发下载）
        if (typeof Blob !== 'undefined' && data instanceof Blob && data.type && !data.type.includes('json')) {
          return data;
        }
        if (typeof Blob !== 'undefined' && data instanceof Blob) {
          return data.text().then((text) => {
            const parsed = JSON.parse(text);
            // bk_resource 响应统一包装 {result, code, data, message}，业务数据在 data 字段；
            // 对齐拦截器对常规 json 响应的既有解包语义（case 0 后业务方拿到的即 data 字段）
            if (parsed && typeof parsed === 'object' && 'result' in parsed && 'data' in parsed) {
              return parsed.data;
            }
            return parsed;
          });
        }
        return data;
      });
  },

  // ---------- 附件 ----------

  createAttachment(
    params: AiCreateAttachmentParams,
    options?: { catchError?: boolean },
  ) {
    return AiAssistantManageSource.createAttachment(params, {
      catchError: options?.catchError,
    })
      .then(({ data }) => data);
  },

  fetchAttachments(
    params: AiAttachmentListParams = {},
    options?: { catchError?: boolean; cancelTokenSource?: CancelTokenSource },
  ) {
    return AiAssistantManageSource.getAttachments(params, {
      catchError: options?.catchError,
      cancelTokenSource: options?.cancelTokenSource,
    })
      .then(({ data }) => (Array.isArray(data) ? data : []));
  },

  fetchAttachment(
    params: { attachment_uid: string },
    options?: { catchError?: boolean },
  ) {
    return AiAssistantManageSource.getAttachment(params, {
      catchError: options?.catchError,
    })
      .then(({ data }) => data);
  },

  updateAttachment(
    params: AiUpdateAttachmentParams,
    options?: { catchError?: boolean },
  ) {
    return AiAssistantManageSource.updateAttachment(params, {
      catchError: options?.catchError,
    })
      .then(({ data }) => data);
  },

  retryAttachment(
    params: { attachment_uid: string; input_data?: Record<string, any> },
    options?: { catchError?: boolean },
  ) {
    return AiAssistantManageSource.retryAttachment(params, {
      catchError: options?.catchError,
    })
      .then(({ data }) => data);
  },

  fetchAttachmentStreamSnapshot(
    params: { attachment_uid: string },
    options?: { catchError?: boolean },
  ) {
    return AiAssistantManageSource.getAttachmentStreamSnapshot(params, {
      catchError: options?.catchError,
    })
      .then(({ data }) => data);
  },

  exportAttachment(
    params: { attachment_uid: string; export_format: AiAttachmentExportFormat },
    options?: { catchError?: boolean },
  ) {
    return AiAssistantManageSource.exportAttachment(params, {
      catchError: options?.catchError,
    })
      .then(({ data }) => data);
  },
};
