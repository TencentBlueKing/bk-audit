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
  <bk-dialog
    class="execution-retry-dialog"
    ext-cls="execution-retry-dialog"
    :is-show="isShow"
    :quick-close="false"
    :width="640"
    @update:is-show="emit('update:isShow', $event)">
    <template #header>
      <div class="retry-header">
        <span class="retry-title">{{ t('重试执行') }}</span>
        <span class="retry-split" />
        <span class="retry-task">{{ detail?.task_id || '--' }}</span>
      </div>
    </template>
    <div
      class="retry-body"
      data-testid="execution-retry-dialog">
      <div
        v-for="item in rows"
        :key="item.label"
        class="retry-row">
        <span class="retry-label"><span>{{ item.label }}</span></span>
        <span class="retry-value">{{ item.value }}</span>
      </div>
    </div>
    <template #footer>
      <bk-button
        data-testid="execution-retry-confirm"
        :loading="loading"
        theme="primary"
        @click="emit('confirm')">
        {{ t('确认重试') }}
      </bk-button>
      <bk-button
        class="retry-cancel"
        @click="emit('update:isShow', false)">
        {{ t('取消') }}
      </bk-button>
    </template>
  </bk-dialog>
</template>
<script setup lang="ts">
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type ExecutionDetail from '@model/application/execution-detail';

  interface Props {
    isShow: boolean;
    detail: ExecutionDetail | null;
    loading?: boolean;
  }
  interface Emits {
    (e: 'update:isShow', value: boolean): void;
    (e: 'confirm'): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const { t } = useI18n();

  const text = (value?: string) => value || '--';
  const rows = computed(() => {
    const detail = props.detail;
    const packageName = detail?.application_name
      ? `${detail.application_name}(${detail.application_id})`
      : '';
    return [
      { label: `${t('套餐名称')}：`, value: text(packageName) },
      { label: `${t('风险ID')}：`, value: text(detail?.risk_id) },
      { label: `${t('风险描述')}：`, value: text(detail?.risk_description) },
      { label: `${t('风险证据')}：`, value: text(detail?.risk_evidence) },
      { label: `${t('风险类型')}：`, value: text(detail?.risk_type) },
      { label: `${t('风险发现时间')}：`, value: text(detail?.risk_found_at) },
      { label: `${t('风险数据源')}：`, value: text(detail?.risk_source) },
      { label: `${t('责任人')}：`, value: text(detail?.risk_owner) },
      { label: `${t('策略ID')}：`, value: text(detail?.strategy_id) },
      { label: `${t('原始事件ID')}：`, value: text(detail?.raw_event_id) },
    ];
  });

</script>
<style lang="postcss" scoped>
.retry-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.retry-title {
  font-size: 20px;
  font-weight: 400;
  line-height: 28px;
  color: var(--audit-neutral-text-01);
  white-space: nowrap;
}

.retry-split {
  width: 1px;
  height: 12px;
  background: var(--audit-neutral-border-01);
  flex: none;
}

.retry-task {
  font-size: var(--audit-font-size-base);
  font-weight: 400;
  line-height: 22px;
  color: var(--audit-neutral-text-03);
  white-space: nowrap;
}

.retry-row {
  display: flex;
  height: 32px;
  font-size: var(--audit-font-size-sm);
  line-height: 20px;
  align-items: center;
  gap: var(--audit-space-8);
}

.retry-label {
  position: relative;
  height: 20px;
  color: var(--audit-neutral-text-02);
  flex: 0 0 84px;
}

.retry-label span {
  position: absolute;
  right: 0;
  white-space: nowrap;
}

.retry-value {
  color: var(--audit-neutral-text-01);
  flex: 1;
  word-break: break-all;
}
</style>
<style lang="postcss">
.execution-retry-dialog .bk-dialog-content {
  margin-top: 20px;
  padding: 0 32px;
}

.execution-retry-dialog .bk-dialog-footer {
  height: 48px;
  background: var(--audit-neutral-bg-02);
  border-top: 1px solid var(--audit-neutral-border-02);
}

.execution-retry-dialog .bk-dialog-footer .bk-button + .bk-button,
.execution-retry-dialog .retry-cancel {
  margin-left: 8px;
}
</style>
