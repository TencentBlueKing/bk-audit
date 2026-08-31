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
import EsQueryService from '@service/es-query';

import type {
  AiExportConfig,
  AiExportTaskDetail,
  AiFullExportResult,
} from '@model/ai-assistant/types';

const POLL_INTERVAL_MS = 2500;
const POLL_MAX_ATTEMPTS = 120; // ~5 分钟

const PENDING_STATUSES = new Set(['READY', 'RUNNING']);
const SUCCESS_STATUS = 'SUCCESS';
const FAILURE_STATUSES = new Set(['FAILURE', 'FAILED', 'EXPIRED']);

const sleep = (ms: number) => new Promise<void>((resolve) => {
  setTimeout(resolve, ms);
});

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
    await AiAssistantManageService.previewExport({ message_uid: messageUid }, { catchError: true });
  } catch (error: any) {
    throw new Error(await resolveExportErrorMessage(error, '预览导出失败，请稍后重试'));
  }
};

/**
 * 轮询导出任务直至成功/失败，成功后触发下载。
 */
export const waitAndDownloadExportTask = async (exportTaskId: number) => {
  for (let attempt = 0; attempt < POLL_MAX_ATTEMPTS; attempt += 1) {
    let detail: AiExportTaskDetail;
    try {
      detail = await EsQueryService.fetchQueryTask(
        { id: exportTaskId },
        { catchError: true },
      ) as AiExportTaskDetail;
    } catch (error: any) {
      throw new Error(await resolveExportErrorMessage(error, '查询导出任务失败，请稍后重试'));
    }

    const status = String(detail?.status || '').toUpperCase();
    if (status === SUCCESS_STATUS) {
      try {
        await EsQueryService.downloadQueryTask(
          { id: exportTaskId },
          { catchError: true },
        );
      } catch (error: any) {
        throw new Error(await resolveExportErrorMessage(error, '下载导出文件失败，请稍后重试'));
      }
      return;
    }

    if (FAILURE_STATUSES.has(status)) {
      throw new Error(detail?.error_msg || '导出失败，请稍后重试');
    }

    if (!PENDING_STATUSES.has(status) && status) {
      throw new Error(detail?.error_msg || `导出任务状态异常：${status}`);
    }

    await sleep(POLL_INTERVAL_MS);
  }

  throw new Error('导出耗时较长，任务仍在处理中，请稍后在导出任务列表中下载');
};

/**
 * 全量导出：创建异步任务 → 轮询 → 下载。
 */
export const exportLogSearchFull = async (
  messageUid: string,
  exportConfig: AiExportConfig = { field_scope: 'all', flatten_extension: true, fields: [] },
) => {
  let created: AiFullExportResult;
  try {
    created = await AiAssistantManageService.fullExport({
      message_uid: messageUid,
      export_config: exportConfig,
    }, { catchError: true });
  } catch (error: any) {
    throw new Error(await resolveExportErrorMessage(error, '创建全量导出任务失败，请稍后重试'));
  }

  const exportTaskId = resolveExportTaskId(created);
  if (!exportTaskId) {
    throw new Error('未获取到导出任务 ID，请稍后重试');
  }

  await waitAndDownloadExportTask(exportTaskId);
};
