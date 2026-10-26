<!--
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
-->
<template>
  <audit-sideslider
    v-model:is-show="isShow"
    ext-cls="execution-detail-sideslider"
    :show-footer="false"
    show-header-slot
    :title="t('执行详情')"
    :width="960">
    <template #header>
      <div class="execution-detail-header">
        <span class="header-title">{{ t('执行详情') }}</span>
        <span class="header-split" />
        <span
          v-bk-tooltips="lineTip('header-task-name', detail?.task_name || '')"
          class="header-sub"
          @mouseenter="syncOverflow($event, 'header-task-name')">
          {{ detail?.task_name || '--' }}
        </span>
        <span
          v-if="detail"
          class="header-status"
          :class="`is-${detail.status}`">
          {{ statusText(detail.status) }}
        </span>
        <bk-button
          v-if="detail?.status === 'failed'"
          class="header-retry"
          data-testid="execution-header-retry"
          @click="openRetryDialog()">
          <span class="header-retry-inner">
            <audit-icon
              class="header-retry-icon"
              type="redo" />
            <span>{{ t('重试') }}</span>
          </span>
        </bk-button>
      </div>
    </template>
    <bk-exception
      v-if="loadError"
      class="execution-detail-state"
      scene="part"
      :title="t('执行详情加载失败')"
      type="500" />
    <div
      v-else-if="showSkeleton"
      class="execution-detail"
      data-testid="execution-detail-skeleton">
      <div class="detail-scroll">
        <section class="detail-section">
          <h4>{{ t('基本信息') }}</h4>
          <div class="desc-grid">
            <div
              v-for="(label, index) in skeletonBasicLabels"
              :key="label"
              class="desc-item">
              <span class="desc-label"><span>{{ label }}：</span></span>
              <span class="desc-value">
                <i
                  class="skeleton-bar"
                  :class="skeletonValueWidth(index)" />
              </span>
            </div>
          </div>
        </section>
        <section class="detail-section">
          <h4>{{ t('关联风险') }}</h4>
          <div class="desc-grid">
            <div
              v-for="(label, index) in skeletonRiskLabels"
              :key="label"
              class="desc-item">
              <span class="desc-label"><span>{{ label }}：</span></span>
              <span class="desc-value">
                <i
                  class="skeleton-bar"
                  :class="skeletonValueWidth(index + 1)" />
              </span>
            </div>
          </div>
        </section>
        <section class="detail-section">
          <h4>{{ t('套餐参数') }}</h4>
          <div class="desc-grid">
            <div
              v-for="(label, index) in skeletonParamLabels"
              :key="label"
              class="desc-item">
              <span class="desc-label"><span>{{ label }}：</span></span>
              <span class="desc-value">
                <i
                  class="skeleton-bar"
                  :class="skeletonValueWidth(index + 2)" />
              </span>
            </div>
          </div>
        </section>
        <section class="detail-section is-nodes">
          <h4>{{ t('执行节点') }}</h4>
          <table class="node-table">
            <colgroup>
              <col class="col-name">
              <col class="col-status">
              <col class="col-time">
              <col class="col-duration">
              <col class="col-error">
            </colgroup>
            <thead>
              <tr>
                <th>{{ t('节点名称') }}</th>
                <th>{{ t('状态') }}</th>
                <th>{{ t('开始时间') }}</th>
                <th>{{ t('耗时') }}</th>
                <th>{{ t('失败原因') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in skeletonNodeRows"
                :key="row">
                <td><i class="skeleton-bar is-v72" /></td>
                <td><i class="skeleton-bar is-v48" /></td>
                <td><i class="skeleton-bar is-v88" /></td>
                <td><i class="skeleton-bar is-v36" /></td>
                <td><i class="skeleton-bar is-fill" /></td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>
    </div>
    <div
      v-else
      class="execution-detail-body">
      <bk-loading :loading="loading">
        <div
          v-if="detail"
          class="execution-detail"
          data-testid="execution-detail-panel">
          <div
            v-if="rounds.length > 1"
            class="attempt-scroller"
            :class="{ 'is-scroll': rounds.length > 3 }"
            data-testid="execution-attempt-list">
            <div
              v-for="item in rounds"
              :key="item.id"
              class="attempt-card is-switchable"
              :class="{
                'is-active': item.id === activeAttemptId,
              }"
              data-testid="execution-attempt-card"
              @click="switchAttempt(item)">
              <div class="attempt-head">
                <div class="attempt-title">
                  <span
                    class="attempt-tag"
                    :class="`is-${item.status}`">
                    {{ statusText(item.status) }}
                  </span>
                  <strong>{{ item.label }}</strong>
                </div>
                <span
                  v-bk-tooltips="lineTip(
                    `${item.id}-duration`,
                    `${t('耗时')} ${liveDuration(item.status, item.started_at, item.duration)}`,
                  )"
                  class="attempt-duration"
                  @mouseenter="syncOverflow($event, `${item.id}-duration`)">
                  <span class="attempt-duration-text">
                    {{ t('耗时') }} {{ liveDuration(item.status, item.started_at, item.duration) }}
                  </span>
                </span>
              </div>
              <div class="attempt-body">
                <p
                  v-bk-tooltips="lineTip(`${item.id}-start`, `${t('开始时间')}：${item.started_at || '--'}`)"
                  @mouseenter="syncOverflow($event, `${item.id}-start`)">
                  {{ t('开始时间') }}：{{ item.started_at || '--' }}
                </p>
                <p
                  v-if="item.status === 'failed'"
                  v-bk-tooltips="errorTip(`${item.id}-reason`, `${t('失败原因')}：${item.error || '--'}`, 'bottom')"
                  class="attempt-reason"
                  @mouseenter="syncOverflow($event, `${item.id}-reason`)">
                  {{ t('失败原因') }}：{{ item.error || '--' }}
                </p>
                <p
                  v-else-if="item.status === 'success'"
                  v-bk-tooltips="lineTip(`${item.id}-end`, `${t('结束时间')}：${item.ended_at || '--'}`)"
                  @mouseenter="syncOverflow($event, `${item.id}-end`)">
                  {{ t('结束时间') }}：{{ item.ended_at || '--' }}
                </p>
              </div>
            </div>
          </div>

          <div class="detail-scroll">
            <section class="detail-section">
              <h4>{{ t('基本信息') }}</h4>
              <div class="desc-grid">
                <div
                  v-for="item in basicRows"
                  :key="item.label"
                  class="desc-item">
                  <span class="desc-label"><span>{{ item.label }}</span></span>
                  <span
                    class="desc-value"
                    :class="{ 'is-jump': item.jump }">
                    <span
                      v-if="item.jump"
                      v-bk-tooltips="lineTip(`basic-${item.label}`, item.value)"
                      class="desc-value-text"
                      @mouseenter="syncOverflow($event, `basic-${item.label}`)">
                      {{ item.value }}
                    </span>
                    <span
                      v-else
                      v-bk-tooltips="lineTip(`basic-${item.label}`, item.value)"
                      class="desc-clamp"
                      @mouseenter="syncOverflow($event, `basic-${item.label}`)">
                      {{ item.value }}
                    </span>
                    <button
                      v-if="item.jump && item.value !== '--'"
                      v-bk-tooltips="{ content: t('打开标准运维任务'), delay: 80 }"
                      class="jump-btn"
                      type="button"
                      @click="openSopsTask(detail?.sops_task_url)">
                      <audit-icon type="jump-link" />
                    </button>
                  </span>
                </div>
              </div>
            </section>

            <section class="detail-section">
              <h4>{{ t('关联风险') }}</h4>
              <div class="desc-grid">
                <div class="desc-item">
                  <span class="desc-label"><span>{{ t('风险ID') }}：</span></span>
                  <span class="desc-value">
                    <button
                      v-if="detail.risk_id"
                      class="text-link"
                      type="button"
                      @click="openLinkedField">
                      {{ detail.risk_id }}
                    </button>
                    <template v-else>--</template>
                  </span>
                </div>
                <div class="desc-item">
                  <span class="desc-label"><span>{{ t('风险标题') }}：</span></span>
                  <span class="desc-value">
                    <span
                      v-bk-tooltips="lineTip('risk-title', detail.risk_title || '--')"
                      class="desc-clamp"
                      @mouseenter="syncOverflow($event, 'risk-title')">
                      {{ detail.risk_title || '--' }}
                    </span>
                  </span>
                </div>
                <div class="desc-item">
                  <span class="desc-label"><span>{{ t('风险等级') }}：</span></span>
                  <span class="desc-value">
                    <span
                      v-if="riskLevelTag"
                      class="risk-level-tag"
                      :class="riskLevelTag.className">
                      {{ riskLevelTag.label }}
                    </span>
                    <template v-else>--</template>
                  </span>
                </div>
                <div class="desc-item">
                  <span class="desc-label"><span>{{ t('责任人') }}：</span></span>
                  <span class="desc-value">{{ detail.risk_owner || '--' }}</span>
                </div>
              </div>
            </section>

            <section class="detail-section">
              <h4>{{ t('套餐参数') }}</h4>
              <div class="desc-grid">
                <div
                  v-for="item in paramRows"
                  :key="item.label"
                  class="desc-item">
                  <span class="desc-label"><span>{{ item.label }}</span></span>
                  <span class="desc-value">
                    <span
                      v-bk-tooltips="lineTip(`param-${item.label}`, item.value)"
                      class="desc-clamp"
                      @mouseenter="syncOverflow($event, `param-${item.label}`)">
                      {{ item.value }}
                    </span>
                  </span>
                </div>
              </div>
            </section>

            <section class="detail-section is-nodes">
              <h4>{{ t('执行节点') }}</h4>
              <table class="node-table">
                <colgroup>
                  <col class="col-name">
                  <col class="col-status">
                  <col class="col-time">
                  <col class="col-duration">
                  <col class="col-error">
                </colgroup>
                <thead>
                  <tr>
                    <th>{{ t('节点名称') }}</th>
                    <th>{{ t('状态') }}</th>
                    <th>{{ t('开始时间') }}</th>
                    <th>{{ t('耗时') }}</th>
                    <th>{{ t('失败原因') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(item, index) in visibleNodes"
                    :key="`${item.name}-${index}`">
                    <td>
                      <span
                        v-bk-tooltips="lineTip(`node-name-${index}`, item.name)"
                        class="node-ellipsis"
                        @mouseenter="syncOverflow($event, `node-name-${index}`)">
                        {{ item.name || '--' }}
                      </span>
                    </td>
                    <td>
                      <span class="node-status">
                        <audit-icon
                          v-if="item.status === 'running'"
                          class="rotate-loading status-loading"
                          type="loading" />
                        <span
                          v-else
                          class="status-dot"
                          :class="`is-${item.status}`">
                          <i class="status-dot-outer" />
                          <i class="status-dot-inner" />
                        </span>
                        {{ statusText(item.status) }}
                      </span>
                    </td>
                    <td>{{ item.started_at || '--' }}</td>
                    <td>{{ liveDuration(item.status, item.started_at, item.duration) }}</td>
                    <td>
                      <span
                        v-bk-tooltips="errorTip(`node-error-${index}`, item.error)"
                        class="node-ellipsis"
                        @mouseenter="syncOverflow($event, `node-error-${index}`)">
                        {{ item.error || '--' }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </section>
          </div>
        </div>
      </bk-loading>
    </div>
  </audit-sideslider>
  <execution-retry-dialog
    v-model:is-show="showRetry"
    :detail="detail"
    :loading="retrying"
    @confirm="handleRetry" />
</template>
<script setup lang="ts">
  import { computed, reactive, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import ProcessApplicationManageService from '@service/process-application-manage';

  import type ExecutionDetailModel from '@model/application/execution-detail';
  import { resolveExecutionDuration } from '@model/application/execution-protocol';
  import type { ExecutionStatus, ExecutionTrigger } from '@model/application/execution-record';

  import useMessage from '@hooks/use-message';

  import { openRiskDetail, openSopsTask } from './execution-links';
  import { executionErrorTip } from './execution-tips';
  import ExecutionRetryDialog from './execution-retry-dialog.vue';
  import { useNow } from './use-now';

  interface Props {
    isShow: boolean;
    taskId: string;
    riskId?: string;
    sceneId?: string;
  }
  interface Emits {
    (e: 'update:isShow', value: boolean): void;
    (e: 'retried'): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const router = useRouter();
  const { messageSuccess } = useMessage();
  const loading = ref(false);
  const loadError = ref(false);
  const detail = ref<ExecutionDetailModel | null>(null);
  const showSkeleton = computed(() => loading.value && !detail.value);
  const skeletonNodeRows = [1, 2, 3];
  const skeletonValueWidth = (index: number) => ['is-v72', 'is-v48', 'is-v88', 'is-v36'][index % 4];
  const skeletonBasicLabels = computed(() => [
    t('任务名称'),
    t('任务ID'),
    t('处理套餐'),
    t('触发方式'),
    t('开始时间'),
    t('结束时间'),
    t('执行人'),
    t('耗时'),
  ]);
  const skeletonRiskLabels = computed(() => [
    t('风险ID'),
    t('风险标题'),
    t('风险等级'),
    t('责任人'),
  ]);
  const skeletonParamLabels = computed(() => [
    t('责任人'),
    t('原始事件ID'),
    t('标签名称'),
    t('风险类型'),
    t('风险数据源'),
    t('风险发现时间'),
    t('风险证据'),
    t('风险描述'),
  ]);
  const rounds = computed(() => (detail.value?.attempts || []).map((item, index) => ({
    ...item,
    label: t('第 {n} 次', { n: index + 1 }),
  })).reverse());
  const showRetry = ref(false);
  const retrying = ref(false);
  const retryTaskId = ref('');
  const activeAttemptId = ref('');

  const isShow = computed({
    get: () => props.isShow,
    set: (value: boolean) => emit('update:isShow', value),
  });

  const text = (value?: string) => value || '--';
  const statusText = (status: ExecutionStatus) => ({
    success: t('执行成功'),
    failed: t('执行失败'),
    running: t('执行中'),
  }[status] || status);

  const overflowed = reactive<Record<string, boolean>>({});
  const syncOverflow = (event: MouseEvent, key: string) => {
    const el = event.currentTarget as HTMLElement;
    const text = el.querySelector('.attempt-duration-text');
    const target = text instanceof HTMLElement ? text : el;
    overflowed[key] = target.scrollWidth > target.clientWidth + 1
      || target.scrollHeight > target.clientHeight + 1;
  };
  const lineTip = (key: string, content: string) => ({
    content,
    disabled: !overflowed[key],
    delay: 80,
    extCls: 'execution-attempt-tip',
  });
  const errorTip = (key: string, content: string, placement: 'top' | 'bottom' = 'top') => executionErrorTip(content, {
    placement,
    disabled: !content || !overflowed[key],
  });

  const activeAttempt = computed(() => (
    rounds.value.find(item => item.id === activeAttemptId.value) || null
  ));
  const visibleNodes = computed(() => (
    activeAttempt.value ? activeAttempt.value.nodes : (detail.value?.nodes || [])
  ));

  const durationActive = computed(() => props.isShow && (
    detail.value?.status === 'running'
    || rounds.value.some(item => item.status === 'running')
    || (detail.value?.nodes || []).some(item => item.status === 'running')
  ));
  const now = useNow(durationActive);
  const liveDuration = (status: string, startedAt: string, fallback: string) => (
    resolveExecutionDuration(status, startedAt, fallback, now.value)
  );

  const switchAttempt = (item: ExecutionDetailModel['attempts'][number]) => {
    activeAttemptId.value = item.id;
  };

  const riskLevelTag = computed(() => {
    const level = detail.value?.risk_level || '';
    const key = level.toUpperCase();
    if (key === 'HIGH' || level === '高') return { className: 'level-high', label: t('高') };
    if (key === 'MIDDLE' || key === 'MEDIUM' || level === '中') return { className: 'level-middle', label: t('中') };
    if (key === 'LOW' || level === '低') return { className: 'level-low', label: t('低') };
    return null;
  });

  const triggerText = (trigger: ExecutionTrigger) => {
    const text: Record<string, string> = {
      manual: t('手动'),
      auto: t('自动'),
      test: t('测试'),
      retry: t('重试'),
    };
    return text[trigger] || '--';
  };

  const basicRows = computed(() => {
    const current = detail.value;
    const packageName = current?.application_name
      ? `${current.application_name}（ ${current.application_id} ）`
      : '';
    return [
      { label: `${t('任务名称')}：`, value: text(current?.task_name), jump: true },
      { label: `${t('任务ID')}：`, value: text(current?.task_id) },
      { label: `${t('处理套餐')}：`, value: text(packageName) },
      { label: `${t('触发方式')}：`, value: current ? triggerText(current.trigger_type) : '--' },
      { label: `${t('开始时间')}：`, value: text(activeAttempt.value?.started_at || current?.started_at) },
      { label: `${t('结束时间')}：`, value: text(activeAttempt.value?.ended_at || current?.ended_at) },
      { label: `${t('执行人')}：`, value: text(current?.executor) },
      { label: `${t('耗时')}：`, value: liveDuration(
        activeAttempt.value?.status || current?.status || '',
        activeAttempt.value?.started_at || current?.started_at || '',
        activeAttempt.value?.duration || current?.duration || '',
      ) },
    ];
  });

  const paramRows = computed(() => {
    const current = detail.value;
    return [
      { label: `${t('责任人')}：`, value: text(current?.risk_owner) },
      { label: `${t('原始事件ID')}：`, value: text(current?.raw_event_id) },
      { label: `${t('标签名称')}：`, value: text(current?.strategy_name) },
      { label: `${t('风险类型')}：`, value: text(current?.risk_type) },
      { label: `${t('风险数据源')}：`, value: text(current?.risk_source) },
      { label: `${t('风险发现时间')}：`, value: text(current?.risk_found_at) },
      { label: `${t('风险证据')}：`, value: text(current?.risk_evidence) },
      { label: `${t('风险描述')}：`, value: text(current?.risk_description) },
    ];
  });

  const openLinkedField = () => {
    openRiskDetail(router, detail.value?.risk_id || props.riskId || '', props.sceneId);
  };

  const loadDetail = async (taskId = props.taskId) => {
    if (!taskId) return;
    loading.value = true;
    loadError.value = false;
    try {
      detail.value = await ProcessApplicationManageService.fetchExecutionDetail({ task_id: taskId });
      if (detail.value && !detail.value.risk_id && props.riskId) {
        detail.value.risk_id = props.riskId;
      }
      const history = detail.value?.attempts || [];
      activeAttemptId.value = history[history.length - 1]?.id || '';
    } catch {
      loadError.value = true;
      detail.value = null;
      activeAttemptId.value = '';
    } finally {
      loading.value = false;
    }
  };

  const openRetryDialog = () => {
    retryTaskId.value = detail.value?.task_id || props.taskId;
    showRetry.value = true;
  };

  watch(() => [props.isShow, props.taskId] as const, ([visible, taskId], prev) => {
    if (!visible || !taskId) return;
    const justOpened = !prev?.[0];
    const taskChanged = prev?.[1] !== taskId;
    if (justOpened || taskChanged) {
      detail.value = null;
      loadError.value = false;
      activeAttemptId.value = '';
    }
    loadDetail(taskId);
  });

  const handleRetry = async () => {
    retrying.value = true;
    try {
      const taskId = retryTaskId.value || detail.value?.task_id || props.taskId;
      await ProcessApplicationManageService.retryExecution({
        task_id: taskId,
        risk_id: detail.value?.risk_id || props.riskId || '',
      });
      messageSuccess(t('已发起重试'));
      await loadDetail(taskId);
      showRetry.value = false;
      emit('retried');
    } finally {
      retrying.value = false;
    }
  };
</script>
<style lang="postcss" scoped>
.execution-detail-header {
  display: flex;
  align-items: center;
  gap: var(--audit-space-8);
  width: 100%;
  min-width: 0;
  padding-right: 18px;
}

.header-title {
  font-size: var(--audit-font-size-lg);
  font-weight: var(--audit-font-weight-regular);
  line-height: var(--audit-line-height-lg);
  color: var(--audit-neutral-text-01);
}

.header-retry {
  width: 82px;
  min-width: 82px;
  height: 32px;
  padding: 0 16px;
  margin-left: auto;
  font-size: var(--audit-font-size-base);
  line-height: 22px;
  flex: none;
}

.header-retry-inner {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.header-retry-icon {
  font-size: 16px;
  line-height: 1;
}

.header-status {
  display: inline-flex;
  height: 22px;
  padding: 0 var(--audit-space-8);
  font-size: var(--audit-font-size-sm);
  font-weight: var(--audit-font-weight-regular);
  line-height: var(--audit-line-height-sm);
  border-radius: var(--audit-radius-control);
  flex: none;
  align-items: center;
}

.header-status.is-failed {
  color: var(--audit-danger-01);
  background: var(--audit-danger-06);
}

.header-status.is-success {
  color: var(--audit-success-01);
  background: var(--audit-success-06);
}

.header-status.is-running {
  color: var(--audit-brand-01);
  background: var(--audit-brand-06);
}

.header-split {
  width: 1px;
  height: 12px;
  background: var(--audit-neutral-border-01);
}

.header-sub {
  min-width: 0;
  overflow: hidden;
  font-size: var(--audit-font-size-base);
  line-height: var(--audit-line-height-base);
  color: var(--audit-neutral-text-03);
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 0 1 auto;
}

.execution-detail-state {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 0;
}

.execution-detail-state :deep(.bk-exception-description) {
  width: 80%;
  max-width: 80%;
  line-height: 20px;
  word-break: break-all;
  white-space: pre-wrap;
}

.execution-detail-body {
  display: flex;
  flex: 1;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.execution-detail-body :deep(.bk-loading-wrapper) {
  display: flex;
  flex: 1;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.execution-detail {
  display: flex;
  flex: 1;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  padding-top: var(--audit-space-24);
  overflow: hidden;
}

.detail-scroll {
  flex: 1;
  min-height: 0;
  padding: 0 var(--audit-space-40) var(--audit-space-24);
  overflow: auto;
}

.attempt-scroller {
  display: flex;
  flex: none;
  margin: 0 var(--audit-space-40) var(--audit-space-24);
  overflow-x: auto;
  gap: var(--audit-space-16);
}

.attempt-card {
  box-sizing: border-box;
  min-width: 0;
  min-height: 94px;
  padding: 10px 14px;
  overflow: hidden;
  text-align: left;
  background: var(--audit-neutral-bg-01);
  border: 2px solid transparent;
  border-radius: 4px;
  flex: 1 1 0;
}

.attempt-scroller.is-scroll .attempt-card {
  width: 240px;
  min-width: 240px;
  flex: 0 0 240px;
}

.attempt-card.is-active {
  background: var(--audit-brand-07);
  border-color: var(--audit-brand-02);
}

.attempt-card.is-switchable {
  cursor: pointer;
}

.skeleton-bar {
  display: block;
  flex: none;
  height: 12px;
  margin: 4px 0;
  background: #e4e7ee;
  border-radius: var(--audit-radius-control);
  animation: execution-skeleton-shimmer 1.2s ease-in-out infinite;
}

.skeleton-bar.is-v36 { width: 72px; }
.skeleton-bar.is-v48 { width: 96px; }
.skeleton-bar.is-v72 { width: 144px; }
.skeleton-bar.is-v88 { width: 180px; }
.skeleton-bar.is-fill { width: 100%; }

@keyframes execution-skeleton-shimmer {
  0%,
  100% {
    background: #e4e7ee;
  }

  50% {
    background: #f2f3f7;
  }
}

.attempt-head,
.attempt-title,
.attempt-extra {
  display: flex;
  align-items: center;
}

.attempt-head {
  justify-content: space-between;
  gap: var(--audit-space-8);
}

.attempt-title {
  gap: var(--audit-space-8);
  overflow: hidden;
  font-size: var(--audit-font-size-base);
  font-weight: 700;
  line-height: 22px;
  color: var(--audit-neutral-text-01);
  flex: none;
  white-space: nowrap;
}

.attempt-title strong {
  white-space: nowrap;
}

.attempt-tag {
  display: inline-flex;
  height: 22px;
  padding: 0 var(--audit-space-8);
  font-size: var(--audit-font-size-sm);
  font-weight: var(--audit-font-weight-regular);
  line-height: var(--audit-line-height-sm);
  color: var(--audit-neutral-bg-04);
  white-space: nowrap;
  border-radius: var(--audit-radius-control);
  flex: none;
  align-items: center;
}

.attempt-tag.is-failed {
  background: var(--audit-danger-02);
}

.attempt-tag.is-success {
  background: var(--audit-success-02);
}

.attempt-tag.is-running {
  background: var(--audit-warn-02);
}

.attempt-extra {
  gap: var(--audit-space-8);
  flex: none;
}

.attempt-duration {
  min-width: 0;
  overflow: hidden;
  font-size: var(--audit-font-size-sm);
  line-height: 20px;
  color: var(--audit-neutral-text-03);
  text-align: right;
  white-space: nowrap;
  flex: 1 1 auto;
}

.attempt-duration-text {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: top;
}

.attempt-card p {
  width: 0;
  min-width: 100%;
  margin: 4px 0 0;
  overflow: hidden;
  font-size: var(--audit-font-size-sm);
  line-height: 20px;
  color: var(--audit-neutral-text-02);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-section {
  padding-bottom: var(--audit-space-24);
  margin-bottom: var(--audit-space-24);
  border-bottom: 1px solid var(--audit-neutral-border-02);
}

.detail-section:last-child {
  padding-bottom: 0;
  margin-bottom: 0;
  border-bottom: 0;
}

.detail-section h4 {
  margin: 0 0 var(--audit-space-8);
  font-size: var(--audit-font-size-base);
  font-weight: var(--audit-font-weight-bold);
  line-height: var(--audit-line-height-base);
  color: var(--audit-neutral-text-01);
}

.detail-section.is-nodes h4 {
  margin-bottom: var(--audit-space-12);
}

.desc-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  column-gap: 48px;
}

.desc-item {
  display: flex;
  min-width: 0;
  min-height: 32px;
  padding: 6px 0;
  font-size: var(--audit-font-size-sm);
  line-height: var(--audit-line-height-sm);
  align-items: flex-start;
  gap: var(--audit-space-8);
}

.desc-label {
  height: var(--audit-line-height-sm);
  color: var(--audit-neutral-text-02);
  text-align: right;
  flex: 0 0 84px;
}

.desc-label span {
  white-space: nowrap;
}

.desc-value {
  display: flex;
  min-width: 0;
  color: var(--audit-neutral-text-01);
  align-items: flex-start;
  gap: var(--audit-space-8);
  flex: 1;
  word-break: break-all;
  overflow-wrap: anywhere;
}

.desc-value-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.desc-clamp {
  display: -webkit-box;
  min-width: 0;
  overflow: hidden;
  flex: 1;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  word-break: break-all;
  overflow-wrap: anywhere;
}

.text-link {
  padding: 0;
  color: var(--audit-brand-02);
  cursor: pointer;
  background: transparent;
  border: 0;
}

.jump-btn {
  display: inline-flex;
  flex: none;
  padding: 0;
  font-size: 16px;
  color: var(--audit-brand-02);
  cursor: pointer;
  background: transparent;
  border: 0;
}

.risk-level-tag {
  box-sizing: border-box;
  display: inline-flex;
  width: 48px;
  height: 26px;
  font-size: var(--audit-font-size-sm);
  line-height: 24px;
  color: var(--audit-neutral-bg-04);
  border: 1px solid transparent;
  border-radius: var(--audit-radius-control);
  align-items: center;
  justify-content: center;
}

.risk-level-tag.level-high {
  background: var(--audit-danger-02);
  border-color: var(--audit-danger-02);
}

.risk-level-tag.level-middle {
  background: var(--audit-warn-02);
  border-color: var(--audit-warn-02);
}

.risk-level-tag.level-low {
  background: var(--audit-neutral-text-03);
  border-color: var(--audit-neutral-text-03);
}

.node-table {
  width: 100%;
  font-size: var(--audit-font-size-sm);
  table-layout: fixed;
  border-collapse: collapse;
}

.node-table .col-name {
  width: 148px;
}

.node-table .col-status {
  width: 108px;
}

.node-table .col-time {
  width: 208px;
}

.node-table .col-duration {
  width: 84px;
}

.node-table th,
.node-table td {
  height: 42px;
  padding: 0 16px;
  overflow: hidden;
  text-align: left;
  white-space: nowrap;
  border-bottom: 1px solid var(--audit-neutral-border-02);
}

.node-ellipsis {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-table th {
  color: var(--audit-neutral-text-02);
  background: var(--audit-neutral-bg-02);
  font-weight: var(--audit-font-weight-regular);
}

.node-status {
  display: inline-flex;
  font-size: var(--audit-font-size-sm);
  line-height: 20px;
  color: var(--audit-neutral-text-02);
  align-items: center;
  gap: 4px;
}

.status-dot {
  position: relative;
  display: inline-flex;
  width: 12px;
  height: 12px;
  flex: none;
  align-items: center;
  justify-content: center;
}

.status-dot-outer,
.status-dot-inner {
  border-radius: 50%;
}

.status-dot-outer {
  width: 12px;
  height: 12px;
  opacity: 0.2;
}

.status-dot-inner {
  position: absolute;
  width: 6px;
  height: 6px;
}

.status-dot.is-failed .status-dot-outer {
  background: rgba(234, 54, 54, 0.6);
}

.status-dot.is-failed .status-dot-inner {
  background: var(--audit-danger-02);
}

.status-dot.is-success .status-dot-outer {
  background: rgba(44, 175, 94, 0.6);
}

.status-dot.is-success .status-dot-inner {
  background: var(--audit-success-02);
}

.status-loading {
  font-size: 16px;
}
</style>
<style lang="postcss">
.execution-detail-sideslider.bk-modal .bk-modal-content {
  display: flex;
  height: calc(100vh - 52px) !important;
  min-height: 0;
  overflow: hidden !important;
  flex-direction: column;
}

.execution-detail-sideslider.bk-modal .bk-modal-content > div {
  display: flex;
  flex: 1;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.execution-detail-sideslider .bk-sideslider-content,
.execution-detail-sideslider .audit-sideslider-content {
  display: flex;
  flex: 1;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.execution-attempt-tip {
  max-width: 320px;
  line-height: 20px;
  word-break: break-all;
  white-space: normal;
}

.execution-error-tip-body {
  max-height: 240px;
  margin-right: -10px;
  padding-right: 8px;
  overflow-x: hidden;
  overflow-y: auto;
  word-break: break-all;
  white-space: normal;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.45) transparent;
}

.execution-error-tip-body::-webkit-scrollbar {
  width: 6px;
}

.execution-error-tip-body::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.45);
  border-radius: 3px;
}

.execution-error-tip-body::-webkit-scrollbar-track {
  background: transparent;
}
</style>
