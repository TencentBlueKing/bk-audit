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
  AiAttachment,
  AiStreamSnapshot,
} from '@model/ai-assistant/types';

const POLL_INTERVAL_MS = 2000;
const WAIT_START_BACKOFF_MS = [1000, 2000, 4000, 8000];
const PLATFORM_STREAM_END = 'platform.stream_end';
const PLATFORM_STREAM_RESET = 'platform.stream_reset';

export interface FollowAttachmentHandle {
  stop: () => void;
}

export interface FollowAttachmentOptions {
  attachmentUid: string;
  /** 重试前的 execution_id；读到相同值时继续等待新代际 */
  previousExecutionId?: string | null;
  onDetail: (attachment: AiAttachment) => void;
  onRebuildProcess?: () => void;
  onProcessEvent?: (data: Record<string, any>, streamId?: string) => void;
  onWaitingStart?: () => void;
  onArchiveIncomplete?: () => void;
  onExecutionId?: (executionId: string | null) => void;
  onProcessParseError?: () => void;
}

const sleep = (ms: number, isAborted: () => boolean) => new Promise<void>((resolve) => {
  const timer = window.setTimeout(resolve, ms);
  if (isAborted()) {
    window.clearTimeout(timer);
    resolve();
  }
});

const buildStreamUrl = (
  attachmentUid: string,
  executionId: string,
  lastStreamId?: string | null,
) => {
  const prefix = String(window.PROJECT_CONFIG?.AJAX_URL_PREFIX || '').replace(/\/$/, '');
  const params = new URLSearchParams({ execution_id: executionId });
  if (lastStreamId) {
    params.set('last_stream_id', lastStreamId);
  }
  return `${prefix}/api/v1/ai_assistant/attachments/${attachmentUid}/stream/?${params.toString()}`;
};

const isTerminalStatus = (status?: string) => status === 'SUCCESS' || status === 'FAILED';

const parseSseData = (raw: string): Record<string, any> | null => {
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch {
    return null;
  }
};

const consumeSnapshotEvents = (
  snapshot: AiStreamSnapshot,
  options: FollowAttachmentOptions,
) => {
  let sawEnd = false;
  let sawReset = false;
  snapshot.events?.forEach((item) => {
    const eventName = item.event || '';
    if (eventName === PLATFORM_STREAM_END) {
      sawEnd = true;
      return;
    }
    if (eventName === PLATFORM_STREAM_RESET) {
      sawReset = true;
      return;
    }
    if (item.data && typeof item.data === 'object') {
      options.onProcessEvent?.(item.data, item.stream_id || undefined);
    }
  });
  if (snapshot.archive_status && snapshot.archive_status !== 'COMPLETE') {
    options.onArchiveIncomplete?.();
  }
  return { sawEnd, sawReset };
};

export const followAttachment = (options: FollowAttachmentOptions): FollowAttachmentHandle => {
  let aborted = false;
  let eventSource: EventSource | null = null;
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let waitAttempt = 0;
  /** 已被重置、不可再订阅的代际；后端自动重试会换 execution，读到它就退避等新代际 */
  let staleExecutionId: string | null = options.previousExecutionId || null;

  const isAborted = () => aborted;

  const clearTimers = () => {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  };

  const stop = () => {
    aborted = true;
    clearTimers();
  };

  const fetchDetail = () => AiAssistantManageService.fetchAttachment({
    attachment_uid: options.attachmentUid,
  }, { catchError: true });

  const fetchSnapshot = () => AiAssistantManageService.fetchAttachmentStreamSnapshot({
    attachment_uid: options.attachmentUid,
  }, { catchError: true });

  const pollDetail = () => {
    const tick = async () => {
      if (aborted) return;
      try {
        const detail = await fetchDetail();
        if (aborted) return;
        options.onDetail(detail);
        if (isTerminalStatus(detail.status)) {
          clearTimers();
        }
      } catch {
        // 轮询失败保持当前态，下一轮再试
      }
    };
    void tick();
    pollTimer = setInterval(tick, POLL_INTERVAL_MS);
  };

  const subscribeStream = (executionId: string, lastStreamId?: string | null) => {
    clearTimers();
    const source = new EventSource(
      buildStreamUrl(options.attachmentUid, executionId, lastStreamId),
      { withCredentials: true },
    );
    eventSource = source;

    source.onmessage = (event) => {
      if (aborted) return;
      if (!event.data) return;
      const data = parseSseData(event.data);
      if (!data) {
        options.onProcessParseError?.();
        source.close();
        if (eventSource === source) eventSource = null;
        void recoverFromDetail();
        return;
      }
      options.onProcessEvent?.(data, event.lastEventId || undefined);
    };
    source.addEventListener(PLATFORM_STREAM_END, () => {
      source.close();
      if (eventSource === source) eventSource = null;
      void refreshTerminal();
    });
    source.addEventListener(PLATFORM_STREAM_RESET, () => {
      source.close();
      if (eventSource === source) eventSource = null;
      staleExecutionId = executionId;
      void recoverFromDetail();
    });
    source.onerror = () => {
      source.close();
      if (eventSource === source) eventSource = null;
      if (!aborted) {
        void (async () => {
          await sleep(1000, isAborted);
          if (!aborted) {
            await recoverFromDetail();
          }
        })();
      }
    };
  };

  const refreshTerminal = async () => {
    if (aborted) return;
    try {
      const detail = await fetchDetail();
      if (aborted) return;
      options.onDetail(detail);
      if (detail.status === 'PROCESSING') {
        await recoverFromDetail();
      }
    } catch {
      if (!aborted) {
        pollDetail();
      }
    }
  };

  const recoverFromDetail = async (): Promise<void> => {
    if (aborted) return;
    try {
      const detail = await fetchDetail();
      if (aborted) return;
      options.onDetail(detail);
      if (isTerminalStatus(detail.status)) {
        clearTimers();
        return;
      }
      if (!detail.is_stream) {
        pollDetail();
        return;
      }
      await recoverStream(detail);
    } catch {
      if (!aborted) {
        pollDetail();
      }
    }
  };

  const recoverStream = async (current?: AiAttachment): Promise<void> => {
    if (aborted) return;
    let detail = current;
    if (!detail) {
      detail = await fetchDetail();
      if (aborted) return;
      options.onDetail(detail);
    }
    if (isTerminalStatus(detail.status)) {
      clearTimers();
      return;
    }
    const snapshot = await fetchSnapshot();
    if (aborted) return;

    const executionId = snapshot.execution_id;
    options.onExecutionId?.(executionId || null);
    if (!executionId) {
      options.onWaitingStart?.();
      const delay = WAIT_START_BACKOFF_MS[Math.min(waitAttempt, WAIT_START_BACKOFF_MS.length - 1)];
      waitAttempt += 1;
      await sleep(delay, isAborted);
      if (!aborted) {
        await recoverFromDetail();
      }
      return;
    }

    if (staleExecutionId && executionId === staleExecutionId) {
      options.onWaitingStart?.();
      const delay = WAIT_START_BACKOFF_MS[Math.min(waitAttempt, WAIT_START_BACKOFF_MS.length - 1)];
      waitAttempt += 1;
      await sleep(delay, isAborted);
      if (!aborted) {
        await recoverFromDetail();
      }
      return;
    }

    waitAttempt = 0;
    options.onRebuildProcess?.();
    const { sawEnd, sawReset } = consumeSnapshotEvents(snapshot, options);
    if (sawReset) {
      staleExecutionId = executionId;
      await recoverFromDetail();
      return;
    }
    if (sawEnd) {
      await refreshTerminal();
      return;
    }
    subscribeStream(executionId, snapshot.latest_stream_id);
  };

  void recoverFromDetail();

  return { stop };
};
