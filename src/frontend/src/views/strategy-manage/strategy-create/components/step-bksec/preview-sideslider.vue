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
    :title="t('BKSEC安全工单预览')"
    :width="640">
    <div
      class="bksec-preview"
      data-testid="bksec-preview-panel">
      <div class="bksec-preview-toolbar">
        <div class="bksec-risk-field">
          <span class="bksec-risk-prefix">{{ t('风险单') }}</span>
          <bk-select
            v-model="selectedId"
            class="bksec-preview-select"
            filterable
            :loading="listLoading"
            :no-data-text="t('暂无数据')"
            :no-match-text="t('暂无匹配的风险单')"
            :placeholder="t('请选择一条风险单用于渲染预览')"
            @change="loadPreview">
            <template #trigger>
              <div class="bksec-risk-trigger">
                <span
                  class="bksec-risk-text"
                  :class="{ 'is-placeholder': !selectedRisk }">
                  {{ selectedRisk ? optionName(selectedRisk) : t('请选择一条风险单用于渲染预览') }}
                </span>
                <span
                  v-if="selectedRisk && showDebugTag(selectedRisk)"
                  class="bksec-debug-tag">
                  {{ t('调试') }}
                </span>
                <audit-icon
                  class="bksec-risk-arrow"
                  type="angle-line-down" />
              </div>
            </template>
            <bk-option
              v-for="item in displayRisks"
              :id="item.id"
              :key="item.id"
              :name="optionName(item)">
              <div class="bksec-risk-option">
                <span>{{ optionName(item) }}</span>
                <span
                  v-if="showDebugTag(item)"
                  class="bksec-debug-tag">
                  {{ t('调试') }}
                </span>
              </div>
            </bk-option>
          </bk-select>
        </div>
        <span
          v-bk-tooltips="{
            content: t('请先选择一条风险单'),
            disabled: !!selectedId,
          }">
          <bk-pop-confirm
            :cancel-text="t('取消')"
            :confirm-config="{
              loading: sending,
              disabled: !handlerName,
            }"
            :confirm-text="t('发送')"
            ext-cls="bksec-test-pop"
            placement="bottom-end"
            :popover-options="{ disableOutsideClick: true }"
            trigger="click"
            :width="360"
            @confirm="handleSend">
            <bk-button
              data-testid="bksec-send-test"
              :disabled="!selectedId"
              theme="primary">
              {{ t('发送测试工单') }}
            </bk-button>
            <template #content>
              <div class="bksec-test-form">
                <div class="bksec-test-label">
                  <span>{{ t('选择测试工单处理人') }}</span>
                  <span class="bksec-test-required">*</span>
                </div>
                <audit-user-selector-tenant
                  v-model="testForm.handler"
                  :multiple="false"
                  :placeholder="t('请输入用户名')" />
              </div>
            </template>
          </bk-pop-confirm>
        </span>
      </div>
      <bk-loading :loading="previewLoading">
        <bk-exception
          v-if="previewError"
          data-testid="bksec-preview-error"
          scene="part"
          type="500">
          {{ t('工单预览加载失败') }}
        </bk-exception>
        <div
          v-else
          class="bksec-preview-body">
          <div
            v-for="(row, index) in previewRows"
            :key="row.key"
            class="bksec-desc-row"
            :class="{ 'is-spaced': isExtensionStart(index) }">
            <span class="bksec-desc-label">
              <span class="bksec-desc-label-text">{{ row.label }}：</span>
            </span>
            <span class="bksec-desc-value">
              <span
                v-if="row.kind === 'level' && row.value && row.value !== '--'"
                class="bksec-level"
                :class="levelClass(row.value)">
                {{ row.value }}
              </span>
              <span
                v-else-if="row.kind === 'status'"
                class="bksec-status">
                <i class="bksec-status-mark" />
                {{ row.value }}
              </span>
              <span
                v-else
                :class="{ 'is-multiline': row.kind === 'multiline' }">{{ row.value || '--' }}</span>
            </span>
          </div>
        </div>
      </bk-loading>
    </div>
  </audit-sideslider>
</template>
<script setup lang="ts">
  import dayjs from 'dayjs';
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import BksecManageService from '@service/bksec-manage';

  import type BksecPreviewRisk from '@model/bksec/preview-risk';
  import type { BksecTicketPreviewRow } from '@model/bksec/ticket-preview';

  import useMessage from '@hooks/use-message';

  import { isStrategyEditRoute } from '../../../utils/strategy-routes';

  interface Props {
    isShow: boolean;
    riskTypeId: number | null;
    fieldValues: Record<string, string>;
    strategyId?: string | number;
    strategyType?: string;
    strategyName?: string;
  }
  interface Emits {
    (e: 'update:isShow', value: boolean): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const route = useRoute();
  const { t } = useI18n();
  const { messageSuccess, messageError } = useMessage();

  const isShow = computed({
    get: () => props.isShow,
    set: (value: boolean) => emit('update:isShow', value),
  });

  const riskList = ref<BksecPreviewRisk[]>([]);
  const selectedId = ref('');
  const listLoading = ref(false);
  const previewLoading = ref(false);
  const previewError = ref(false);
  const previewRows = ref<BksecTicketPreviewRow[]>([]);
  const openedAt = ref('');
  const sending = ref(false);
  const testForm = ref({ handler: '' });

  const isCreateMode = computed(() => !isStrategyEditRoute(route.name));
  const isDebugRisk = (item: BksecPreviewRisk) => item.source === 'debug' || !item.risk_id;
  const displayRisks = computed(() => {
    if (!isCreateMode.value) return riskList.value;
    const debugs = riskList.value.filter(isDebugRisk);
    return debugs.length ? debugs : riskList.value;
  });
  const selectedRisk = computed(() => displayRisks.value.find(item => item.id === selectedId.value) || null);
  const handlerName = computed(() => String(testForm.value.handler || '').trim());

  const optionName = (item: BksecPreviewRisk) => {
    if (isCreateMode.value) return item.title;
    return item.risk_id ? `${item.risk_id} ${item.title}` : item.title;
  };
  const showDebugTag = (item: BksecPreviewRisk) => isCreateMode.value && isDebugRisk(item);

  const levelClass = (value: string) => {
    if (value === '高') return 'is-high';
    if (value === '低') return 'is-low';
    return 'is-medium';
  };
  const isExtensionStart = (index: number) => previewRows.value[index - 1]?.key === 'guidance';

  const pickDefault = (list: BksecPreviewRisk[]) => {
    if (isCreateMode.value) {
      const debugs = list.filter(isDebugRisk);
      const pool = debugs.length ? debugs : list;
      return pool.length ? pool[pool.length - 1].id : '';
    }
    const reals = list
      .filter(item => item.source === 'real')
      .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
    if (reals.length) return reals[0].id;
    return list.length ? list[list.length - 1].id : '';
  };

  const loadPreview = async () => {
    previewError.value = false;
    if (!props.riskTypeId) {
      previewRows.value = [];
      return;
    }
    previewLoading.value = true;
    try {
      const preview = await BksecManageService.fetchTicketPreview({
        risk_type_id: props.riskTypeId,
        field_values: props.fieldValues || {},
        strategy_name: props.strategyName,
        opened_at: openedAt.value,
        risk: selectedRisk.value,
      });
      previewRows.value = preview.rows;
    } catch {
      previewError.value = true;
      previewRows.value = [];
    } finally {
      previewLoading.value = false;
    }
  };

  const loadRisks = async () => {
    listLoading.value = true;
    openedAt.value = dayjs().format('YYYY-MM-DD HH:mm:ss');
    try {
      riskList.value = await BksecManageService.fetchPreviewRiskList({
        strategy_id: isCreateMode.value ? undefined : props.strategyId,
        strategy_type: props.strategyType,
      });
      selectedId.value = pickDefault(displayRisks.value);
      if (!riskList.value.length) {
        previewRows.value = [];
      }
      await loadPreview();
    } finally {
      listLoading.value = false;
    }
  };

  watch(() => props.isShow, (visible) => {
    if (visible) loadRisks();
  }, { immediate: true });

  const handleSend = async () => {
    const handler = handlerName.value;
    if (!handler) {
      messageError(t('请填写测试工单处理人'));
      return;
    }
    if (!selectedRisk.value) {
      messageError(t('请先选择一条风险单'));
      return;
    }
    sending.value = true;
    try {
      await BksecManageService.sendTestTicket({
        handler,
        risk_type_id: props.riskTypeId,
        field_values: props.fieldValues || {},
        risk_id: selectedRisk.value.risk_id || selectedRisk.value.id,
      });
      messageSuccess(t('测试工单已发送给 {handler}', { handler }));
    } finally {
      sending.value = false;
    }
  };
</script>
<style lang="postcss" scoped>
.bksec-preview {
  display: flex;
  flex-direction: column;
  gap: var(--audit-space-24);
  padding: var(--audit-space-24) var(--audit-space-40);
}

.bksec-preview-toolbar {
  display: flex;
  align-items: flex-start;
  gap: var(--audit-space-8);
}

.bksec-risk-field {
  display: flex;
  min-width: 0;
  flex: 1;
  align-items: stretch;
}

.bksec-risk-prefix {
  display: flex;
  height: 32px;
  padding: 0 var(--audit-space-8);
  margin-right: -1px;
  font-size: var(--audit-font-size-sm);
  line-height: var(--audit-line-height-sm);
  color: var(--audit-neutral-text-02);
  background: var(--audit-neutral-bg-02);
  border: 1px solid var(--audit-neutral-text-04);
  border-radius: var(--audit-radius-control) 0 0 var(--audit-radius-control);
  align-items: center;
  flex: none;
}

.bksec-preview-select {
  min-width: 0;
  flex: 1;
}

.bksec-preview-select :deep(.bk-select-tag) {
  height: 32px;
  padding: 0;
  background: transparent;
  border: 0;
  box-shadow: none;
}

.bksec-risk-trigger {
  position: relative;
  display: flex;
  width: 100%;
  height: 32px;
  padding: 0 28px 0 var(--audit-space-8);
  background: var(--audit-neutral-bg-04);
  border: 1px solid var(--audit-neutral-text-04);
  border-radius: 0 var(--audit-radius-control) var(--audit-radius-control) 0;
  align-items: center;
  gap: var(--audit-space-8);
}

.bksec-preview-select.is-focus .bksec-risk-trigger {
  border-color: var(--audit-brand-02);
}

.bksec-risk-text {
  overflow: hidden;
  font-size: var(--audit-font-size-sm);
  line-height: var(--audit-line-height-sm);
  color: var(--audit-neutral-text-02);
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 0 1 auto;
  min-width: 0;
}

.bksec-risk-text.is-placeholder {
  color: var(--audit-neutral-text-04);
}

.bksec-risk-arrow {
  position: absolute;
  right: 8px;
  font-size: var(--audit-font-size-sm);
  color: var(--audit-neutral-text-03);
}

.bksec-debug-tag {
  display: inline-flex;
  height: 18px;
  padding: 0 var(--audit-space-4);
  font-size: var(--audit-font-size-sm);
  line-height: var(--audit-line-height-sm);
  color: var(--audit-brand-01);
  background: var(--audit-brand-06);
  border-radius: var(--audit-radius-control);
  align-items: center;
  flex: none;
}

.bksec-risk-option {
  display: inline-flex;
  max-width: 100%;
  align-items: center;
  gap: var(--audit-space-8);
}

.bksec-preview-body {
  padding-left: 48px;
}

.bksec-desc-row {
  display: flex;
  min-height: 32px;
  padding: 6px 0;
  font-size: var(--audit-font-size-sm);
  line-height: var(--audit-line-height-sm);
  align-items: flex-start;
  gap: var(--audit-space-8);
}

.bksec-desc-row.is-spaced {
  margin-top: var(--audit-space-24);
}

.bksec-desc-label {
  position: relative;
  width: 84px;
  height: 20px;
  flex: 0 0 84px;
}

.bksec-desc-label-text {
  position: absolute;
  top: 0;
  right: 0;
  color: var(--audit-neutral-text-02);
  white-space: nowrap;
}

.bksec-desc-value {
  min-width: 0;
  overflow: hidden;
  color: var(--audit-neutral-text-01);
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.bksec-desc-value:has(.is-multiline) {
  overflow: visible;
  white-space: normal;
}

.is-multiline {
  display: block;
  white-space: pre-wrap;
}

.bksec-level {
  display: inline-flex;
  height: 22px;
  padding: 0 var(--audit-space-8);
  color: var(--audit-neutral-bg-04);
  border-radius: var(--audit-radius-control);
  align-items: center;
}

.bksec-level.is-high {
  background: var(--audit-danger-02);
}

.bksec-level.is-medium {
  background: var(--audit-warn-02);
}

.bksec-level.is-low {
  background: var(--audit-success-02);
}

.bksec-status {
  display: inline-flex;
  align-items: center;
  gap: var(--audit-space-8);
}

.bksec-status-mark {
  display: inline-flex;
  width: 16px;
  height: 16px;
  align-items: center;
  justify-content: center;
  flex: none;
}

.bksec-status-mark::after {
  width: 8px;
  height: 8px;
  content: '';
  background: var(--audit-warn-07);
  border: 1px solid var(--audit-warn-02);
  border-radius: 50%;
  box-sizing: border-box;
}

.bksec-test-form {
  padding: var(--audit-space-16) var(--audit-space-16) var(--audit-space-12);
}

.bksec-test-label {
  display: flex;
  margin-bottom: var(--audit-space-8);
  font-size: var(--audit-font-size-sm);
  line-height: var(--audit-line-height-sm);
  color: var(--audit-neutral-text-02);
  align-items: center;
  gap: var(--audit-space-4);
}

.bksec-test-required {
  color: var(--audit-danger-02);
}

.bksec-test-form :deep(.bk-user-selector) {
  width: 100%;
}
</style>
<style lang="postcss">
.bk-select-option.is-selected .bksec-debug-tag {
  color: var(--audit-brand-01);
  background: var(--audit-neutral-bg-04);
}

.bksec-test-pop.bk-pop2-content {
  padding: 0;
}

.bksec-test-pop .bk-pop-confirm-footer {
  padding: var(--audit-space-8) var(--audit-space-16);
  background: var(--audit-neutral-bg-02);
  border-top: 1px solid var(--audit-neutral-border-02);
}
</style>
