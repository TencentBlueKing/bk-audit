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
import type { AiMessage } from '@model/ai-assistant/types';

import type {
  ChatMessage,
  SelectedSystem,
} from '../types';

const pickSystems = (data?: Record<string, any> | null): SelectedSystem[] => {
  if (!data) return [];
  if (Array.isArray(data.systems)) {
    return data.systems
      .map((item: any) => ({
        id: String(item?.id ?? item?.system_id ?? ''),
        name: String(item?.name ?? item?.system_name ?? item?.id ?? ''),
      }))
      .filter((item: SelectedSystem) => item.id);
  }
  if (Array.isArray(data.system_ids)) {
    return data.system_ids.map((id: string) => ({
      id: String(id),
      name: String(id),
    }));
  }
  return [];
};

/**
 * 将后端消息映射为当前 UI 卡片模型。
 * 三类消息的 input/output Schema 未冻结，这里只做最小可用映射，下周可集中替换。
 */
export const mapAiMessageToChatMessage = (message: AiMessage): ChatMessage => {
  const outputSystems = pickSystems(message.output_data);
  const systems = outputSystems.length ? outputSystems : pickSystems(message.input_data);
  const systemIds = systems.map(item => item.id);

  if (message.message_type === 'SYSTEM_SELECTION') {
    if (message.status === 'SUCCESS' && systems.length) {
      return {
        id: message.uid,
        role: 'assistant',
        type: 'retrieval-guide',
        systems,
        systemIds,
        apiStatus: message.status,
        messageType: message.message_type,
        errorCode: message.error_code || undefined,
        errorMessage: message.error_message || undefined,
      };
    }
    return {
      id: message.uid,
      role: 'assistant',
      type: 'select-system',
      status: message.status === 'FAILED' ? 'closed' : 'pending',
      systems,
      systemIds,
      apiStatus: message.status,
      messageType: message.message_type,
      errorCode: message.error_code || undefined,
      errorMessage: message.error_message || undefined,
    };
  }

  if (message.message_type === 'NATURAL_LANGUAGE_SEARCH' || message.message_type === 'LOG_SEARCH') {
    const queryText = String(message.input_data?.query_text
      ?? message.input_data?.query
      ?? message.output_data?.query_summary
      ?? '');
    return {
      id: message.uid,
      role: 'assistant',
      type: 'retrieval-result',
      content: queryText,
      apiStatus: message.status,
      messageType: message.message_type,
      errorCode: message.error_code || undefined,
      errorMessage: message.error_message || undefined,
      // Schema 未到前不强行拼 result；有 samples 时下周再补完整映射
      result: undefined,
    };
  }

  return {
    id: message.uid,
    role: 'assistant',
    type: 'text',
    content: message.error_message || message.message_type,
    apiStatus: message.status,
    messageType: message.message_type,
    errorCode: message.error_code || undefined,
    errorMessage: message.error_message || undefined,
  };
};

/** 从消息窗口中取最近一条成功的 SYSTEM_SELECTION */
export const findLatestSuccessSystemSelection = (messages: AiMessage[]): AiMessage | null => {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const item = messages[i];
    if (item.message_type === 'SYSTEM_SELECTION' && item.status === 'SUCCESS') {
      return item;
    }
  }
  return null;
};
