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
import AiAssistantManageService from '@service/ai-assistant-manage';

import type {
  AiExportConfig,
  AiFullExportResult,
} from '@model/ai-assistant/types';

const resolveExportTaskId = (data: AiFullExportResult | Record<string, any> | null | undefined) => {
  if (!data) return undefined;
  const raw = (data as AiFullExportResult).export_task_id ?? (data as AiFullExportResult).id;
  const id = Number(raw);
  return Number.isFinite(id) && id > 0 ? id : undefined;
};

const parseErrorPayload = async (error: any): Promise<Record<string, any> | undefined> => {
  const data = error?.response?.data;
  if (!data) return undefined;
  if (typeof data === 'object' && !(typeof Blob !== 'undefined' && data instanceof Blob)) {
    return data;
  }
  if (typeof Blob !== 'undefined' && data instanceof Blob) {
    try {
      const text = await data.text();
      const parsed = JSON.parse(text);
      return parsed && typeof parsed === 'object' ? parsed : undefined;
    } catch {
      return undefined;
    }
  }
  return undefined;
};

const resolveExportErrorMessage = async (error: any, fallback: string) => {
  const payload = await parseErrorPayload(error);
  const code = String(error?.code ?? payload?.code ?? '');
  const backendMessage = (
    typeof payload?.message === 'string' ? payload.message : undefined
  ) || error?.message;

  if (code === '036' || code === 'LOG_EXPORT_PERMISSION_DENIED') {
    return backendMessage || '导出权限已失效，请重新申请导出权限';
  }
  if (code === '026' || code === 'INVALID_MESSAGE_STATE') {
    return backendMessage || '当前检索结果不可导出，请重新检索后再试';
  }
  if (code === 'LOG_EXPORT_FAILED') {
    return backendMessage || '导出失败，请稍后重试';
  }
  return backendMessage || fallback;
};

/**
 * 预览导出：下载快照前 N 条（默认最多 100）。
 */
export const exportLogSearchPreview = async (messageUid: string) => {
  try {
    await AiAssistantManageService.previewExport({
      message_uid: messageUid,
      export_config: {
        field_scope: 'ai_standard',
        flatten_extension: true,
        fields: [],
      },
    }, { catchError: true });
  } catch (error: any) {
    throw new Error(await resolveExportErrorMessage(error, '预览导出失败，请稍后重试'));
  }
};

/**
 * 全量导出：创建异步任务，完成后邮件通知（无需轮询）。
 */
export const exportLogSearchFull = async (
  messageUid: string,
  exportConfig: AiExportConfig = { field_scope: 'ai_standard', flatten_extension: true, fields: [] },
): Promise<AiFullExportResult> => {
  try {
    const created = await AiAssistantManageService.fullExport({
      message_uid: messageUid,
      export_config: exportConfig,
    }, { catchError: true });

    const exportTaskId = resolveExportTaskId(created);
    if (!exportTaskId) {
      throw new Error('未获取到导出任务 ID，请稍后重试');
    }

    return created;
  } catch (error: any) {
    throw new Error(await resolveExportErrorMessage(error, '创建全量导出任务失败，请稍后重试'));
  }
};
