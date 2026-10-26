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
    ext-cls="bksec-preview-sideslider"
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
            @change="handleRiskChange">
            <template #trigger>
              <div class="bksec-risk-trigger">
                <span
                  v-bk-tooltips="labelTip('selected-risk', selectedRisk ? optionName(selectedRisk) : '')"
                  class="bksec-risk-text"
                  :class="{ 'is-placeholder': !selectedRisk }"
                  @mouseenter="syncLabelOverflow($event, 'selected-risk')">
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
                <span
                  v-bk-tooltips="optionTip(item.id, optionName(item))"
                  class="bksec-risk-option-text"
                  @mouseenter="syncLabelOverflow($event, `risk-option-${item.id}`)">
                  {{ optionName(item) }}
                </span>
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
            content: sending ? t('发送中') : t('请先选择一条风险单'),
            disabled: canSendTest && !sending,
          }">
          <bk-pop-confirm
            :cancel-text="t('取消')"
            :confirm-config="{
              loading: sending,
              disabled: !handlerName,
            }"
            :confirm-text="t('发送')"
            :disabled="sending"
            ext-cls="bksec-test-pop"
            placement="bottom-end"
            :popover-options="{ disableOutsideClick: true }"
            trigger="click"
            :width="360"
            @confirm="handleSend">
            <bk-button
              data-testid="bksec-send-test"
              :disabled="!canSendTest"
              :loading="sending"
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
      <div
        v-if="listLoading || previewLoading"
        class="bksec-preview-scroll bksec-preview-body"
        data-testid="bksec-preview-skeleton">
        <template
          v-for="row in previewSkeletonRows"
          :key="row.id">
          <span class="bksec-desc-label">
            <i
              class="bksec-skeleton-bar is-label"
              :class="row.label" />
          </span>
          <span class="bksec-desc-value">
            <i
              class="bksec-skeleton-bar"
              :class="[row.value, { 'is-tall': row.tall }]" />
          </span>
        </template>
      </div>
      <bk-exception
        v-else-if="previewError"
        class="bksec-preview-scroll"
        data-testid="bksec-preview-error"
        scene="part"
        type="500">
        {{ t('工单预览加载失败') }}
      </bk-exception>
      <div
        v-else
        class="bksec-preview-scroll bksec-preview-body">
        <template
          v-for="(row, index) in previewRows"
          :key="row.key">
          <span
            class="bksec-desc-label"
            :class="{ 'is-spaced': isExtensionStart(index) }">
            <span
              v-bk-tooltips="labelTip(row.key, row.label)"
              class="bksec-desc-label-text"
              @mouseenter="syncLabelOverflow($event, row.key)">{{ row.label }}：</span>
          </span>
          <span
            class="bksec-desc-value"
            :class="{ 'is-spaced': isExtensionStart(index) }">
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
              :class="{ 'is-multiline': row.kind === 'multiline' }">
              <template
                v-for="(part, partIndex) in textParts(row.value)"
                :key="`${row.key}-${partIndex}`">
                <span
                  v-if="part.url"
                  class="bksec-desc-url">{{ part.text }}</span>
                <template v-else>{{ part.text }}</template>
              </template>
            </span>
          </span>
        </template>
      </div>
    </div>
  </audit-sideslider>
</template>
<script setup lang="ts">
  import { Message } from 'bkui-vue';
  import dayjs from 'dayjs';
  import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import BksecManageService from '@service/bksec-manage';

  import { buildBksecConfig } from '@model/bksec/config';
  import BksecTestTaskStatus, { decideTaskPoll } from '@model/bksec/task-status';
  import type BksecPreviewRisk from '@model/bksec/preview-risk';
  import type { BksecTicketPreviewRow } from '@model/bksec/ticket-preview';

  import useMessage from '@hooks/use-message';

  import { canSendTestTicket, shouldRequestRemotePreview } from './form-rules';
  import { buildLocalPreview, mapRemotePreview } from './local-preview';

  import { isStrategyEditRoute } from '../../../utils/strategy-routes';

  interface Props {
    isShow: boolean;
    riskTypeId: string | null;
    riskTypeName?: string;
    fieldValues: Record<string, string>;
    fields?: Array<{ id: string; name: string; required?: boolean }>;
    strategyId?: string | number;
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
  const previewSkeletonRows = [
    { id: 'ticket-id', label: 'is-w48', value: 'is-v36' },
    { id: 'title', label: 'is-w64', value: 'is-v72' },
    { id: 'deadline', label: 'is-w96', value: 'is-v48' },
    { id: 'created', label: 'is-w64', value: 'is-v88' },
    { id: 'status', label: 'is-w64', value: 'is-v36' },
    { id: 'level', label: 'is-w48', value: 'is-v72' },
    { id: 'description', label: 'is-w80', value: 'is-v88', tall: true },
    { id: 'guidance', label: 'is-w96', value: 'is-v48', tall: true },
  ];
  const previewError = ref(false);
  const previewRows = ref<BksecTicketPreviewRow[]>([]);
  const openedAt = ref('');
  const sending = ref(false);
  const testForm = ref({ handler: '' });
  let pollGeneration = 0;

  const isCreateMode = computed(() => !isStrategyEditRoute(route.name));
  const isDebugRisk = (item: BksecPreviewRisk) => item.source === 'debug' || !item.risk_id;
  const displayRisks = computed(() => riskList.value);
  const selectedRisk = computed(() => displayRisks.value.find(item => item.id === selectedId.value) || null);
  const handlerName = computed(() => String(testForm.value.handler || '').trim());
  const canSendTest = computed(() => canSendTestTicket(selectedRisk.value?.risk_id));
  const sendDisabledTip = computed(() => t('请先选择一条风险单'));

  const optionName = (item: BksecPreviewRisk) => (
    item.risk_id ? `${item.risk_id} ${item.title}` : item.title
  );
  const showDebugTag = (item: BksecPreviewRisk) => isDebugRisk(item);

  const stopPoll = () => {
    pollGeneration += 1;
  };

  const labelOverflowed = reactive<Record<string, boolean>>({});
  const syncLabelOverflow = (event: MouseEvent, key: string) => {
    const el = event.currentTarget as HTMLElement;
    labelOverflowed[key] = el.scrollWidth > el.clientWidth;
  };
  const labelTip = (key: string, content: string) => ({
    content,
    disabled: !labelOverflowed[key],
    delay: 80,
  });
  const optionTip = (id: string, content: string) => ({
    ...labelTip(`risk-option-${id}`, content),
    placement: 'left',
    extCls: 'bksec-risk-option-tip',
  });

  const levelClass = (value: string) => {
    if (value === '高') return 'is-high';
    if (value === '中') return 'is-medium';
    if (value === '低') return 'is-low';
    return '';
  };
  const isExtensionStart = (index: number) => previewRows.value[index - 1]?.key === 'guidance';

  const textParts = (value: unknown) => {
    const source = String(value ?? '').trim() || '--';
    const parts: Array<{ url: boolean; text: string }> = [];
    const rule = /https?:\/\/\S+/g;
    let last = 0;
    let match = rule.exec(source);
    while (match) {
      const index = match.index ?? 0;
      if (index > last) parts.push({ url: false, text: source.slice(last, index) });
      parts.push({ url: true, text: match[0] });
      last = index + match[0].length;
      match = rule.exec(source);
    }
    if (last < source.length || !parts.length) {
      parts.push({ url: false, text: source.slice(last) });
    }
    return parts;
  };

  const previewFields = () => (props.fields || []).map(field => ({
    id: field.id,
    name: field.name,
  }));

  const renderLocal = () => {
    previewError.value = false;
    previewRows.value = buildLocalPreview({
      fieldValues: props.fieldValues || {},
      fields: previewFields(),
      riskTypeId: props.riskTypeId,
      riskTypeName: props.riskTypeName,
      strategyName: props.strategyName,
      openedAt: openedAt.value,
    });
  };

  let previewSeq = 0;
  let openSeq = 0;
  let openingPreview = false;

  const latestRiskId = () => {
    const latest = [...riskList.value].sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
    return latest[0]?.id || '';
  };

  const loadPreview = async () => {
    previewSeq += 1;
    const seq = previewSeq;
    previewError.value = false;
    const riskId = selectedRisk.value?.risk_id || '';
    if (!shouldRequestRemotePreview(isCreateMode.value, riskId)) {
      if (seq !== previewSeq) return;
      renderLocal();
      previewLoading.value = false;
      return;
    }
    previewLoading.value = true;
    try {
      const response = await BksecManageService.fetchTicketPreview({
        risk_id: riskId,
        bksec_config: buildBksecConfig({
          bksecEnabled: true,
          bksecRiskTypeId: props.riskTypeId,
          bksecRiskTypeName: props.riskTypeName,
          bksecFieldValues: props.fieldValues || {},
          bksecFieldMeta: (props.fields || []).map(field => ({
            key: field.id,
            name: field.name,
            required: !!field.required,
          })),
        }),
      });
      if (seq !== previewSeq) return;
      previewRows.value = mapRemotePreview({
        riskTypeId: props.riskTypeId,
        riskTypeName: props.riskTypeName,
        fields: previewFields(),
        response,
      });
    } catch {
      if (seq !== previewSeq) return;
      previewError.value = true;
      previewRows.value = [];
    } finally {
      if (seq === previewSeq) previewLoading.value = false;
    }
  };

  const wait = (ms: number) => new Promise(resolve => window.setTimeout(resolve, ms));

  const notifySendFailed = (detail?: string) => {
    const text = String(detail || '').trim();
    Message({
      theme: 'error',
      actions: [{ id: 'assistant', disabled: true }],
      message: {
        overview: t('测试工单发送失败'),
        suggestion: '',
        details: JSON.stringify(text || t('测试工单发送失败')),
        type: 'json',
      },
    });
  };

  const followTask = async (
    generation: number,
    load: () => Promise<BksecTestTaskStatus>,
    onSuccess?: () => void,
    initial?: BksecTestTaskStatus,
  ) => {
    let current = initial;
    while (decideTaskPoll(generation, pollGeneration, 'RUNNING') === 'continue') {
      const status = current || await load();
      current = undefined;
      const decision = decideTaskPoll(generation, pollGeneration, status.state);
      if (decision === 'stopped') return;
      if (decision === 'success') {
        onSuccess?.();
        return;
      }
      if (decision === 'failed') {
        notifySendFailed(status.failureHint);
        return;
      }
      await wait(800);
    }
  };

  let taskWatchSeq = 0;
  const watchRiskTask = async (riskId: string) => {
    taskWatchSeq += 1;
    const seq = taskWatchSeq;
    stopPoll();
    sending.value = false;
    const normalized = String(riskId || '').trim();
    if (!props.isShow || !canSendTestTicket(normalized)) return;
    const generation = pollGeneration;
    try {
      const status = await BksecManageService.fetchTestTaskStatus({ risk_id: normalized });
      if (seq !== taskWatchSeq || generation !== pollGeneration || !props.isShow) return;
      if (!status.hasState || status.state !== 'RUNNING') return;
      sending.value = true;
      await followTask(
        generation,
        () => BksecManageService.fetchTestTaskStatus({ risk_id: normalized }),
        undefined,
        status,
      );
    } catch {
      // 没有可恢复的测试任务，或查询失败时，按钮保持可发送
    } finally {
      if (generation === pollGeneration) sending.value = false;
    }
  };

  const handleRiskChange = (value: string) => {
    if (!value && (openingPreview || latestRiskId())) return;
    loadPreview();
    if (openingPreview) return;
    watchRiskTask(selectedRisk.value?.risk_id || '');
  };

  const openPreview = async () => {
    openSeq += 1;
    const ticket = openSeq;
    stopPoll();
    sending.value = false;
    openedAt.value = dayjs().format('YYYY-MM-DD HH:mm:ss');
    previewError.value = false;
    if (isCreateMode.value) {
      riskList.value = [];
      selectedId.value = '';
      renderLocal();
      return;
    }
    listLoading.value = true;
    previewLoading.value = true;
    openingPreview = true;
    try {
      riskList.value = await BksecManageService.fetchEditPreviewRisks(props.strategyId);
      if (ticket !== openSeq) return;
      const id = latestRiskId();
      selectedId.value = id;
      await nextTick();
      if (ticket !== openSeq) return;
      if (id && selectedId.value !== id) selectedId.value = id;
      const picked = riskList.value.find(item => item.id === selectedId.value);
      watchRiskTask(picked?.risk_id || '');
      await loadPreview();
      if (id && selectedId.value !== id) selectedId.value = id;
    } catch {
      if (ticket !== openSeq) return;
      previewError.value = true;
      previewRows.value = [];
      previewLoading.value = false;
    } finally {
      if (ticket === openSeq) {
        openingPreview = false;
        listLoading.value = false;
      }
    }
  };

  watch(() => props.isShow, (visible) => {
    if (visible) openPreview();
    else stopPoll();
  }, { immediate: true });

  onBeforeUnmount(() => {
    stopPoll();
  });

  const handleSend = async () => {
    const handler = handlerName.value;
    const riskId = selectedRisk.value?.risk_id || '';
    if (!handler) {
      messageError(t('请填写测试工单处理人'));
      return;
    }
    if (!canSendTestTicket(riskId)) {
      messageError(sendDisabledTip.value);
      return;
    }
    if (sending.value) return;
    testForm.value.handler = '';
    stopPoll();
    const generation = pollGeneration;
    sending.value = true;
    try {
      const created = await BksecManageService.sendTestTicket({
        risk_id: riskId,
        test_receivers: [handler],
        bksec_config: buildBksecConfig({
          bksecEnabled: true,
          bksecRiskTypeId: props.riskTypeId,
          bksecRiskTypeName: props.riskTypeName,
          bksecFieldValues: props.fieldValues || {},
          bksecFieldMeta: (props.fields || []).map(field => ({
            key: field.id,
            name: field.name,
            required: !!field.required,
          })),
        }),
      });
      if (!created.taskId) {
        notifySendFailed();
        return;
      }
      await followTask(
        generation,
        () => BksecManageService.fetchTestTaskStatus({ task_id: created.taskId }),
        () => messageSuccess(t('测试工单已发送给 {handler}', { handler })),
      );
    } catch (error) {
      if (generation === pollGeneration) {
        notifySendFailed(error instanceof Error ? error.message : '');
      }
    } finally {
      if (generation === pollGeneration) sending.value = false;
    }
  };
</script>
<style lang="postcss" scoped>
.bksec-preview {
  display: flex;
  flex: 1;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.bksec-preview-toolbar {
  display: flex;
  flex: none;
  align-items: flex-start;
  gap: var(--audit-space-8);
  padding: var(--audit-space-24) var(--audit-space-40) 0;
}

.bksec-preview-scroll {
  flex: 1;
  min-height: 0;
  padding: var(--audit-space-24) var(--audit-space-40);
  overflow: auto;
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
  flex: 1 1 auto;
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
  display: flex;
  width: 100%;
  min-width: 0;
  align-items: center;
  gap: var(--audit-space-8);
}

.bksec-risk-option-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.bksec-preview-body {
  display: grid;
  grid-template-columns: minmax(0, 124px) minmax(0, 1fr);
  align-content: start;
  min-width: 0;
  column-gap: var(--audit-space-8);
  font-size: var(--audit-font-size-sm);
  line-height: var(--audit-line-height-sm);
}

.bksec-desc-label,
.bksec-desc-value {
  min-height: 32px;
  padding: 6px 0;
}

.bksec-desc-label.is-spaced,
.bksec-desc-value.is-spaced {
  margin-top: var(--audit-space-24);
}

.bksec-desc-label {
  max-width: 124px;
  min-width: 0;
  overflow: hidden;
}

.bksec-desc-label-text {
  display: block;
  max-width: 100%;
  overflow: hidden;
  color: var(--audit-neutral-text-02);
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bksec-desc-value {
  min-width: 0;
  color: var(--audit-neutral-text-01);
  white-space: pre-wrap;
  word-break: normal;
  overflow-wrap: break-word;
}

.bksec-desc-url {
  word-break: break-all;
}

.bksec-skeleton-bar {
  display: block;
  height: 12px;
  margin: 4px 0;
  background: #e4e7ee;
  border-radius: var(--audit-radius-control);
  animation: bksec-preview-shimmer 1.2s ease-in-out infinite;
}

.bksec-skeleton-bar.is-label {
  margin-left: auto;
}

.bksec-skeleton-bar.is-tall {
  height: 32px;
}

.bksec-skeleton-bar.is-w48 { width: 48px; }
.bksec-skeleton-bar.is-w64 { width: 64px; }
.bksec-skeleton-bar.is-w80 { width: 80px; }
.bksec-skeleton-bar.is-w96 { width: 96px; }
.bksec-skeleton-bar.is-v36 { width: 36%; }
.bksec-skeleton-bar.is-v48 { width: 48%; }
.bksec-skeleton-bar.is-v72 { width: 72%; }
.bksec-skeleton-bar.is-v88 { width: 88%; }

@keyframes bksec-preview-shimmer {
  0%,
  100% {
    background: #e4e7ee;
  }

  50% {
    background: #f2f3f7;
  }
}

.bksec-level {
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

.bksec-level.is-high {
  background: var(--audit-danger-02);
  border-color: var(--audit-danger-02);
}

.bksec-level.is-medium {
  background: var(--audit-warn-02);
  border-color: var(--audit-warn-02);
}

.bksec-level.is-low {
  background: var(--audit-neutral-text-03);
  border-color: var(--audit-neutral-text-03);
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
.bk-select-option .bksec-risk-option {
  display: flex;
  width: 100%;
  min-width: 0;
}

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

.bksec-risk-option-tip.bk-popper {
  z-index: 100000 !important;
  max-width: 400px;
  word-break: break-all;
}

/* 人员选择下拉挂在 body 上，层级低于后打开的发送弹层时会被挡住，无法点选 */
.bk-user-selector-popover.bk-pop2-content {
  z-index: 100000 !important;
}

/* 抽屉内容区固定高度，只让预览明细滚动，风险单选择留在顶部 */
.bksec-preview-sideslider.bk-modal .bk-modal-content {
  display: flex;
  height: calc(100vh - 52px) !important;
  min-height: 0;
  overflow: hidden !important;
  flex-direction: column;
}

.bksec-preview-sideslider.bk-modal .bk-modal-content > div {
  display: flex;
  flex: 1;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.bksec-preview-sideslider .bk-sideslider-content,
.bksec-preview-sideslider .audit-sideslider-content {
  display: flex;
  flex: 1;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

/* 详情里的长错误按消息宽度折行。组件默认 white-space: pre，长句不会换行 */
.bk-message .json-formatter-row .json-formatter-string,
.bk-message .json-formatter-row .json-formatter-stringifiable {
  white-space: pre-wrap !important;
  word-break: break-all;
}
</style>
