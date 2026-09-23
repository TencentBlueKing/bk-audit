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
    :show-footer="false"
    show-header-slot
    :title="t('执行详情')"
    :width="960">
    <template #header>
      <div class="execution-detail-header">
        <span>{{ t('执行详情') }}</span>
        <span class="header-split" />
        <span class="header-sub">{{ detail?.task_id || props.taskId }}</span>
      </div>
    </template>
    <bk-loading :loading="loading">
      <bk-exception
        v-if="loadError"
        scene="part"
        type="500">
        {{ t('执行详情加载失败') }}
      </bk-exception>
      <div
        v-else-if="detail"
        class="execution-detail"
        data-testid="execution-detail-panel">
        <div
          v-if="detail.attempts.length > 1"
          class="attempt-scroller"
          data-testid="execution-attempt-list">
          <div
            v-for="item in detail.attempts"
            :key="item.id"
            class="attempt-card"
            :class="{
              'is-active': item.id === activeAttemptId,
              'is-switchable': item.status === 'failed',
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
              <div class="attempt-extra">
                <span class="attempt-duration">{{ t('耗时') }} {{ item.duration }}</span>
                <bk-button
                  v-if="item.status === 'failed'"
                  class="attempt-retry"
                  data-testid="execution-attempt-retry"
                  text
                  theme="primary"
                  @click.stop="showRetry = true">
                  {{ t('重试') }}
                </bk-button>
              </div>
            </div>
            <div class="attempt-body">
              <p
                v-bk-tooltips="lineTip(`${item.id}-start`, `${t('开始时间')}：${item.started_at || '--'}`)"
                @mouseenter="syncOverflow($event, `${item.id}-start`)">
                {{ t('开始时间') }}：{{ item.started_at || '--' }}
              </p>
              <p
                v-if="item.status === 'failed'"
                v-bk-tooltips="lineTip(`${item.id}-reason`, `${t('失败原因')}：${item.error || '--'}`)"
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

        <section class="detail-section">
          <h4>{{ t('基本信息') }}</h4>
          <div class="desc-grid">
            <div
              v-for="item in basicRows"
              :key="item.label"
              class="desc-item">
              <span class="desc-label"><span>{{ item.label }}</span></span>
              <span class="desc-value">
                {{ item.value }}
                <button
                  v-if="item.copy && item.value !== '--'"
                  class="copy-btn"
                  type="button"
                  @click="copyText(item.value)">
                  <audit-icon type="copy" />
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
                {{ detail.risk_id || '--' }}
                <button
                  v-if="detail.risk_id"
                  class="copy-btn"
                  type="button"
                  @click="copyText(detail.risk_id)">
                  <audit-icon type="copy" />
                </button>
              </span>
            </div>
            <div class="desc-item">
              <span class="desc-label"><span>{{ t('风险标题') }}：</span></span>
              <span class="desc-value">{{ detail.risk_title || '--' }}</span>
            </div>
            <div class="desc-item">
              <span class="desc-label"><span>{{ t('风险等级') }}：</span></span>
              <span class="desc-value">
                <span
                  v-if="detail.risk_level"
                  class="level-tag"
                  :class="`is-${detail.risk_level}`">
                  {{ detail.risk_level }}
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
              <span class="desc-value">{{ item.value }}</span>
            </div>
          </div>
        </section>

        <section class="detail-section">
          <h4>{{ t('执行节点') }}</h4>
          <table class="node-table">
            <thead>
              <tr>
                <th>{{ t('节点名称') }}</th>
                <th>{{ t('状态') }}</th>
                <th>{{ t('开始时间') }}</th>
                <th>{{ t('耗时') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in detail.nodes"
                :key="item.name">
                <td>{{ item.name }}</td>
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
                <td>{{ item.duration || '--' }}</td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>
    </bk-loading>
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

  import ProcessApplicationManageService from '@service/process-application-manage';

  import type ExecutionDetailModel from '@model/application/execution-detail';
  import type { ExecutionStatus, ExecutionTrigger } from '@model/application/execution-record';

  import useMessage from '@hooks/use-message';

  import ExecutionRetryDialog from './execution-retry-dialog.vue';

  interface Props {
    isShow: boolean;
    taskId: string;
  }
  interface Emits {
    (e: 'update:isShow', value: boolean): void;
    (e: 'retried'): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const loading = ref(false);
  const loadError = ref(false);
  const detail = ref<ExecutionDetailModel | null>(null);
  const showRetry = ref(false);
  const retrying = ref(false);
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
    overflowed[key] = el.scrollWidth > el.clientWidth;
  };
  const lineTip = (key: string, content: string) => ({
    content,
    disabled: !overflowed[key],
    delay: 80,
    extCls: 'execution-attempt-tip',
  });

  const activeAttempt = computed(() => (
    detail.value?.attempts.find(item => item.id === activeAttemptId.value) || null
  ));

  const switchAttempt = (item: ExecutionDetailModel['attempts'][number]) => {
    if (item.status !== 'failed') return;
    activeAttemptId.value = item.id;
  };

  const triggerText = (trigger: ExecutionTrigger) => ({
    manual: t('手动'),
    auto: t('自动'),
    retry: t('重试'),
  }[trigger] || trigger);

  const basicRows = computed(() => {
    const current = detail.value;
    const packageName = current?.application_name
      ? `${current.application_name}(${current.application_id})`
      : '';
    return [
      { label: `${t('任务ID')}：`, value: text(current?.task_id), copy: true },
      { label: `${t('任务名称')}：`, value: text(current?.task_name) },
      { label: `${t('处理套餐')}：`, value: text(packageName) },
      { label: `${t('触发方式')}：`, value: current ? triggerText(current.trigger_type) : '--' },
      { label: `${t('执行人')}：`, value: text(current?.executor) },
      { label: `${t('耗时')}：`, value: text(activeAttempt.value?.duration || current?.duration) },
      { label: `${t('开始时间')}：`, value: text(activeAttempt.value?.started_at || current?.started_at) },
      { label: `${t('结束时间')}：`, value: text(activeAttempt.value?.ended_at || current?.ended_at) },
    ];
  });

  const paramRows = computed(() => {
    const current = detail.value;
    return [
      { label: `${t('策略ID')}：`, value: text(current?.strategy_id) },
      { label: `${t('风险类型')}：`, value: text(current?.risk_type) },
      { label: `${t('风险证据')}：`, value: text(current?.risk_evidence) },
      { label: `${t('风险数据源')}：`, value: text(current?.risk_source) },
      { label: `${t('风险描述')}：`, value: text(current?.risk_description) },
      { label: `${t('风险发现时间')}：`, value: text(current?.risk_found_at) },
      { label: `${t('责任人')}：`, value: text(current?.risk_owner) },
      { label: `${t('原始事件ID')}：`, value: text(current?.raw_event_id) },
    ];
  });

  const copyText = async (value: string) => {
    await navigator.clipboard.writeText(value);
    messageSuccess(t('已复制'));
  };

  const loadDetail = async () => {
    if (!props.taskId) return;
    loading.value = true;
    loadError.value = false;
    try {
      detail.value = await ProcessApplicationManageService.fetchExecutionDetail({ task_id: props.taskId });
      const attempts = detail.value?.attempts || [];
      activeAttemptId.value = attempts[attempts.length - 1]?.id || '';
    } catch {
      loadError.value = true;
      detail.value = null;
    } finally {
      loading.value = false;
    }
  };

  watch(() => [props.isShow, props.taskId], ([visible]) => {
    if (visible) loadDetail();
  });

  const handleRetry = async () => {
    retrying.value = true;
    try {
      detail.value = await ProcessApplicationManageService.retryExecution({
        task_id: props.taskId,
        reason: '',
      });
      const attempts = detail.value?.attempts || [];
      activeAttemptId.value = attempts[attempts.length - 1]?.id || '';
      messageSuccess(t('已发起重试'));
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
}

.header-split {
  width: 1px;
  height: 12px;
  background: var(--audit-neutral-border-01);
}

.header-sub {
  font-size: var(--audit-font-size-base);
  line-height: 22px;
  color: var(--audit-neutral-text-03);
}

.execution-detail {
  display: flex;
  padding: 24px 40px;
  flex-direction: column;
  gap: 24px;
}

.attempt-scroller {
  display: flex;
  overflow-x: auto;
  gap: 16px;
}

.attempt-card {
  box-sizing: border-box;
  width: max-content;
  min-width: 240px;
  max-width: 360px;
  padding: 12px 16px;
  text-align: left;
  background: var(--audit-neutral-bg-01);
  border: 2px solid transparent;
  border-radius: 4px;
  flex: 0 0 auto;
}

.attempt-card.is-active {
  background: var(--audit-brand-07);
  border-color: var(--audit-brand-02);
}

.attempt-card.is-switchable {
  cursor: pointer;
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
  padding: 0 8px;
  font-size: var(--audit-font-size-sm);
  font-weight: 400;
  line-height: 22px;
  color: var(--audit-neutral-bg-04);
  white-space: nowrap;
  border-radius: 2px;
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
  font-size: var(--audit-font-size-sm);
  line-height: 20px;
  color: var(--audit-neutral-text-03);
  white-space: nowrap;
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

.detail-section h4 {
  margin: 0 0 var(--audit-space-8);
  font-size: var(--audit-font-size-base);
  font-weight: 700;
  line-height: 22px;
  color: var(--audit-neutral-text-01);
}

.desc-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
}

.desc-item {
  display: flex;
  min-height: 32px;
  padding: 6px 0;
  font-size: var(--audit-font-size-sm);
  line-height: 20px;
  align-items: center;
  gap: var(--audit-space-8);
}

.desc-label {
  position: relative;
  height: 20px;
  color: var(--audit-neutral-text-02);
  flex: 0 0 84px;
}

.desc-label span {
  position: absolute;
  right: 0;
  white-space: nowrap;
}

.desc-value {
  display: flex;
  color: var(--audit-neutral-text-01);
  align-items: center;
  gap: var(--audit-space-8);
}

.copy-btn {
  display: inline-flex;
  padding: 0;
  font-size: 16px;
  color: var(--audit-brand-02);
  cursor: pointer;
  background: transparent;
  border: 0;
}

.level-tag {
  height: 22px;
  padding: 0 8px;
  font-size: var(--audit-font-size-sm);
  line-height: 22px;
  color: var(--audit-neutral-bg-04);
  border-radius: 2px;
}

.level-tag.is-高 {
  background: var(--audit-danger-02);
}

.level-tag.is-中 {
  background: var(--audit-warn-02);
}

.level-tag.is-低 {
  background: var(--audit-success-02);
}

.node-table {
  width: 100%;
  font-size: var(--audit-font-size-sm);
  border-collapse: collapse;
}

.node-table th,
.node-table td {
  height: 42px;
  padding: 0 16px;
  text-align: left;
  border-bottom: 1px solid var(--audit-neutral-border-02);
}

.node-table th {
  color: var(--audit-neutral-text-02);
  background: var(--audit-neutral-bg-03);
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
.execution-attempt-tip {
  max-width: 320px;
  line-height: 20px;
  word-break: break-all;
  white-space: normal;
}
</style>
