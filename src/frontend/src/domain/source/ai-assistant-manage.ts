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
  AiConversationGroup,
  AiCreateConversationParams,
  AiCreateMessageParams,
  AiExportConfig,
  AiFullExportResult,
  AiMessage,
  AiMessageHistoryParams,
  AiMessageWindow,
  AiSidebarMoveParams,
  AiSidebarNode,
  AiSidebarNodePage,
  AiSidebarNodesParams,
  AiSidebarPinParams,
} from '@model/ai-assistant/types';

import Request, {
  type IRequestPayload,
} from '@utils/request';

import ModuleBase from './module-base';

/**
 * AI 助手 HTTP 资源层。
 * Base: /api/v1/ai_assistant/
 * 本期不接 attachments / feedback。
 */
class AiAssistantManage extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1/ai_assistant';
  }

  // ---------- 会话分组 ----------

  createConversationGroup(params: { name: string }, payload = {} as IRequestPayload) {
    return Request.post<AiConversationGroup>(`${this.module}/conversation_groups/`, {
      params,
      payload,
    });
  }

  updateConversationGroup(
    params: { group_uid: string; name: string },
    payload = {} as IRequestPayload,
  ) {
    const { group_uid: groupUid, ...body } = params;
    return Request.patch<AiConversationGroup>(`${this.module}/conversation_groups/${groupUid}/`, {
      params: body,
      payload,
    });
  }

  deleteConversationGroup(params: { group_uid: string }, payload = {} as IRequestPayload) {
    return Request.delete(`${this.module}/conversation_groups/${params.group_uid}/`, {
      payload,
    });
  }

  // ---------- 会话 ----------

  createConversation(params: AiCreateConversationParams, payload = {} as IRequestPayload) {
    return Request.post<AiConversation>(`${this.module}/conversations/`, {
      params,
      payload,
    });
  }

  getConversation(params: { conversation_uid: string }, payload = {} as IRequestPayload) {
    return Request.get<AiConversation>(`${this.module}/conversations/${params.conversation_uid}/`, {
      payload,
    });
  }

  updateConversation(
    params: { conversation_uid: string; title: string },
    payload = {} as IRequestPayload,
  ) {
    const { conversation_uid: conversationUid, ...body } = params;
    return Request.patch<AiConversation>(`${this.module}/conversations/${conversationUid}/`, {
      params: body,
      payload,
    });
  }

  deleteConversation(params: { conversation_uid: string }, payload = {} as IRequestPayload) {
    return Request.delete(`${this.module}/conversations/${params.conversation_uid}/`, {
      payload,
    });
  }

  clearConversations(payload = {} as IRequestPayload) {
    return Request.post<string>(`${this.module}/conversations/clear/`, {
      payload,
    });
  }

  // ---------- 侧栏 ----------

  getPinnedNodes(payload = {} as IRequestPayload) {
    return Request.get<AiSidebarNode[] | AiSidebarNodePage>(`${this.module}/conversation_sidebar/pinned/`, {
      payload,
    });
  }

  getSidebarNodes(params: AiSidebarNodesParams = {}, payload = {} as IRequestPayload) {
    return Request.get<AiSidebarNodePage | AiSidebarNode[]>(`${this.module}/conversation_sidebar/nodes/`, {
      params,
      payload,
    });
  }

  searchSidebar(params: { keyword: string }, payload = {} as IRequestPayload) {
    return Request.get<AiSidebarNode[] | AiSidebarNodePage>(`${this.module}/conversation_sidebar/search/`, {
      params,
      payload,
    });
  }

  moveSidebarNode(params: AiSidebarMoveParams, payload = {} as IRequestPayload) {
    return Request.post(`${this.module}/conversation_sidebar/nodes/move/`, {
      params,
      payload,
    });
  }

  pinSidebarNode(params: AiSidebarPinParams, payload = {} as IRequestPayload) {
    return Request.put(`${this.module}/conversation_sidebar/nodes/pin/`, {
      params,
      payload,
    });
  }

  // ---------- 消息（不含附件/反馈） ----------

  createMessage(params: AiCreateMessageParams, payload = {} as IRequestPayload) {
    return Request.post<AiMessage>(`${this.module}/messages/`, {
      params,
      payload,
    });
  }

  getMessageHistory(params: AiMessageHistoryParams, payload = {} as IRequestPayload) {
    return Request.get<AiMessageWindow>(`${this.module}/messages/`, {
      params,
      payload,
    });
  }

  getMessage(params: { message_uid: string }, payload = {} as IRequestPayload) {
    return Request.get<AiMessage>(`${this.module}/messages/${params.message_uid}/`, {
      payload,
    });
  }

  retryMessage(params: { message_uid: string }, payload = {} as IRequestPayload) {
    return Request.post<AiMessage>(`${this.module}/messages/${params.message_uid}/retry/`, {
      payload,
    });
  }

  /**
   * 预览导出：快照前 100 条，返回 xlsx 二进制流。
   */
  previewExport(params: { message_uid: string }, payload = {} as IRequestPayload) {
    return Request.get(`${this.module}/messages/${params.message_uid}/preview-export/`, {
      responseType: 'blob',
      payload,
    });
  }

  /**
   * 全量导出：异步创建导出任务。
   */
  fullExport(
    params: { message_uid: string; export_config?: AiExportConfig },
    payload = {} as IRequestPayload,
  ) {
    const { message_uid: messageUid, export_config: exportConfig } = params;
    return Request.post<AiFullExportResult>(`${this.module}/messages/${messageUid}/full-export/`, {
      params: {
        export_config: exportConfig || {
          field_scope: 'all',
          flatten_extension: true,
          fields: [],
        },
      },
      payload,
    });
  }
}

export default new AiAssistantManage();
