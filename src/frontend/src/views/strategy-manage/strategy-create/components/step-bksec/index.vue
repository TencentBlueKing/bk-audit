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
  <smart-action
    class="create-strategy-page"
    :offset-target="getSmartActionOffsetTarget">
    <div class="bksec-card">
      <div class="bksec-title">
        <button
          class="bksec-collapse"
          type="button"
          @click="expanded = !expanded">
          <audit-icon
            class="bksec-collapse-icon"
            :class="{ 'is-collapsed': !expanded }"
            type="angle-line-down" />
        </button>
        <span class="bksec-title-text">{{ t('BKSEC安全工单') }}</span>
        <bk-switcher
          v-model="enabled"
          data-testid="bksec-ticket-switch"
          theme="primary"
          @change="handleSwitcher" />
        <div class="bksec-title-desc">
          <audit-icon
            class="bksec-info-icon"
            type="tishi" />
          <span>{{ t('启用后审计策略生成风险后，系统将调用处理套餐发送 BKSEC 安全工单') }}</span>
        </div>
      </div>
      <div
        v-if="enabled && expanded"
        class="bksec-body">
        <div
          class="bksec-type"
          data-testid="bksec-risk-type">
          <div class="bksec-label">
            <span class="is-required">*</span>
            {{ t('风险类型') }}
          </div>
          <bk-select
            v-model="riskTypeId"
            class="bksec-type-select"
            :class="{ 'is-error': typeError }"
            filterable
            :loading="typeLoading"
            :no-data-text="t('暂无匹配的风险类型')"
            :no-match-text="t('暂无匹配的风险类型')"
            :placeholder="t('请选择风险类型')"
            @change="handleTypeChange">
            <bk-option
              v-for="item in riskTypes"
              :id="item.id"
              :key="item.id"
              :name="item.label" />
          </bk-select>
          <div
            v-if="typeError"
            class="bksec-error"
            data-testid="bksec-type-error">
            {{ t('请选择风险类型') }}
          </div>
        </div>
        <bk-loading :loading="fieldLoading">
          <div
            v-if="fields.length"
            class="bksec-field-grid"
            data-testid="bksec-field-grid">
            <div
              v-for="field in fields"
              :key="field.id"
              class="bksec-field">
              <div class="bksec-field-head">
                <div class="bksec-field-label">
                  <span
                    v-if="field.required"
                    class="is-required">*</span>
                  <span>{{ field.label }}</span>
                  <audit-icon
                    v-if="field.tips"
                    v-bk-tooltips="field.tips"
                    class="bksec-info-icon"
                    type="tishi" />
                </div>
                <bk-popover
                  :arrow="false"
                  ext-cls="bksec-var-popover"
                  placement="bottom-end"
                  theme="light"
                  trigger="click"
                  width="480">
                  <button
                    class="bksec-var-trigger"
                    type="button"
                    @click="activeFieldId = field.id">
                    <audit-icon
                      class="bksec-var-icon"
                      type="bianliang" />
                    {{ t('引用变量') }}
                  </button>
                  <template #content>
                    <variable-popover
                      :groups="variableGroups"
                      @insert="insertToken" />
                  </template>
                </bk-popover>
              </div>
              <div
                class="bksec-input"
                :class="{ 'is-error': invalidFields.includes(field.id) }">
                <input
                  class="bksec-native-input"
                  :placeholder="t('请输入{name}', { name: field.label })"
                  :value="fieldValues[field.id] || ''"
                  @blur="rememberCaret(field.id, $event)"
                  @click="rememberCaret(field.id, $event)"
                  @keyup="rememberCaret(field.id, $event)"
                  @input="updateField(field.id, $event)">
              </div>
            </div>
          </div>
          <div
            v-if="fieldError"
            class="bksec-error"
            data-testid="bksec-field-error">
            {{ fieldError }}
          </div>
        </bk-loading>
      </div>
    </div>
    <template #action>
      <div class="action-button">
        <bk-button @click="handlePrevious">
          {{ t('上一步') }}
        </bk-button>
        <bk-button
          class="ml8"
          data-testid="bksec-ticket-submit"
          theme="primary"
          @click="handleNext">
          {{ primaryActionText }}
        </bk-button>
        <bk-button
          v-if="showSaveDraftButton"
          class="ml8"
          data-testid="bksec-ticket-draft"
          @click="handleSaveDraft">
          {{ t('保存草稿') }}
        </bk-button>
        <bk-button
          class="ml8"
          @click="handleCancel">
          {{ t('取消') }}
        </bk-button>
        <span
          v-bk-tooltips="{
            content: previewTip,
            disabled: canPreview,
          }">
          <bk-button
            class="ml8"
            data-testid="bksec-ticket-preview"
            :disabled="!canPreview"
            @click="showPreview = true">
            <audit-icon
              style="margin-right: 4px;"
              type="view" />
            {{ t('工单预览') }}
          </bk-button>
        </span>
      </div>
    </template>
  </smart-action>
  <preview-sideslider
    v-model:is-show="showPreview"
    :field-values="fieldValues"
    :risk-type-id="riskTypeId"
    :strategy-id="strategyId"
    :strategy-name="strategyName"
    :strategy-type="strategyType" />
</template>
<script setup lang="ts">
  import { computed, inject, onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import BksecManageService from '@service/bksec-manage';

  import type BksecPreviewRisk from '@model/bksec/preview-risk';
  import type BksecRiskType from '@model/bksec/risk-type';
  import type BksecRiskTypeField from '@model/bksec/risk-type-field';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import PreviewSideslider from './preview-sideslider.vue';
  import VariablePopover from './variable-popover.vue';
  import { buildVariableGroups } from './variable-groups';

  import { STRATEGY_SHOW_SAVE_DRAFT_KEY } from '../../composables/use-strategy-config-lock';
  import { getStrategyRouteNames } from '../../../utils/strategy-routes';

  interface Props {
    formData?: Record<string, any>;
    strategyType?: string;
    strategyName?: string;
  }
  interface Emits {
    (e: 'previousStep', step: number, params: Record<string, any>): void;
    (e: 'saveCurrentStep', params: Record<string, any>): void;
    (e: 'saveDraft', params: Record<string, any>): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    formData: () => ({}),
    strategyType: '',
    strategyName: '',
  });
  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const route = useRoute();
  const router = useRouter();
  const { messageError } = useMessage();
  const strategyRoutes = getStrategyRouteNames(route);
  const showSaveDraftButton = inject(STRATEGY_SHOW_SAVE_DRAFT_KEY, computed(() => true));

  const enabled = ref(false);
  const expanded = ref(true);
  const riskTypeId = ref<number | null>(null);
  const fieldValues = ref<Record<string, string>>({});
  const fields = ref<BksecRiskTypeField[]>([]);
  const typeError = ref(false);
  const fieldError = ref('');
  const invalidFields = ref<string[]>([]);
  const fieldLoading = ref(false);
  const showPreview = ref(false);
  const carets = ref<Record<string, number>>({});
  const activeFieldId = ref('');
  const sampleRisks = ref<BksecPreviewRisk[]>([]);
  const getSmartActionOffsetTarget = () => document.querySelector('.create-strategy-page');

  const { data: riskTypes, loading: typeLoading } = useRequest(BksecManageService.fetchRiskTypes, {
    defaultValue: [] as BksecRiskType[],
    manual: true,
  });

  const strategyId = computed(() => props.formData?.strategy_id || route.params.id);
  const primaryActionText = computed(() => t('完成创建'));
  const canPreview = computed(() => enabled.value && !!riskTypeId.value);
  const previewTip = computed(() => (
    riskTypeId.value ? t('请先启用BKSEC安全工单') : t('请先选择风险类型')
  ));
  const variableGroups = computed(() => buildVariableGroups({
    riskFields: props.formData?.risk_meta_field_config,
    eventFields: [
      ...(props.formData?.event_basic_field_configs || []),
      ...(props.formData?.event_data_field_configs || []),
      ...(props.formData?.event_evidence_field_configs || []),
    ],
    aiVariables: props.formData?.report_config?.ai_variables,
    strategyType: props.strategyType || props.formData?.strategy_type,
    sample: sampleRisks.value[sampleRisks.value.length - 1]?.sample || {},
  }));

  const buildParams = () => ({
    bksecEnabled: enabled.value,
    bksecRiskTypeId: riskTypeId.value,
    bksecFieldValues: { ...fieldValues.value },
  });

  const handleSwitcher = (value: boolean) => {
    enabled.value = value;
    if (!value) {
      typeError.value = false;
      fieldError.value = '';
      invalidFields.value = [];
    }
  };

  const handleTypeChange = async (id: number | null) => {
    typeError.value = false;
    fieldError.value = '';
    invalidFields.value = [];
    if (!id) {
      fields.value = [];
      return;
    }
    fieldLoading.value = true;
    try {
      const nextFields = await BksecManageService.fetchRiskTypeFields({ risk_type_id: Number(id) });
      const prev = fieldValues.value;
      const next: Record<string, string> = {};
      nextFields.forEach((field: BksecRiskTypeField) => {
        if (prev[field.id]) next[field.id] = prev[field.id];
      });
      if (!next.operator) next.operator = '{{operator}}';
      fieldValues.value = next;
      fields.value = nextFields;
    } finally {
      fieldLoading.value = false;
    }
  };

  const updateField = (fieldId: string, event: Event) => {
    const input = event.target as HTMLInputElement;
    fieldValues.value = { ...fieldValues.value, [fieldId]: input.value };
    carets.value[fieldId] = input.selectionStart ?? input.value.length;
    invalidFields.value = invalidFields.value.filter(id => id !== fieldId);
  };

  const rememberCaret = (fieldId: string, event: Event) => {
    const input = event.target as HTMLInputElement;
    carets.value[fieldId] = input.selectionStart ?? input.value.length;
  };

  const insertToken = (insertText: string) => {
    const fieldId = activeFieldId.value;
    if (!fieldId) return;
    const current = fieldValues.value[fieldId] || '';
    const pos = carets.value[fieldId] ?? current.length;
    fieldValues.value = {
      ...fieldValues.value,
      [fieldId]: `${current.slice(0, pos)}${insertText}${current.slice(pos)}`,
    };
    carets.value[fieldId] = pos + insertText.length;
  };

  const validate = () => {
    typeError.value = false;
    fieldError.value = '';
    invalidFields.value = [];
    if (!enabled.value) return true;
    if (!riskTypeId.value) {
      typeError.value = true;
      messageError(t('请选择风险类型'));
      return false;
    }
    const missing = fields.value.filter(field => field.required && !String(fieldValues.value[field.id] || '').trim());
    if (missing.length) {
      invalidFields.value = missing.map(field => field.id);
      fieldError.value = `${t('请填写')}${missing.map(field => field.label).join('、')}`;
      messageError(fieldError.value);
      return false;
    }
    return true;
  };

  const handlePrevious = () => {
    emit('previousStep', 4, buildParams());
  };
  const handleNext = () => {
    if (!validate()) return;
    emit('saveCurrentStep', buildParams());
  };
  const handleSaveDraft = () => {
    emit('saveDraft', buildParams());
  };
  const handleCancel = () => {
    router.push({ name: strategyRoutes.list });
  };

  onMounted(async () => {
    enabled.value = !!props.formData?.bksecEnabled;
    riskTypeId.value = props.formData?.bksecRiskTypeId ?? null;
    fieldValues.value = { ...(props.formData?.bksecFieldValues || {}) };
    if (riskTypeId.value) await handleTypeChange(riskTypeId.value);
    sampleRisks.value = await BksecManageService.fetchPreviewRiskList({
      strategy_id: strategyId.value,
      strategy_type: props.strategyType || props.formData?.strategy_type,
    });
  });
</script>
<style lang="postcss" scoped>
.bksec-card {
  margin-bottom: var(--audit-space-16);
  background: var(--audit-neutral-bg-04);
  border-radius: var(--audit-radius-container);
  box-shadow: var(--audit-shadow-card);
}

.bksec-title {
  display: flex;
  height: auto;
  padding: var(--audit-space-12) var(--audit-space-24) var(--audit-space-16);
  font-size: var(--audit-font-size-base);
  font-weight: var(--audit-font-weight-bold);
  line-height: var(--audit-line-height-base);
  color: var(--audit-neutral-text-01);
  align-items: center;
}

.bksec-collapse {
  display: inline-flex;
  width: 16px;
  height: 16px;
  padding: 0;
  margin-right: var(--audit-space-8);
  color: var(--audit-neutral-text-02);
  cursor: pointer;
  background: transparent;
  border: 0;
  align-items: center;
  justify-content: center;
}

.bksec-collapse-icon {
  font-size: var(--audit-font-size-lg);
}

.bksec-collapse-icon.is-collapsed {
  transform: rotate(-90deg);
}

.bksec-body {
  padding: var(--audit-space-16) var(--audit-space-24) var(--audit-space-24);
  border-top: 1px solid var(--audit-neutral-border-02);
}

.bksec-title-text {
  margin-right: 13px;
}

.bksec-title-desc {
  display: flex;
  margin-left: 13px;
  font-size: var(--audit-font-size-sm);
  font-weight: var(--audit-font-weight-regular);
  color: var(--audit-neutral-text-02);
  align-items: center;
  gap: var(--audit-space-4);
}

.bksec-info-icon {
  font-size: var(--audit-font-size-base);
  color: var(--audit-brand-02);
}

.bksec-field {
  margin-top: var(--audit-space-24);
}

.bksec-label,
.bksec-field-label {
  display: flex;
  min-width: 0;
  font-size: var(--audit-font-size-sm);
  font-weight: var(--audit-font-weight-regular);
  line-height: var(--audit-line-height-sm);
  color: var(--audit-neutral-text-02);
  align-items: center;
  gap: var(--audit-space-4);
}

.bksec-label {
  margin-bottom: var(--audit-space-8);
}

.bksec-field-head {
  display: flex;
  height: 20px;
  margin-bottom: var(--audit-space-8);
  align-items: center;
  justify-content: space-between;
  gap: var(--audit-space-8);
}

.is-required {
  color: var(--audit-danger-02);
}

.bksec-type-select {
  width: 100%;
}

.bksec-type-select.is-error :deep(.bk-select-trigger) {
  border-color: var(--audit-danger-02);
}

.bksec-field-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  column-gap: var(--audit-space-24);
}

.bksec-input {
  display: flex;
  height: 32px;
  background: var(--audit-neutral-bg-04);
  border: 1px solid var(--audit-neutral-border-01);
  border-radius: var(--audit-radius-control);
  align-items: center;
}

.bksec-input.is-error {
  border-color: var(--audit-danger-02);
}

.bksec-native-input {
  height: 100%;
  min-width: 0;
  padding: 0 var(--audit-space-8);
  font-size: var(--audit-font-size-sm);
  line-height: var(--audit-line-height-sm);
  color: var(--audit-neutral-text-01);
  background: transparent;
  border: 0;
  outline: none;
  flex: 1;
}

.bksec-native-input::placeholder {
  color: var(--audit-neutral-text-04);
}

.bksec-var-trigger {
  display: inline-flex;
  padding: 0;
  font-size: var(--audit-font-size-sm);
  line-height: var(--audit-line-height-sm);
  color: var(--audit-brand-02);
  cursor: pointer;
  background: transparent;
  border: 0;
  align-items: center;
  gap: var(--audit-space-4);
  flex: none;
}

.bksec-var-icon {
  font-size: var(--audit-font-size-lg);
}

.bksec-error {
  margin-top: var(--audit-space-8);
  font-size: var(--audit-font-size-sm);
  color: var(--audit-danger-02);
}
</style>
<style lang="postcss">
.bksec-var-popover.bk-pop2-content,
.bksec-var-popover .bk-pop2-content {
  padding: var(--audit-space-4) 0;
}
</style>
