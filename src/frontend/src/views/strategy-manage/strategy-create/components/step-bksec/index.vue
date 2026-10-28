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
  <div>
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
          ref="typeFieldRef"
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
            :filter-option="false"
            filterable
            :no-data-text="t('暂无匹配的风险类型')"
            :no-match-text="t('暂无匹配的风险类型')"
            :placeholder="t('请选择风险类型')"
            :popover-options="riskTypePopoverOptions"
            :remote-method="searchRiskTypes"
            @change="handleTypeChange"
            @toggle="handleTypeMenuToggle">
            <bk-option-group
              v-for="project in displayProjects"
              :key="project.id"
              :label="project.name">
              <bk-option
                v-for="item in project.riskTypes"
                :id="item.id"
                :key="`${project.id}-${item.id}`"
                :name="item.label" />
            </bk-option-group>
            <div
              v-if="keptRiskType && !selectedInList"
              class="bksec-kept-option">
              <bk-option
                :id="keptRiskType.id"
                :name="keptRiskType.label"
                :ref="markKeptOption" />
            </div>
          </bk-select>
          <div
            v-if="typeError"
            class="bksec-error"
            data-testid="bksec-type-error">
            {{ t('请选择风险类型') }}
          </div>
          <div
            v-if="typeLoadError"
            class="bksec-error"
            data-testid="bksec-type-load-error">
            {{ t('风险类型加载失败') }}
          </div>
        </div>
        <div
          v-if="fields.length"
          class="bksec-fields">
            <div class="bksec-fields-title">
              {{ t('工单字段') }}
            </div>
            <div
              class="bksec-field-grid"
              data-testid="bksec-field-grid">
            <div
              v-for="field in fields"
              :key="field.id"
              :ref="(el) => setFieldAnchorRef(field.id, el)"
              class="bksec-field">
              <div class="bksec-field-head">
                <div class="bksec-field-label">
                  <span
                    v-if="field.required"
                    class="is-required">*</span>
                  <span>{{ field.label }}</span>
                  <audit-icon
                    v-if="field.id === 'target'"
                    v-bk-tooltips="t('填写资产标识信息，例如资产类型为 account 时，填写对应账号')"
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
                    @click="activateFieldEdit(field.id)">
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
                <button
                  v-if="!isFieldEditing(field.id)"
                  v-bk-tooltips="fieldValueTip(field.id)"
                  class="bksec-field-display"
                  type="button"
                  @click="activateFieldEdit(field.id, $event)"
                  @mouseenter="syncFieldOverflow($event, field.id)">
                  <template
                    v-for="(item, index) in parseDynamicFieldValue(fieldValues[field.id] || '')"
                    :key="`${index}-${item.value}`">
                    <span :class="{ 'is-variable': item.isVariable }">{{ item.value }}</span>
                  </template>
                  <span
                    v-if="!fieldValues[field.id]"
                    class="bksec-field-placeholder">
                    {{ t('请输入{name}', { name: field.label }) }}
                  </span>
                </button>
                <input
                  v-else
                  :ref="(el) => setFieldInputRef(field.id, el)"
                  class="bksec-native-input"
                  :placeholder="t('请输入{name}', { name: field.label })"
                  :value="fieldValues[field.id] || ''"
                  @blur="finishFieldEdit(field.id, $event)"
                  @click="rememberCaret(field.id, $event)"
                  @keyup="rememberCaret(field.id, $event)"
                  @input="updateField(field.id, $event)">
              </div>
              <div
                v-if="invalidFields.includes(field.id)"
                class="bksec-error">
                {{ t('请填写') }}{{ field.label }}
              </div>
            </div>
          </div>
        </div>
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
    :fields="previewFields"
    :risk-type-id="riskTypeId"
    :risk-type-name="riskTypeName"
    :strategy-id="strategyId"
    :strategy-name="strategyName"
    :strategy-type="strategyType" />
  </div>
</template>
<script setup lang="ts">
  import { computed, inject, nextTick, onBeforeUnmount, onMounted, onUpdated, reactive, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import BksecManageService from '@service/bksec-manage';

  import type BksecPreviewRisk from '@model/bksec/preview-risk';
  import type BksecProject from '@model/bksec/project';
  import type BksecRiskType from '@model/bksec/risk-type';
  import type BksecRiskTypeField from '@model/bksec/risk-type-field';

  import useRequest from '@hooks/use-request';

  import PreviewSideslider from './preview-sideslider.vue';
  import VariablePopover from './variable-popover.vue';
  import {
    insertDynamicFieldToken,
    missingRequiredFields,
    parseDynamicFieldValue,
    retainFieldValues,
  } from './form-rules';
  import { buildVariableGroups } from './variable-groups';

  import { STRATEGY_SHOW_SAVE_DRAFT_KEY } from '../../composables/use-strategy-config-lock';
  import { getStrategyRouteNames, isStrategyEditRoute } from '../../../utils/strategy-routes';

  interface Props {
    formData?: Record<string, any>;
    strategyType?: string;
    strategyName?: string;
  }
  interface Emits {
    (e: 'previousStep', step: number, params: Record<string, any>): void;
    (e: 'saveCurrentStep', params: Record<string, any>): void;
    (e: 'saveDraft', params: Record<string, any>): void;
    // 向导对每个步骤统一绑定，本步不使用，声明后避免多根节点无法继承
    (e: 'cancel'): void;
    (e: 'nextStep', step: number, params: Record<string, any>): void;
    (e: 'resetHitConditions'): void;
    (e: 'showPreview'): void;
    (e: 'submitData'): void;
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
  const strategyRoutes = getStrategyRouteNames(route);
  const showSaveDraftButton = inject(STRATEGY_SHOW_SAVE_DRAFT_KEY, computed(() => true));

  const enabled = ref(!!props.formData?.bksecEnabled);
  const expanded = ref(true);
  const riskTypeId = ref<string | null>(
    props.formData?.bksecRiskTypeId ? String(props.formData.bksecRiskTypeId) : null,
  );
  const riskTypeName = ref(props.formData?.bksecRiskTypeName || '');
  const fieldValues = ref<Record<string, string>>({ ...(props.formData?.bksecFieldValues || {}) });
  const fields = ref<BksecRiskTypeField[]>([]);
  const typeError = ref(false);
  const invalidFields = ref<string[]>([]);
  const typeFieldRef = ref<HTMLElement | null>(null);
  const fieldAnchorRefs = ref<Record<string, HTMLElement | null>>({});
  const showPreview = ref(false);
  const carets = ref<Record<string, number>>({});
  const activeFieldId = ref('');
  const editingFields = ref<Record<string, boolean>>({});
  const fieldInputRefs = ref<Record<string, HTMLInputElement | null>>({});
  const fieldOverflowed = reactive<Record<string, boolean>>({});
  const sampleRisks = ref<BksecPreviewRisk[]>([]);
  const getSmartActionOffsetTarget = () => document.querySelector('.create-strategy-page');

  const searchKeyword = ref('');
  const projectCatalog = ref<BksecProject[]>([]);

  const {
    data: projects,
    loading: typeLoading,
    error: typeLoadError,
    run: loadProjects,
  } = useRequest(BksecManageService.fetchProjects, {
    defaultValue: [] as BksecProject[],
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

  const previewFields = computed(() => fields.value.map(field => ({
    id: field.id,
    name: field.name,
  })));

  const findRiskType = (id: string) => {
    const sources = [projects.value, projectCatalog.value];
    for (const source of sources) {
      for (const project of source) {
        const type = project.riskTypes.find((item: BksecRiskType) => item.id === id);
        if (type) return { project, type };
      }
    }
    return undefined;
  };

  const displayProjects = computed(() => projects.value.filter(project => project.riskTypes.length));

  const keptRiskType = computed(() => {
    if (!riskTypeId.value) return undefined;
    const matched = findRiskType(riskTypeId.value);
    if (matched) return { id: matched.type.id, label: matched.type.label };
    if (!riskTypeName.value) return undefined;
    const suffix = `(${riskTypeId.value})`;
    return {
      id: riskTypeId.value,
      label: riskTypeName.value.endsWith(suffix) ? riskTypeName.value : `${riskTypeName.value}${suffix}`,
    };
  });

  const selectedInList = computed(() => {
    const selectedId = riskTypeId.value ? String(riskTypeId.value) : '';
    if (!selectedId) return false;
    return displayProjects.value.some(project => (
      project.riskTypes.some(type => type.id === selectedId)
    ));
  });

  const riskTypePopoverOptions = { extCls: 'bksec-risk-type-popover' };
  let latestSearchDom: string | null = null;
  let riskTypeComposing = false;
  let enterSearchValue = '';
  let enterDuringComposition = false;
  let enterToken = 0;

  const riskTypeSearchInput = (target: EventTarget | null): HTMLInputElement | null => {
    const input = target as HTMLInputElement | null;
    if (!input?.classList?.contains('bk-select-search-input')) return null;
    if (!input.closest('.bksec-risk-type-popover')) return null;
    return input;
  };

  const markKeptOption = (option: { visible?: boolean } | null) => {
    if (option) option.visible = false;
  };

  const rememberSearchInput = (event: Event) => {
    if (riskTypeComposing) return;
    const input = riskTypeSearchInput(event.target);
    if (!input) return;
    latestSearchDom = input.value;
  };

  const markRiskTypeCompositionStart = (event: Event) => {
    if (!riskTypeSearchInput(event.target)) return;
    riskTypeComposing = true;
  };

  const markRiskTypeCompositionEnd = (event: CompositionEvent) => {
    const input = riskTypeSearchInput(event.target);
    if (!input) return;
    riskTypeComposing = false;
    if (enterToken) enterDuringComposition = true;
    latestSearchDom = input.value;
  };

  const handleTypeMenuToggle = (open: boolean) => {
    if (!open) {
      latestSearchDom = null;
      enterToken = 0;
      enterDuringComposition = false;
    }
  };

  const rememberEnterSearchValue = (event: KeyboardEvent) => {
    if (event.key !== 'Enter' && event.code !== 'NumpadEnter') return;
    const input = riskTypeSearchInput(event.target);
    if (!input) return;
    if (!enterToken) enterSearchValue = input.value;
    enterToken += 1;
    if (event.isComposing || event.keyCode === 229 || riskTypeComposing) {
      enterDuringComposition = true;
    }
  };

  const selectHighlightedRiskType = () => {
    const menu = document.querySelector('.bksec-risk-type-popover');
    if (!menu || typeLoading.value) return;
    const input = menu.querySelector('.bk-select-search-input') as HTMLInputElement | null;
    if (!input || input.value.trim() !== searchKeyword.value) return;
    const hovered = menu.querySelector('.bk-option-group .bk-select-option.is-hover');
    const fallback = menu.querySelector('.bk-option-group .bk-select-option');
    const option = (hovered || fallback) as HTMLElement | null;
    option?.click();
  };

  const confirmRiskTypeByEnter = (event: KeyboardEvent) => {
    if (event.key !== 'Enter' && event.code !== 'NumpadEnter') return;
    const input = riskTypeSearchInput(event.target);
    if (!input) return;
    const token = enterToken;
    const valueAtKeyup = input.value;
    window.setTimeout(() => {
      const confirmedComposition = enterDuringComposition;
      if (token !== enterToken) return;
      enterToken = 0;
      enterDuringComposition = false;
      if (confirmedComposition || riskTypeComposing) return;
      if (input.value !== enterSearchValue || input.value !== valueAtKeyup) return;
      selectHighlightedRiskType();
    }, 30);
  };

  const applyRiskType = (id: string | null) => {
    if (!id) {
      fields.value = [];
      return;
    }
    const matched = findRiskType(id);
    if (!matched) return;
    riskTypeName.value = matched.type.name;
    fields.value = matched.type.fields;
    fieldValues.value = retainFieldValues(fieldValues.value, matched.type.fields);
  };

  const searchRiskTypes = (keyword: string) => {
    const text = keyword.trim();
    searchKeyword.value = text;
    if (!text && projectCatalog.value.length) {
      projects.value = projectCatalog.value;
    }
    return loadProjects(text ? { name__icontains: text } : {})
      .then((list) => {
        if (searchKeyword.value !== text) return;
        if (!text) projectCatalog.value = list || [];
      })
      .catch(() => undefined);
  };

  const buildParams = () => ({
    bksecEnabled: enabled.value,
    bksecRiskTypeId: riskTypeId.value,
    bksecRiskTypeName: riskTypeName.value,
    bksecFieldValues: { ...fieldValues.value },
    bksecFieldMeta: fields.value.length
      ? fields.value.map(field => ({
        key: field.id,
        name: field.name,
        required: field.required,
      }))
      : (props.formData?.bksecFieldMeta || []),
  });

  const handleSwitcher = (value: boolean) => {
    enabled.value = value;
    if (!value) {
      typeError.value = false;
      invalidFields.value = [];
    }
  };

  const handleTypeChange = (id: string | number | null) => {
    typeError.value = false;
    invalidFields.value = [];
    const nextId = id === null || id === undefined || id === '' ? null : String(id);
    riskTypeId.value = nextId;
    if (!nextId) {
      fields.value = [];
      return;
    }
    applyRiskType(nextId);
  };

  watch(projects, (list) => {
    if (!searchKeyword.value && list.length) projectCatalog.value = list;
    // 搜索只刷新下拉。当前选中没变时，不重绘下面的工单字段。
    if (!riskTypeId.value || fields.value.length) return;
    applyRiskType(riskTypeId.value);
  });

  const updateField = (fieldId: string, event: Event) => {
    const input = event.target as HTMLInputElement;
    fieldValues.value = { ...fieldValues.value, [fieldId]: input.value };
    // 空值时未点过输入框也会直接显示 input。第一下写入后要保持编辑态，否则会立刻换成展示按钮并失焦。
    editingFields.value[fieldId] = true;
    carets.value[fieldId] = input.selectionStart ?? input.value.length;
    invalidFields.value = invalidFields.value.filter(id => id !== fieldId);
  };

  const rememberCaret = (fieldId: string, event: Event) => {
    const input = event.target as HTMLInputElement;
    carets.value[fieldId] = input.selectionStart ?? input.value.length;
  };

  const setFieldInputRef = (fieldId: string, element: unknown) => {
    fieldInputRefs.value[fieldId] = element as HTMLInputElement | null;
  };

  const setFieldAnchorRef = (fieldId: string, element: unknown) => {
    fieldAnchorRefs.value[fieldId] = element instanceof HTMLElement ? element : null;
  };

  const scrollToNearestError = (nodes: Array<HTMLElement | null | undefined>) => {
    const visible = nodes.filter((node): node is HTMLElement => !!node);
    if (!visible.length) return;
    const viewportCenter = window.innerHeight / 2;
    const target = visible.reduce((nearest, node) => {
      const rect = node.getBoundingClientRect();
      const distance = Math.abs(rect.top + rect.height / 2 - viewportCenter);
      return distance < nearest.distance ? { node, distance } : nearest;
    }, { node: visible[0], distance: Number.POSITIVE_INFINITY }).node;
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  const isFieldEditing = (fieldId: string) => (
    editingFields.value[fieldId] ?? !fieldValues.value[fieldId]
  );

  const syncFieldOverflow = (event: MouseEvent, fieldId: string) => {
    const el = event.currentTarget as HTMLElement;
    fieldOverflowed[fieldId] = el.scrollWidth > el.clientWidth || el.scrollHeight > el.clientHeight;
  };
  const fieldValueTip = (fieldId: string) => ({
    content: fieldValues.value[fieldId] || '',
    disabled: !fieldValues.value[fieldId] || !fieldOverflowed[fieldId],
    delay: 80,
    extCls: 'bksec-field-value-tip',
    maxWidth: 400,
  });

  const caretClientX = (node: Text, index: number) => {
    const range = document.createRange();
    range.setStart(node, index);
    range.setEnd(node, index);
    const rect = range.getBoundingClientRect();
    if (rect.left || rect.right) return rect.left || rect.right;
    if (index === 0) return 0;
    range.setStart(node, index - 1);
    range.setEnd(node, index);
    return range.getBoundingClientRect().right;
  };

  const offsetWithinText = (node: Text, x: number) => {
    let nearest = node.data.length;
    let nearestDistance = Number.POSITIVE_INFINITY;
    for (let index = 0; index <= node.data.length; index += 1) {
      const distance = Math.abs(caretClientX(node, index) - x);
      if (distance < nearestDistance) {
        nearestDistance = distance;
        nearest = index;
      }
    }
    return nearest;
  };

  const caretFromDisplayClick = (event: MouseEvent) => {
    const root = event.currentTarget;
    if (!(root instanceof HTMLElement)) return 0;
    const spans = Array.from(root.children).filter((node): node is HTMLElement => (
      node instanceof HTMLElement && !node.classList.contains('bksec-field-placeholder')
    ));
    if (!spans.length) return 0;
    const x = event.clientX;
    let offset = 0;
    for (const span of spans) {
      const rect = span.getBoundingClientRect();
      const textNode = span.firstChild instanceof Text ? span.firstChild : null;
      const textLength = textNode?.data.length ?? (span.textContent || '').length;
      if (x < rect.left) return offset;
      if (x <= rect.right) {
        return offset + (textNode ? offsetWithinText(textNode, x) : textLength);
      }
      offset += textLength;
    }
    return offset;
  };

  const activateFieldEdit = (fieldId: string, event?: MouseEvent) => {
    const clickedCaret = event ? caretFromDisplayClick(event) : undefined;
    activeFieldId.value = fieldId;
    editingFields.value[fieldId] = true;
    if (clickedCaret !== undefined) {
      carets.value[fieldId] = clickedCaret;
    }
    nextTick(() => {
      const input = fieldInputRefs.value[fieldId];
      const position = clickedCaret ?? carets.value[fieldId] ?? input?.value.length ?? 0;
      input?.focus();
      input?.setSelectionRange(position, position);
    });
  };

  const staysInFieldEditor = (fieldId: string, next: Element) => {
    if (next.closest('.bksec-var-panel')) return true;
    const trigger = next.closest('.bksec-var-trigger');
    return !!trigger && trigger.closest('.bksec-field') === fieldAnchorRefs.value[fieldId];
  };

  const finishFieldEdit = (fieldId: string, event: FocusEvent) => {
    rememberCaret(fieldId, event);
    const next = event.relatedTarget;
    // 焦点进了变量面板或当前字段的引用按钮时，不要退出编辑，否则会先闪成变量标签再聚焦回来。
    if (next instanceof Element && staysInFieldEditor(fieldId, next)) return;
    editingFields.value[fieldId] = false;
  };

  const insertToken = (insertText: string) => {
    const fieldId = activeFieldId.value;
    if (!fieldId) return;
    const current = fieldValues.value[fieldId] || '';
    const pos = carets.value[fieldId] ?? current.length;
    const inserted = insertDynamicFieldToken(current, insertText, pos);
    fieldValues.value = {
      ...fieldValues.value,
      [fieldId]: inserted.value,
    };
    carets.value[fieldId] = inserted.caret;
    editingFields.value[fieldId] = true;
    invalidFields.value = invalidFields.value.filter(id => id !== fieldId);
    nextTick(() => {
      const input = fieldInputRefs.value[fieldId];
      input?.focus();
      input?.setSelectionRange(inserted.caret, inserted.caret);
    });
  };

  const validate = () => {
    typeError.value = false;
    invalidFields.value = [];
    if (!enabled.value) return true;
    if (!riskTypeId.value) {
      typeError.value = true;
      expanded.value = true;
      nextTick(() => scrollToNearestError([typeFieldRef.value]));
      return false;
    }
    const missing = missingRequiredFields(fields.value, fieldValues.value);
    if (missing.length) {
      invalidFields.value = missing.map(field => field.id);
      expanded.value = true;
      nextTick(() => scrollToNearestError(missing.map(field => fieldAnchorRefs.value[field.id])));
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

  onUpdated(() => {
    if (riskTypeComposing || latestSearchDom === null) return;
    const input = document.querySelector('.bksec-risk-type-popover .bk-select-search-input') as HTMLInputElement | null;
    if (!input || input.value === latestSearchDom) return;
    input.value = latestSearchDom;
  });

  onBeforeUnmount(() => {
    document.removeEventListener('input', rememberSearchInput, true);
    document.removeEventListener('keydown', rememberEnterSearchValue);
    document.removeEventListener('keyup', confirmRiskTypeByEnter);
    document.removeEventListener('compositionstart', markRiskTypeCompositionStart, true);
    document.removeEventListener('compositionend', markRiskTypeCompositionEnd, true);
  });

  onMounted(async () => {
    document.addEventListener('input', rememberSearchInput, true);
    document.addEventListener('keydown', rememberEnterSearchValue);
    document.addEventListener('keyup', confirmRiskTypeByEnter);
    document.addEventListener('compositionstart', markRiskTypeCompositionStart, true);
    document.addEventListener('compositionend', markRiskTypeCompositionEnd, true);
    if (!isStrategyEditRoute(route.name)) return;
    sampleRisks.value = await BksecManageService.fetchEditPreviewRisks(strategyId.value);
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
  color: var(--audit-neutral-text-02);
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
  border-top: 1px solid var(--audit-neutral-border-01);
}

.bksec-title-text {
  margin-right: 13px;
}

.bksec-title-desc {
  display: flex;
  margin-left: 13px;
  font-size: var(--audit-font-size-sm);
  font-weight: var(--audit-font-weight-regular);
  line-height: var(--audit-line-height-sm);
  color: var(--audit-neutral-text-02);
  align-items: center;
  gap: var(--audit-space-4);
}

.bksec-info-icon {
  font-size: var(--audit-font-size-base);
  color: var(--audit-brand-02);
}

.bksec-field {
  position: relative;
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
  gap: 2px;
}

.bksec-label {
  margin-bottom: 6px;
}

.bksec-field-head {
  display: flex;
  height: 20px;
  margin-bottom: 6px;
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

.bksec-kept-option {
  display: none;
}

.bksec-type-select :deep(.bk-select-trigger) {
  border-color: var(--audit-neutral-text-04);
}

.bksec-type-select :deep(.bk-input--text) {
  font-size: var(--audit-font-size-sm);
  line-height: var(--audit-line-height-sm);
  color: var(--audit-neutral-text-02);
}

.bksec-type-select :deep(.bk-input--text::placeholder) {
  color: var(--audit-neutral-text-04);
}

.bksec-type-select.is-error :deep(.bk-select-trigger) {
  border-color: var(--audit-danger-02);
}

.bksec-fields {
  margin-top: var(--audit-space-24);
}

.bksec-fields-title {
  font-size: var(--audit-font-size-base);
  font-weight: var(--audit-font-weight-bold);
  line-height: var(--audit-line-height-base);
  color: var(--audit-neutral-text-02);
}

.bksec-field-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  margin-top: var(--audit-space-12);
  column-gap: var(--audit-space-24);
  row-gap: var(--audit-space-24);
}

.bksec-input {
  display: flex;
  height: 32px;
  background: var(--audit-neutral-bg-04);
  border: 1px solid var(--audit-neutral-text-04);
  border-radius: var(--audit-radius-control);
  align-items: center;
}

.bksec-input.is-error {
  border-color: var(--audit-danger-02);
}

.bksec-field-display {
  box-sizing: border-box;
  display: flex;
  width: 100%;
  min-width: 0;
  height: 100%;
  padding: var(--audit-space-4) var(--audit-space-8);
  overflow: hidden;
  font-size: var(--audit-font-size-sm);
  line-height: var(--audit-line-height-sm);
  color: var(--audit-neutral-text-02);
  text-align: left;
  white-space: nowrap;
  cursor: text;
  background: transparent;
  border: 0;
  align-items: center;
  flex-wrap: nowrap;
}

.bksec-field-display .is-variable {
  padding: 0 var(--audit-space-4);
  margin: 0 1px;
  background: var(--audit-neutral-bg-01);
  border-radius: var(--audit-radius-control);
}

.bksec-field-placeholder {
  color: var(--audit-neutral-text-04);
}

.bksec-native-input {
  height: 100%;
  min-width: 0;
  padding: 0 var(--audit-space-8);
  font-size: var(--audit-font-size-sm);
  line-height: var(--audit-line-height-sm);
  color: var(--audit-neutral-text-02);
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

.bksec-field > .bksec-error {
  position: absolute;
  top: 100%;
  right: 0;
  left: 0;
  z-index: 1;
  margin-top: 2px;
  overflow: hidden;
  line-height: var(--audit-line-height-sm);
  text-overflow: ellipsis;
  white-space: nowrap;
  pointer-events: none;
}
</style>
<style lang="postcss">
.bksec-var-popover.bk-pop2-content,
.bksec-var-popover .bk-pop2-content {
  padding: var(--audit-space-4) 0;
}

.bksec-field-value-tip {
  max-width: 400px !important;
  line-height: 20px;
  white-space: normal;
  word-break: break-all;
}

.bksec-risk-type-popover .bk-select-content-wrapper {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
}

.bksec-risk-type-popover .bk-select-search-wrapper {
  grid-column: 1;
  grid-row: 1;
}

.bksec-risk-type-popover .bk-select-content,
.bksec-risk-type-popover .bk-select-empty {
  grid-column: 1;
  grid-row: 2;
}

.bksec-risk-type-popover .bk-select-empty {
  z-index: 2;
  height: auto;
  min-height: 56px;
  background: var(--audit-neutral-bg-04);
  align-self: stretch;
}
</style>
