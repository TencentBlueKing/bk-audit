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
  <teleport
    v-if="isShow"
    to="#sec-chat-overlay-root">
    <div class="log-statistics-overlay">
      <div
        class="log-statistics-dialog-sizer"
        @click.self="handleOverlayClose">
        <div
          class="log-statistics-modal"
          :class="{ 'is-expanded': customExpanded }">
          <div
            class="modal-close"
            @click="handleClose">
            <audit-icon type="close" />
          </div>
          <div class="modal-header">
            <h4 class="modal-title">
              {{ t('数据统计') }}
            </h4>
          </div>

          <div class="modal-body">
            <div class="field-section">
              <p class="subtitle">
                {{ t('请选择需要统计的字段') }}
              </p>

              <template v-if="fieldLoading">
                <div
                  class="field-placeholder"
                  data-testid="statistics-field-loading">
                  <audit-icon
                    class="placeholder-loading"
                    type="loading" />
                  {{ t('字段加载中') }}
                </div>
              </template>
              <div
                v-else-if="fieldError"
                class="field-placeholder"
                data-testid="statistics-field-error">
                <span>{{ fieldError }}</span>
                <bk-button
                  text
                  theme="primary"
                  @click="handleReloadFields">
                  {{ t('重新加载') }}
                </bk-button>
              </div>
              <template v-else>
                <bk-select
                  v-if="filteredGroups.length"
                  v-model="selectedFieldKey"
                  allow-create
                  class="field-select"
                  data-testid="statistics-field-select"
                  :disabled="submitting"
                  filterable
                  :input-search="false"
                  :no-match-text="t('未找到匹配字段')"
                  :placeholder="t('请选择字段或输入自定义字段，自定义字段格式为 extend_data.a.b.c，Enter 后直接统计')"
                  :scroll-height="320"
                  :search-placeholder="t('搜索字段名称')"
                  @change="handleFieldChange">
                  <bk-option-group
                    v-for="group in filteredGroups"
                    :key="group.key"
                    collapsible
                    :label="group.label">
                    <template v-if="group.loading">
                      <bk-option
                        :id="`${group.key}-loading`"
                        disabled
                        :name="t('字段加载中')" />
                    </template>
                    <template v-else-if="group.error">
                      <bk-option
                        :id="`${group.key}-error`"
                        disabled
                        :name="group.error" />
                    </template>
                    <template v-else-if="group.fields.length">
                      <bk-option
                        v-for="field in group.fields"
                        :id="field.key"
                        :key="field.key"
                        :disabled="!field.statisticsSupported"
                        :name="field.label">
                        <show-tooltips-text
                          class="field-option-label"
                          :data="field.label"
                          :max-width="360"
                          :tip="field.tip"
                          tooltip-content-class="show-tooltips-text-popup"
                          tooltip-max-height="240px" />
                      </bk-option>
                    </template>
                    <template v-else>
                      <bk-option
                        :id="`${group.key}-empty`"
                        disabled
                        :name="t('本次样本未发现子字段')" />
                    </template>
                  </bk-option-group>
                </bk-select>
                <div
                  v-else
                  class="field-placeholder"
                  data-testid="statistics-field-empty">
                  {{ t('当前层级没有可统计字段') }}
                </div>
                <p
                  v-if="fieldTruncated"
                  class="field-hint">
                  {{ t('采样可能未覆盖全部子字段，可以通过自定义字段方式使用。') }}
                </p>
              </template>
              <p
                v-if="submitError"
                class="field-hint is-error"
                data-testid="statistics-submit-error">
                {{ submitError }}
              </p>

              <!-- 平铺字段列表暂时停用，先保留
              <div
                v-if="fieldPath.length"
                class="field-breadcrumb">
                <button
                  class="crumb-item"
                  type="button"
                  @click="handleBackToLevel(-1)">
                  {{ t('全部字段') }}
                </button>
                <template
                  v-for="(crumb, index) in fieldPath"
                  :key="crumb.key">
                  <audit-icon
                    class="crumb-split"
                    type="right" />
                  <button
                    class="crumb-item"
                    :class="{ 'is-current': index === fieldPath.length - 1 }"
                    type="button"
                    @click="handleBackToLevel(index)">
                    {{ crumb.label }}
                  </button>
                </template>
              </div>

              <label class="search-wrap">
                <input
                  v-model="keyword"
                  class="search-input"
                  :placeholder="t('搜索字段名称')"
                  type="text">
                <audit-icon
                  class="search-icon"
                  type="search1" />
              </label>

              <div
                class="field-groups"
                data-testid="statistics-field-list">
                <div
                  v-if="fieldLoading"
                  class="field-placeholder"
                  data-testid="statistics-field-loading">
                  <audit-icon
                    class="placeholder-loading"
                    type="loading" />
                  {{ t('字段加载中') }}
                </div>
                <div
                  v-else-if="fieldError"
                  class="field-placeholder"
                  data-testid="statistics-field-error">
                  <span>{{ fieldError }}</span>
                  <bk-button
                    text
                    theme="primary"
                    @click="handleReloadFields">
                    {{ t('重新加载') }}
                  </bk-button>
                </div>
                <template v-else-if="filteredGroups.length">
                  <div
                    v-for="group in filteredGroups"
                    :key="group.key"
                    class="field-group">
                    <div class="group-title">
                      {{ group.label }}
                      <template v-if="!group.loading">
                        ({{ group.fields.length }})
                      </template>
                    </div>
                    <div
                      v-if="group.loading"
                      class="group-tip">
                      <audit-icon
                        class="placeholder-loading"
                        type="loading" />
                      {{ t('字段加载中') }}
                    </div>
                    <div
                      v-else-if="group.error"
                      class="group-tip">
                      {{ group.error }}
                    </div>
                    <div
                      v-else
                      class="field-grid">
                      <div
                        v-for="field in group.fields"
                        :key="field.key"
                        v-bk-tooltips="{
                          content: field.tip,
                          disabled: !field.tip,
                        }"
                        class="field-item">
                        <button
                          class="field-pill"
                          :disabled="submitting || !field.statisticsSupported"
                          type="button"
                          @click="handleSelectField(field)">
                          {{ field.label }}
                        </button>
                        <button
                          v-if="field.isExpandable"
                          class="field-expand"
                          :disabled="submitting"
                          type="button"
                          @click="handleExpandField(field)">
                          <audit-icon type="right" />
                        </button>
                      </div>
                    </div>
                  </div>
                  <p
                    v-if="fieldTruncated"
                    class="field-hint">
                    {{ t('字段较多，仅返回部分结果，可用搜索缩小范围') }}
                  </p>
                </template>
                <div
                  v-else
                  class="field-placeholder"
                  data-testid="statistics-field-empty">
                  {{ keyword.trim() ? t('暂无匹配字段') : t('当前层级没有可统计字段') }}
                </div>
              </div>
              -->
            </div>

            <div class="custom-block">
              <div class="divider-wrapper">
                <div class="divider-line" />
                <div class="divider-text">
                  {{ t('以上字段统计不满足要求？') }}
                </div>
                <div class="divider-line" />
              </div>

              <div class="custom-section">
                <div
                  class="custom-header"
                  @click="customExpanded = !customExpanded">
                  <audit-icon
                    class="collapse-icon"
                    :type="customExpanded ? 'angle-fill-down' : 'angle-fill-rignt'" />
                  <span class="custom-title">{{ t('自定义统计') }}</span>
                  <span class="custom-desc">{{ t('（输入任意内容，AI为您定制报告）') }}</span>
                </div>
                <div
                  v-show="customExpanded"
                  class="custom-content">
                  <div class="custom-input-wrapper">
                    <bk-input
                      v-model="customPrompt"
                      class="custom-input"
                      data-testid="statistics-instruction-input"
                      :maxlength="INSTRUCTION_MAX_LENGTH"
                      :placeholder="t('输入你想统计的内容，例如：分析张三在英雄联盟业务的资产转移报告')"
                      :resize="false"
                      :rows="3"
                      type="textarea" />
                    <bk-button
                      class="custom-confirm-btn"
                      data-testid="statistics-custom-confirm"
                      :disabled="submitting"
                      :loading="submitting"
                      size="small"
                      theme="primary"
                      @click.stop="handleCustomConfirm">
                      {{ t('确认统计') }}
                    </bk-button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script lang="ts" setup>
  import { computed, onDeactivated, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import EsQueryService from '@service/es-query';

  import type {
    AiLogFieldRef,
    AiSearchCondition,
  } from '@model/ai-assistant/types';
  import type { LogFieldMetadataItem } from '@model/es-query/log-field-metadata';

  import ShowTooltipsText from '@components/show-tooltips-text/index.vue';

  import useMessage from '@hooks/use-message';

  import {
    collectDescendantFields,
    descendantFieldMetadataParams,
    fieldOptionLabel,
    rootFieldMetadataParams,
    unsupportedFieldDataType,
  } from '../utils/field-metadata-catalog';

  export interface StatisticsSelectPayload {
    type: 'field' | 'custom';
    field?: AiLogFieldRef;
    fieldLabel?: string;
    prompt?: string;
  }

  interface FieldViewItem {
    key: string;
    label: string;
    category: string;
    field: AiLogFieldRef;
    statisticsSupported: boolean;
    isExpandable: boolean;
    tip: string;
    searchText: string;
  }

  interface FieldGroupView {
    key: string;
    label: string;
    fields: FieldViewItem[];
    loading: boolean;
    error: string;
    /** 该组后代来自有限样本，目录可能不全 */
    truncated?: boolean;
  }

  const props = withDefaults(defineProps<{
    modelValue?: boolean;
    /** 来源检索条件；缺失时无法获取字段目录，也不允许创建 */
    condition?: AiSearchCondition | null;
    submitting?: boolean;
    /** 创建校验失败时留在面板上的原因 */
    submitError?: string;
  }>(), {
    modelValue: false,
    condition: null,
    submitting: false,
    submitError: '',
  });

  const emit = defineEmits<{
    'update:modelValue': [value: boolean];
    select: [payload: StatisticsSelectPayload];
  }>();

  const { t } = useI18n();
  const { messageWarn } = useMessage();

  /** 与后端 BKAPP_AI_ASSISTANT_AI_STATISTICS_INSTRUCTION_MAX_LENGTH 默认值一致 */
  const INSTRUCTION_MAX_LENGTH = 2048;

  const keyword = ref('');
  const selectedFieldKey = ref('');
  const customExpanded = ref(false);
  const customPrompt = ref('');
  const fieldLoading = ref(false);
  const fieldError = ref('');
  const fieldTruncated = ref(false);
  const fieldItems = ref<FieldViewItem[]>([]);
  /** 根层自动展开出来的拓展字段分组，各自独立 loading */
  const extendGroups = ref<FieldGroupView[]>([]);
  const fieldPath = ref<Array<{ key: string; label: string; field: AiLogFieldRef }>>([]);
  /** 切层或重载时丢弃上一层目录的迟到回包 */
  let fieldRequestToken = 0;

  /** 每个可展开根字段各采样一次，限并发避免一次性打满后端 */
  const AUTO_EXPAND_CONCURRENCY = 3;

  const isShow = computed({
    get: () => props.modelValue,
    set: (val: boolean) => emit('update:modelValue', val),
  });

  const matchKeyword = (item: FieldViewItem) => {
    const key = keyword.value.trim().toLowerCase();
    if (!key) return true;
    return item.searchText.includes(key);
  };

  /**
   * 后端同一次请求里的 category 是同质的（根层全 BASIC，展开后全 EXTENDED），
   * 所以分组不靠 category，而是靠「根层 + 自动展开出来的子层」拼出来。
   */
  const filteredGroups = computed<FieldGroupView[]>(() => {
    if (fieldPath.value.length) {
      const current = fieldPath.value[fieldPath.value.length - 1];
      return [{
        key: 'current',
        label: current.label,
        fields: fieldItems.value.filter(matchKeyword),
        loading: false,
        error: '',
      }].filter(group => group.fields.length);
    }
    // 已经单独成组的 JSON 根字段本身不可统计，再放进通用字段只会多出一个点不动的项
    const expandedKeys = new Set(extendGroups.value.map(group => group.key));
    const groups: FieldGroupView[] = [{
      key: 'basic',
      label: t('通用字段'),
      fields: fieldItems.value
        .filter(item => item.statisticsSupported || !expandedKeys.has(item.key))
        .filter(matchKeyword),
      loading: false,
      error: '',
    }];
    extendGroups.value.forEach((group) => {
      groups.push({ ...group, fields: group.fields.filter(matchKeyword) });
    });
    return groups.filter(group => group.fields.length || group.loading || group.error || group.truncated);
  });

  const resolveFieldKey = (field: AiLogFieldRef) => (
    [field.raw_name, ...(field.keys || [])].join('\u0000')
  );

  /** 可展开不等于可统计：JSON 根字段要先展开到子路径 */
  const resolveTip = (item: LogFieldMetadataItem, label: string) => {
    if (!item.statistics_supported) {
      if (item.is_expandable) return t('该字段需展开到子字段后统计');
      const dataType = unsupportedFieldDataType(item.field?.field_type, item.observed_types);
      return dataType
        ? t('该字段数据类型为 {type}，不支持统计', { type: dataType })
        : t('该字段不支持统计');
    }
    const path = [item.field?.raw_name, ...(item.field?.keys || [])].filter(Boolean).join('.');
    return path === label ? item.description || '' : [path, item.description].filter(Boolean).join(' · ');
  };

  const toFieldViewItem = (item: LogFieldMetadataItem): FieldViewItem => {
    const field: AiLogFieldRef = {
      raw_name: item.field?.raw_name || '',
      keys: item.field?.keys || [],
      ...(item.field?.field_type ? { field_type: item.field.field_type } : {}),
    };
    const label = fieldOptionLabel(item.display_name || '', field.raw_name, field.keys);
    return {
      key: resolveFieldKey(field),
      label,
      category: String(item.category || ''),
      field,
      statisticsSupported: Boolean(item.statistics_supported),
      isExpandable: Boolean(item.is_expandable),
      tip: resolveTip(item, label),
      searchText: `${label} ${field.raw_name} ${field.keys.join('.')}`.toLowerCase(),
    };
  };

  const patchExtendGroup = (key: string, patch: Partial<FieldGroupView>) => {
    extendGroups.value = extendGroups.value.map(group => (
      group.key === key ? { ...group, ...patch } : group
    ));
  };

  const runWithConcurrency = async (tasks: Array<() => Promise<void>>, limit: number) => {
    let cursor = 0;
    const workers = Array.from({ length: Math.min(limit, tasks.length) }, async () => {
      while (cursor < tasks.length) {
        const index = cursor;
        cursor += 1;
        await tasks[index]();
      }
    });
    await Promise.all(workers);
  };

  /**
   * 每个可展开根字段单独采样一次，include_descendants 带回全部对象后代。
   * 数组不是可展开对象，不会再请求。失败只影响该组。
   */
  const autoExpandRootFields = async (items: FieldViewItem[], token: number) => {
    const expandable = items.filter(item => item.isExpandable);
    if (!expandable.length) return;
    extendGroups.value = expandable.map(item => ({
      key: item.key,
      label: item.label,
      fields: [],
      loading: true,
      error: '',
      truncated: false,
    }));
    await runWithConcurrency(expandable.map(item => async () => {
      if (token !== fieldRequestToken) return;
      try {
        const result = await EsQueryService.fetchLogFieldMetadata(
          descendantFieldMetadataParams(props.condition as AiSearchCondition, item.field),
          { catchError: true },
        );
        if (token !== fieldRequestToken) return;
        const truncated = Boolean(result.sample_summary?.truncated);
        if (truncated) fieldTruncated.value = true;
        const fields = collectDescendantFields(
          (result.fields || []).map(toFieldViewItem),
          item.key,
        );
        patchExtendGroup(item.key, {
          label: truncated ? `${item.label}${t('（样本发现）')}` : item.label,
          fields,
          loading: false,
          truncated,
        });
      } catch (error: any) {
        if (token !== fieldRequestToken) return;
        patchExtendGroup(item.key, {
          loading: false,
          error: error?.message || t('字段加载失败'),
        });
      }
    }), AUTO_EXPAND_CONCURRENCY);
  };

  const loadFields = async () => {
    if (!props.condition) {
      fieldItems.value = [];
      fieldTruncated.value = false;
      fieldError.value = t('缺少检索条件，无法获取字段');
      return;
    }
    fieldRequestToken += 1;
    const token = fieldRequestToken;
    fieldLoading.value = true;
    fieldError.value = '';
    extendGroups.value = [];
    try {
      const result = await EsQueryService.fetchLogFieldMetadata(
        rootFieldMetadataParams(props.condition),
        { catchError: true },
      );
      if (token !== fieldRequestToken) return;
      const items = (result.fields || []).map(toFieldViewItem);
      fieldItems.value = items;
      fieldTruncated.value = Boolean(result.sample_summary?.truncated);
      void autoExpandRootFields(items, token);
    } catch (error: any) {
      if (token !== fieldRequestToken) return;
      fieldItems.value = [];
      fieldTruncated.value = false;
      fieldError.value = error?.message || t('字段加载失败');
    } finally {
      if (token === fieldRequestToken) fieldLoading.value = false;
    }
  };

  const resetState = () => {
    keyword.value = '';
    selectedFieldKey.value = '';
    customExpanded.value = false;
    customPrompt.value = '';
    fieldPath.value = [];
    fieldItems.value = [];
    extendGroups.value = [];
    fieldTruncated.value = false;
    fieldError.value = '';
  };

  // 外层用 v-if 挂载，创建时 modelValue 已是 true，必须 immediate，否则首次打开不拉字段
  watch(() => props.modelValue, (val) => {
    if (!val || props.submitting) return;
    resetState();
    void loadFields();
  }, { immediate: true });

  const handleClose = () => {
    if (props.submitting) return;
    isShow.value = false;
  };

  const handleOverlayClose = () => {
    handleClose();
  };

  onDeactivated(() => {
    isShow.value = false;
    resetState();
  });

  const fieldPathText = (field: AiLogFieldRef) => (
    [field.raw_name, ...(field.keys || [])].filter(Boolean).join('.')
  );

  const catalogFields = () => [
    ...fieldItems.value,
    ...extendGroups.value.flatMap(group => group.fields),
  ];

  const findCatalogField = (text: string) => {
    const normalized = text.trim().toLowerCase();
    return catalogFields().find((item) => {
      const path = fieldPathText(item.field).toLowerCase();
      return item.label.toLowerCase() === normalized || path === normalized;
    });
  };

  const handleFieldChange = (key: string) => {
    if (!key || props.submitting || key.endsWith('-loading') || key.endsWith('-error') || key.endsWith('-empty')) return;
    const item = catalogFields().find(field => field.key === key);
    if (item) {
      if (!item.statisticsSupported) {
        messageWarn(item.tip || t('该字段不支持统计'));
        selectedFieldKey.value = '';
        return;
      }
      handleSelectField(item);
      return;
    }
    // allow-create 把外层输入框的回车值原样抛出来，目录里没有就按自定义字段统计
    handleSearchEnter(key);
  };

  const parseCustomField = (text: string): AiLogFieldRef | null => {
    const parts = text.split('.')
      .map(part => part.trim())
      .filter(Boolean);
    if (!parts.length) return null;
    const [rawName, ...keys] = parts;
    return { raw_name: rawName, keys };
  };

  const handleSearchEnter = (value?: string) => {
    const text = String(value ?? keyword.value).trim();
    if (!text || props.submitting) return;
    const matched = findCatalogField(text);
    if (matched) {
      if (!matched.statisticsSupported) {
        messageWarn(matched.tip || t('该字段不支持统计'));
        return;
      }
      handleSelectField(matched);
      return;
    }
    const field = parseCustomField(text);
    if (!field) {
      messageWarn(t('请输入字段名'));
      return;
    }
    emit('select', {
      type: 'field',
      field,
      fieldLabel: text,
    });
  };

  const handleSelectField = (item: FieldViewItem) => {
    if (props.submitting || !item.statisticsSupported) return;
    emit('select', {
      type: 'field',
      field: item.field,
      fieldLabel: item.label,
    });
  };

  const handleExpandField = (item: FieldViewItem) => {
    if (props.submitting) return;
    keyword.value = '';
    fieldPath.value = [...fieldPath.value, {
      key: item.key,
      label: item.label,
      field: item.field,
    }];
    void loadFields();
  };

  /** index 为 -1 回到根层；点当前层不重复请求 */
  const handleBackToLevel = (index: number) => {
    if (index === fieldPath.value.length - 1) return;
    keyword.value = '';
    fieldPath.value = index < 0 ? [] : fieldPath.value.slice(0, index + 1);
    void loadFields();
  };

  const handleReloadFields = () => {
    void loadFields();
  };

  const handleCustomConfirm = () => {
    if (props.submitting) return;
    const prompt = customPrompt.value.trim();
    if (!prompt) {
      messageWarn(t('请输入统计要求'));
      return;
    }
    emit('select', {
      type: 'custom',
      prompt,
    });
  };

  // 平铺列表已注释，展开和面包屑回退先留着，恢复界面时删掉这两行
  void handleExpandField;
  void handleBackToLevel;
</script>

<style lang="postcss" scoped>
  .log-statistics-overlay {
    position: absolute;
    inset: 0;
    z-index: 100;
    overflow: auto;
    pointer-events: auto;
    background: rgb(0 0 0 / 40%);
    box-sizing: border-box;
  }

  .log-statistics-dialog-sizer {
    display: flex;
    width: max-content;
    min-width: 100%;
    min-height: 100%;
    padding: var(--audit-space-24);
    box-sizing: border-box;
    align-items: center;
    justify-content: center;
  }

  .log-statistics-modal {
    position: relative;
    display: flex;
    width: 640px;
    height: auto;
    max-height: calc(100% - 48px);
    min-width: 640px;
    padding: var(--audit-space-16) var(--audit-space-24) var(--audit-space-24);
    margin: auto;
    overflow: hidden;
    background: var(--audit-neutral-bg-04);
    border-radius: var(--audit-radius-container);
    box-shadow: var(--audit-shadow-dialog);
    flex-direction: column;
    flex-shrink: 0;
    gap: 20px;
    box-sizing: border-box;

    &.is-expanded {
      height: auto;
    }
  }

  .modal-header {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    box-sizing: border-box;

    .modal-title {
      margin: 0;
      font-size: var(--audit-font-size-xl);
      font-weight: var(--audit-font-weight-regular);
      line-height: var(--audit-line-height-xl);
      color: var(--audit-neutral-text-01);
    }
  }

  .modal-close {
    position: absolute;
    top: var(--audit-space-8);
    right: var(--audit-space-8);
    z-index: 1;
    display: flex;
    width: 24px;
    height: 24px;
    font-size: var(--audit-font-size-base);
    color: var(--audit-neutral-text-03);
    cursor: pointer;
    border-radius: var(--audit-radius-control);
    align-items: center;
    justify-content: center;

    &:hover {
      color: var(--audit-neutral-text-02);
      background: var(--audit-neutral-border-02);
    }
  }

  .modal-body {
    display: flex;
    min-height: 0;
    overflow: hidden;
    flex-direction: column;
    flex: 1;
    gap: var(--audit-space-24);
  }

  .field-section {
    display: flex;
    min-height: 0;
    flex-direction: column;
    flex-shrink: 0;
    gap: var(--audit-space-8);
  }

  .field-select {
    width: 100%;
  }

  .field-option-label {
    width: 100%;
    min-width: 0;
  }

  .subtitle {
    margin: 0;
    font-size: var(--audit-font-size-sm);
    font-weight: var(--audit-font-weight-regular);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-02);
    flex-shrink: 0;
  }

  .field-breadcrumb {
    display: flex;
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-03);
    flex-wrap: wrap;
    flex-shrink: 0;
    align-items: center;
    gap: var(--audit-space-4);

    .crumb-item {
      padding: 0;
      font-size: var(--audit-font-size-sm);
      color: var(--audit-brand-02);
      cursor: pointer;
      background: transparent;
      border: none;

      &.is-current {
        color: var(--audit-neutral-text-02);
        cursor: default;
      }
    }

    .crumb-split {
      font-size: var(--audit-font-size-sm);
      color: var(--audit-neutral-text-04);
    }
  }

  .search-wrap {
    display: flex;
    width: 100%;
    height: 32px;
    padding: 6px 8px;
    background: var(--audit-neutral-bg-04);
    border: 1px solid var(--audit-neutral-text-04);
    border-radius: var(--audit-radius-control);
    box-sizing: border-box;
    flex-shrink: 0;
    align-items: center;
    justify-content: space-between;
    gap: var(--audit-space-8);

    &:hover {
      border-color: var(--audit-neutral-text-03);
    }

    &:focus-within {
      border-color: var(--audit-brand-02);
    }

    .search-input {
      width: 100%;
      height: 20px;
      min-width: 0;
      padding: 0;
      font-size: var(--audit-font-size-sm);
      font-weight: var(--audit-font-weight-regular);
      line-height: var(--audit-line-height-sm);
      color: var(--audit-neutral-text-01);
      background: transparent;
      border: 0;
      outline: none;
      box-shadow: none;
      flex: 1;

      &::placeholder {
        color: var(--audit-neutral-text-04);
      }
    }

    .search-icon {
      display: flex;
      width: 16px;
      height: 16px;
      font-size: 16px;
      color: var(--audit-neutral-text-04);
      flex-shrink: 0;
      align-items: center;
      justify-content: center;
    }
  }

  .field-groups {
    display: flex;
    width: 100%;
    height: 456px;
    min-height: 0;
    overflow: auto;
    flex-direction: column;
    flex-shrink: 1;
    gap: var(--audit-space-16);
    scrollbar-width: thin;
    scrollbar-color: var(--audit-neutral-border-01) transparent;

    &::-webkit-scrollbar {
      width: 6px;
    }

    &::-webkit-scrollbar-thumb {
      background: var(--audit-neutral-border-01);
      border-radius: 99px;
    }

    &::-webkit-scrollbar-track {
      background: transparent;
    }
  }

  .field-group {
    .group-title {
      margin-bottom: var(--audit-space-8);
      font-size: var(--audit-font-size-sm);
      font-weight: var(--audit-font-weight-regular);
      line-height: var(--audit-line-height-sm);
      color: var(--audit-neutral-text-03);
    }
  }

  .group-tip {
    display: flex;
    padding: var(--audit-space-8) 0;
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-04);
    align-items: center;
    gap: var(--audit-space-8);
  }

  .field-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--audit-space-8);
  }

  .field-item {
    display: flex;
    min-width: 0;
    align-items: center;
    gap: var(--audit-space-4);
  }

  .field-pill {
    height: 32px;
    padding: 0 12px;
    overflow: hidden;
    font-size: var(--audit-font-size-sm);
    font-weight: var(--audit-font-weight-regular);
    line-height: 30px;
    color: var(--audit-neutral-text-02);
    text-align: left;
    text-overflow: ellipsis;
    white-space: nowrap;
    cursor: pointer;
    background: var(--audit-neutral-bg-03);
    border: 1px solid var(--audit-neutral-bg-01);
    border-radius: var(--audit-radius-container);
    box-sizing: border-box;
    flex: 1;

    &:hover:not(:disabled) {
      border-color: var(--audit-brand-02);
    }

    &:active:not(:disabled) {
      color: var(--audit-brand-02);
      background: var(--audit-brand-06);
      border-color: var(--audit-brand-02);
    }

    &:disabled {
      cursor: not-allowed;
      opacity: 60%;
    }
  }

  .field-expand {
    display: flex;
    width: 24px;
    height: 32px;
    font-size: var(--audit-font-size-sm);
    color: var(--audit-neutral-text-03);
    cursor: pointer;
    background: transparent;
    border: none;
    flex-shrink: 0;
    align-items: center;
    justify-content: center;

    &:hover:not(:disabled) {
      color: var(--audit-brand-02);
    }

    &:disabled {
      cursor: not-allowed;
    }
  }

  .field-placeholder {
    display: flex;
    padding: var(--audit-space-40) 0;
    font-size: var(--audit-font-size-sm);
    color: var(--audit-neutral-text-04);
    align-items: center;
    justify-content: center;
    gap: var(--audit-space-8);

    .placeholder-loading {
      animation: statistics-field-rotate 1s linear infinite;
    }
  }

  @keyframes statistics-field-rotate {
    from {
      transform: rotate(0deg);
    }

    to {
      transform: rotate(360deg);
    }
  }

  .field-hint {
    margin: 0;
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-04);

    &.is-error {
      color: var(--audit-danger-02);
    }
  }

  .divider-wrapper {
    display: flex;
    height: 20px;
    margin: 0;
    flex-shrink: 0;
    align-items: center;

    .divider-line {
      height: 1px;
      background: var(--audit-neutral-border-01);
      flex: 1;
    }

    .divider-text {
      padding: 0 var(--audit-space-16);
      font-size: var(--audit-font-size-sm);
      line-height: var(--audit-line-height-sm);
      color: var(--audit-neutral-text-02);
      white-space: nowrap;
    }
  }

  .custom-block {
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
    gap: var(--audit-space-16);
  }

  .custom-section {
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
    gap: var(--audit-space-12);

    .custom-header {
      display: flex;
      min-width: 0;
      cursor: pointer;
      user-select: none;
      align-items: center;
      gap: var(--audit-space-8);

      .collapse-icon {
        display: inline-flex;
        width: 12px;
        height: 12px;
        font-size: 12px;
        line-height: 12px;
        color: var(--audit-neutral-text-03);
        flex-shrink: 0;
        align-items: center;
        justify-content: center;
      }

      .custom-title {
        font-size: var(--audit-font-size-base);
        font-weight: var(--audit-font-weight-bold);
        line-height: var(--audit-line-height-base);
        color: var(--audit-neutral-text-02);
        white-space: nowrap;
        flex-shrink: 0;
      }

      .custom-desc {
        min-width: 0;
        font-size: var(--audit-font-size-sm);
        line-height: var(--audit-line-height-sm);
        color: var(--audit-neutral-text-03);
        white-space: nowrap;
      }
    }

    .custom-content {
      width: 100%;
    }

    .custom-input-wrapper {
      position: relative;
      display: flex;
      width: 100%;
      height: 72px;
      background: linear-gradient(white, white) padding-box,
        linear-gradient(90deg, #a469ff 0%, #1cc2fe 100%) border-box;
      border: 1px solid transparent;
      border-radius: var(--audit-radius-control);
      box-sizing: border-box;
      transition: all .2s;
      align-items: flex-end;

      .custom-input {
        height: 100%;
        background: transparent;
        border: none;
        box-shadow: none;
        flex: 1;

        :deep(.bk-textarea) {
          height: 100%;
          min-height: 0;
          padding: 4px 88px 32px 8px;
          background: transparent;
          border: none;
          box-sizing: border-box;
          resize: none !important;
        }

        :deep(textarea) {
          resize: none !important;
        }

        /* textarea 设了 maxlength 就强制渲染字数统计，show-word-limit 关不掉，只能隐藏；
           textarea 用的是 bk-textarea-- 前缀，和 input 的不是同一个类名 */
        :deep(.bk-textarea--max-length),
        :deep(.bk-input--max-length) {
          display: none;
        }
      }

      .custom-confirm-btn {
        position: absolute;
        right: 8px;
        bottom: 8px;
        height: 26px;
        min-width: 64px;
        padding: 3px 12px;
      }
    }
  }
</style>
