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
  <bk-select
    v-if="config.custom_type === 'select'"
    v-model="selectTypeValue"
    :allow-empty-values="[ '0', 0]"
    class="bk-select"
    filterable
    :placeholder="t('请选择已有选项')"
    @change="handlerSelectChange">
    <bk-option
      v-for="(item, index) in JSON.parse(config.value.items_text)"
      :id="item.value"
      :key="index"
      :name="item.text">
      <bk-popover
        placement="left"
        theme="light">
        <div style="width: 100%;height: 100%;">
          {{ item.text }}
        </div>
        <template #content>
          <div>
            <div style="font-size: 12px;font-weight: 700;">
              {{ t('当前值：') }}
            </div>
            <div class="current-value">
              {{ item.value }}
            </div>
          </div>
        </template>
      </bk-popover>
    </bk-option>
  </bk-select>

  <template v-else-if="useFieldInsert && supportsFieldInsert">
    <div
      class="field-insert-wrapper"
      :class="{
        'is-textarea': config.custom_type === 'textarea',
        'has-suffix': canInsertField,
      }">
      <div class="field-insert-wrapper__main">
        <bk-date-picker
          v-if="config.custom_type === 'datetime'"
          v-model="datePickerValue"
          class="field-insert-wrapper__control"
          clearable
          :placeholder="t('请选择日期')"
          type="datetime"
          @change="handleChange" />
        <bk-input
          v-else
          ref="textareaInputRef"
          v-model="unifiedInputValue"
          class="field-insert-wrapper__control"
          :class="{ 'auto-grow-textarea-input': config.custom_type === 'textarea' }"
          clearable
          :placeholder="canInsertField ? t('请输入或选择字段插入') : t('请输入')"
          :resize="false"
          :rows="config.custom_type === 'textarea' ? 1 : undefined"
          :show-overflow-tooltips="config.custom_type !== 'textarea'"
          :type="config.custom_type === 'textarea' ? 'textarea' : 'text'"
          @change="handleTextareaChange"
          @input="adjustTextareaHeight" />
      </div>
      <div
        v-if="canInsertField"
        class="field-insert-wrapper__suffix-host">
        <bk-popover
          :is-show="isFieldInsertOpen"
          placement="bottom-end"
          theme="light"
          trigger="manual"
          width="320"
          @after-hidden="handleFieldInsertHidden">
          <div
            ref="fieldInsertSuffixRef"
            v-bk-tooltips="t('点击插入字段值')"
            class="field-insert-wrapper__suffix"
            :class="{ 'is-active': isFieldInsertOpen }"
            @click.stop="toggleFieldInsert">
            <img
              alt=""
              class="field-insert-wrapper__icon"
              :src="jumpIntoIcon">
          </div>
          <template #content>
            <div
              class="field-insert-panel"
              @click.stop
              @mousedown.stop>
              <div class="field-insert-panel__search">
                <audit-icon
                  class="field-insert-panel__search-icon"
                  type="search1" />
                <input
                  v-model="fieldSearchKeyword"
                  class="field-insert-panel__search-input"
                  :placeholder="t('搜索')"
                  type="text">
              </div>
              <div class="field-insert-panel__list">
                <div
                  v-if="filteredRiskFields.length"
                  class="field-insert-group">
                  <div class="field-insert-group__title">
                    {{ t('风险字段') }} ({{ filteredRiskFields.length }})
                  </div>
                  <div
                    v-for="item in filteredRiskFields"
                    :key="item.id"
                    v-bk-tooltips="getEmptyFieldTooltip(getCurrentValue(item.id))"
                    class="field-insert-item"
                    :class="{ 'is-disabled': isFieldValueEmpty(getCurrentValue(item.id)) }"
                    @click="handleInsertFieldItem(getCurrentValue(item.id))">
                    <span class="field-insert-item__name">{{ item.name }}</span>
                    <span class="field-insert-item__sep"> : </span>
                    <span
                      v-bk-tooltips="getFieldValueTooltip(getCurrentValue(item.id))"
                      class="field-insert-item__value">
                      {{ formatFieldDisplayValue(getCurrentValue(item.id)) }}
                    </span>
                  </div>
                </div>
                <div
                  v-if="filteredEventFields.length"
                  class="field-insert-group">
                  <div class="field-insert-group__title">
                    {{ t('事件字段') }} ({{ filteredEventFields.length }})
                  </div>
                  <div
                    v-for="(item, index) in filteredEventFields"
                    :key="`${item.lable}-${index}`"
                    v-bk-tooltips="getEmptyFieldTooltip(item.value)"
                    class="field-insert-item"
                    :class="{ 'is-disabled': isFieldValueEmpty(item.value) }"
                    @click="handleInsertFieldItem(item.value)">
                    <span class="field-insert-item__name">{{ item.lable }}</span>
                    <span class="field-insert-item__sep"> : </span>
                    <span
                      v-bk-tooltips="getFieldValueTooltip(item.value)"
                      class="field-insert-item__value">
                      {{ formatFieldDisplayValue(item.value) }}
                    </span>
                  </div>
                </div>
                <div
                  v-if="!filteredRiskFields.length && !filteredEventFields.length"
                  class="field-insert-panel__empty">
                  {{ t('暂无数据') }}
                </div>
              </div>
            </div>
          </template>
        </bk-popover>
      </div>
    </div>
  </template>

  <div v-else>
    <div v-if="config.custom_type === 'datetime' && config.type === 'self'">
      <bk-date-picker
        v-if="config.custom_type === 'datetime' && config.type === 'self'"
        v-model="datePickerValue"
        clearable
        :placeholder="t('请选择日期')"
        type="datetime"
        @change="handleChange" />
    </div>
    <div v-else>
      <bk-select
        v-if="config.type === 'field'"
        v-model="selectValue"
        class="bk-select"
        filterable
        :placeholder="t('请选择已有选项')"
        @change="handlerChange">
        <bk-option-group
          v-if="riskFieldList.length > 0"
          collapsible
          :label="t('风险字段')">
          <bk-option
            v-for="(item, index) in riskFieldList"
            :id="item.id"
            :key="index"
            :name="item.name">
            <bk-popover
              max-width="800px"
              placement="left"
              theme="light">
              <div style="width: 100%;height: 100%;">
                {{ item.name }}
              </div>
              <template #content>
                <div v-if="isCurrentValue">
                  <div style="font-size: 12px;font-weight: 700;">
                    {{ t('参考值：') }}
                  </div>
                  <div class="current-value">
                    {{ getCurrentValue(item.id) }}
                  </div>
                </div>
              </template>
            </bk-popover>
          </bk-option>
        </bk-option-group>

        <bk-option-group
          v-if="eventDataList.length > 0"
          collapsible
          :label="t('事件字段')">
          <bk-option
            v-for="(item, index) in eventDataList"
            :id="item.lable"
            :key="index"
            :name="item.lable">
            <bk-popover
              placement="left"
              theme="light">
              <div style="width: 100%;height: 100%;">
                {{ item.lable }}
              </div>
              <template #content>
                <div v-if="isCurrentValue">
                  <div style="font-size: 12px;font-weight: 700;">
                    {{ t('参考值：') }}
                  </div>
                  <div class="current-value">
                    {{ item.value }}
                  </div>
                </div>
              </template>
            </bk-popover>
          </bk-option>
        </bk-option-group>
      </bk-select>
      <div v-else>
        <audit-user-selector-tenant
          v-if="config.custom_type === 'bk_user_selector'"
          allow-create
          class="consition-value pa-user-selector"
          :model-value="userSelectorValue"
          :placeholder="t('请输入人员进行搜索')"
          @update:model-value="handlerUserChange" />

        <div
          v-else
          class="auto-grow-textarea">
          <bk-input
            ref="generalTextareaRef"
            v-model="generalValue"
            class="auto-grow-textarea-input"
            clearable
            :resize="false"
            :rows="config.custom_type === 'textarea' ? 1 : undefined"
            show-overflow-tooltips
            show-word-limit
            :type="config.custom_type === 'textarea' ? 'textarea': 'text'"
            @change="handleTextareaChange"
            @input="adjustTextareaHeight" />
        </div>
      </div>
    </div>
  </div>

  <div
    v-if="!useFieldInsert
      && localValue
      && (Array.isArray(localValue) ? localValue.length > 0 : localValue !== '')
      && config.custom_type !== 'select'
      && isShowtip
      && isCurrentValue"
    class="item-value">
    <div>
      {{ t('当前值：') }}
    </div>
    <tool-tip-text
      :data="tipText"
      :line="2"
      :max-width="800"
      placement="left"
      theme="light" />
  </div>
</template>
<script setup lang="ts">
  import {
    computed,
    nextTick,
    onBeforeUnmount,
    onMounted,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import jumpIntoIcon from '@images/jump-into.svg';

  import ToolTipText from '@/components/show-tooltips-text/index.vue';

  interface Props {
    riskFieldList: Array<{
      id: string,
      name: string,
    }>
    isCurrentValue?: boolean,
    config?: any,
    eventDataList?: any,
    detailData: any,
    useFieldInsert?: boolean,
  }

  const props = withDefaults(defineProps<Props>(), {
    isCurrentValue: true,
    config: () => ({}),
    eventDataList: () => ([]),
    detailData: () => ({}),
    useFieldInsert: false,
  });
  const { t } = useI18n();
  const tipText = ref('');
  const selectValue = ref();
  const selectTypeValue = ref<string | number>('');
  const fieldSearchKeyword = ref('');
  const isFieldInsertOpen = ref(false);
  const fieldInsertSuffixRef = ref<HTMLElement>();
  let fieldInsertIgnoreCloseBefore = 0;
  const textareaInputRef = ref<{ $el: HTMLElement }>();
  const generalTextareaRef = ref<{ $el: HTMLElement }>();
  const TEXTAREA_MIN_HEIGHT = 32;
  const TEXTAREA_MAX_HEIGHT = 200;
  const TEXTAREA_CLEAR_PADDING = 30;
  const VALUE_OVERFLOW_LENGTH = 24;

  const isTextareaType = computed(() => props.config?.custom_type === 'textarea');

  const getTextareaElement = () => {
    const componentRef = props.useFieldInsert
      ? textareaInputRef.value
      : generalTextareaRef.value;
    return componentRef?.$el?.querySelector('textarea') as HTMLTextAreaElement | null;
  };

  let textareaResizeObserver: ResizeObserver | null = null;
  let adjustingTextareaHeight = false;

  const adjustTextareaHeight = () => {
    if (!isTextareaType.value || adjustingTextareaHeight) {
      return;
    }
    adjustingTextareaHeight = true;
    nextTick(() => {
      const textarea = getTextareaElement();
      if (!textarea) {
        adjustingTextareaHeight = false;
        return;
      }
      textarea.style.paddingRight = `${TEXTAREA_CLEAR_PADDING}px`;
      if (!textarea.value) {
        textarea.style.height = `${TEXTAREA_MIN_HEIGHT}px`;
        textarea.style.overflowY = 'hidden';
        adjustingTextareaHeight = false;
        return;
      }
      textarea.style.height = `${TEXTAREA_MIN_HEIGHT}px`;
      const { scrollHeight } = textarea;
      const nextHeight = Math.min(
        Math.max(scrollHeight, TEXTAREA_MIN_HEIGHT),
        TEXTAREA_MAX_HEIGHT,
      );
      textarea.style.height = `${nextHeight}px`;
      textarea.style.overflowY = scrollHeight > TEXTAREA_MAX_HEIGHT ? 'auto' : 'hidden';
      adjustingTextareaHeight = false;
    });
  };

  const setupTextareaResizeObserver = () => {
    textareaResizeObserver?.disconnect();
    textareaResizeObserver = null;

    if (!isTextareaType.value) {
      return;
    }

    nextTick(() => {
      const textarea = getTextareaElement();
      if (!textarea) {
        return;
      }
      textareaResizeObserver = new ResizeObserver(() => {
        adjustTextareaHeight();
      });
      textareaResizeObserver.observe(textarea);
      adjustTextareaHeight();
    });
  };

  const supportsFieldInsert = computed(() => {
    const type = props.config?.custom_type;
    return type === 'datetime'
      || type === 'textarea'
      || type === 'input'
      || type === 'bk_date_picker'
      || type === '';
  });

  const canInsertField = computed(() => (
    props.riskFieldList.length > 0 || props.eventDataList.length > 0
  ));

  const formatFieldDisplayValue = (value: unknown) => {
    if (value === undefined || value === null || value === '') {
      return '--';
    }
    if (Array.isArray(value)) {
      return value.join(', ');
    }
    if (typeof value === 'object') {
      return JSON.stringify(value);
    }
    return String(value);
  };

  const isValueOverflow = (value: unknown) => (
    formatFieldDisplayValue(value).length > VALUE_OVERFLOW_LENGTH
  );

  const isFieldValueEmpty = (value: unknown) => {
    if (value === undefined || value === null || value === '') {
      return true;
    }
    if (Array.isArray(value)) {
      return value.length === 0;
    }
    return false;
  };

  const fieldInsertTooltipMaxWidth = '30vw';
  const fieldInsertTooltipExtCls = 'field-insert-item-tooltips';

  const getEmptyFieldTooltip = (value: unknown) => ({
    content: t('当前值为空'),
    maxWidth: fieldInsertTooltipMaxWidth,
    extCls: fieldInsertTooltipExtCls,
    disabled: !isFieldValueEmpty(value),
  });

  const getFieldValueTooltip = (value: unknown) => ({
    content: formatFieldDisplayValue(value),
    maxWidth: fieldInsertTooltipMaxWidth,
    extCls: fieldInsertTooltipExtCls,
    disabled: isFieldValueEmpty(value) || !isValueOverflow(value),
  });

  const getCurrentValue = (id: string) => props.detailData[id];

  const filteredRiskFields = computed(() => {
    const keyword = fieldSearchKeyword.value.trim().toLowerCase();
    return props.riskFieldList.filter((item) => {
      const value = formatFieldDisplayValue(getCurrentValue(item.id));
      if (!keyword) {
        return true;
      }
      return item.name.toLowerCase().includes(keyword)
        || value.toLowerCase().includes(keyword);
    });
  });

  const filteredEventFields = computed(() => props.eventDataList.filter((item: {
    lable?: string,
    value?: unknown,
  }) => {
    const value = formatFieldDisplayValue(item.value);
    const label = item.lable || '';
    const keyword = fieldSearchKeyword.value.trim().toLowerCase();
    if (!keyword) {
      return true;
    }
    return label.toLowerCase().includes(keyword)
      || value.toLowerCase().includes(keyword);
  }));

  const datePickerValue = computed(() => {
    if (props.config.custom_type === 'datetime'
      && (props.config.type === 'self' || props.useFieldInsert)) {
      const value = modelValue.value.value || modelValue.value.field;
      return value ? String(value) : undefined;
    }
    return undefined;
  });

  const userSelectorValue = computed<string | string[]>(() => {
    if (props.config.custom_type !== 'bk_user_selector') {
      return [];
    }
    const val = modelValue.value.value;
    if (Array.isArray(val)) {
      return val;
    }
    if (val !== undefined && val !== null && val !== '') {
      return String(val);
    }
    return [];
  });

  const unifiedInputValue = computed({
    get() {
      const val = modelValue.value.value;
      if (val !== undefined && val !== null && val !== '') {
        if (Array.isArray(val)) {
          return val.join(', ');
        }
        return String(val);
      }
      if (modelValue.value.field) {
        const fieldVal = getCurrentValue(String(modelValue.value.field));
        const display = formatFieldDisplayValue(fieldVal);
        return display === '--' ? '' : display;
      }
      return '';
    },
    set(val: string) {
      modelValue.value = {
        field: '',
        value: val,
      };
    },
  });

  const generalValue = computed<string | number>(() => {
    const val = modelValue.value.value;
    const value = (val !== undefined && val !== null && val !== '') ? val : modelValue.value.field;
    if (Array.isArray(value)) {
      return value.join(', ');
    }
    if (typeof value === 'number') {
      return value;
    }

    return value ? String(value) : '';
  });

  const localValue = computed(() => {
    if (props.config.custom_type === 'datetime'
      && (props.config.type === 'self' || props.useFieldInsert)) {
      return datePickerValue.value;
    }
    if (props.config.custom_type === 'bk_user_selector') {
      return userSelectorValue.value;
    }
    if (selectValue.value) {
      return selectValue.value;
    }
    if (props.useFieldInsert) {
      return unifiedInputValue.value;
    }
    return generalValue.value;
  });
  const isShowtip = ref(false);
  const modelValue = defineModel<{field: string | number, value: string | number |string[]}>({
    default: () => ({
      field: '',
      value: '',
    }),
  });

  const toggleFieldInsert = () => {
    if (isFieldInsertOpen.value) {
      handleFieldInsertHidden();
      return;
    }
    fieldInsertIgnoreCloseBefore = Date.now() + 500;
    isFieldInsertOpen.value = true;
  };

  const isInFieldInsertPopoverLayer = (target: Node) => {
    const el = target as HTMLElement;
    if (!el?.closest) return false;
    return !!el.closest('.field-insert-panel, .field-insert-wrapper__suffix, .bk-popover.bk-pop2-content, .tippy-box');
  };

  const unbindFieldInsertDocumentMousedown = () => {
    document.removeEventListener('mousedown', handleFieldInsertDocumentMousedown, true);
  };

  const bindFieldInsertDocumentMousedown = () => {
    setTimeout(() => {
      document.addEventListener('mousedown', handleFieldInsertDocumentMousedown, true);
    });
  };

  const handleFieldInsertDocumentMousedown = (e: Event) => {
    if (!isFieldInsertOpen.value) return;
    if (Date.now() < fieldInsertIgnoreCloseBefore) return;
    const target = e.target as HTMLElement;
    if (fieldInsertSuffixRef.value?.contains(target)) return;
    if (isInFieldInsertPopoverLayer(target)) return;
    handleFieldInsertHidden();
  };

  watch(isFieldInsertOpen, (open) => {
    if (open) {
      unbindFieldInsertDocumentMousedown();
      bindFieldInsertDocumentMousedown();
      return;
    }
    unbindFieldInsertDocumentMousedown();
  });

  onBeforeUnmount(() => {
    unbindFieldInsertDocumentMousedown();
    textareaResizeObserver?.disconnect();
    textareaResizeObserver = null;
  });

  const handleFieldInsertHidden = () => {
    isFieldInsertOpen.value = false;
    fieldSearchKeyword.value = '';
  };

  const handleInsertFieldValue = (value: unknown) => {
    const display = formatFieldDisplayValue(value);
    modelValue.value = {
      field: '',
      value: display === '--' ? '' : display,
    };
    handleFieldInsertHidden();
    adjustTextareaHeight();
  };

  const handleInsertFieldItem = (value: unknown) => {
    if (isFieldValueEmpty(value)) {
      return;
    }
    handleInsertFieldValue(value);
  };

  const handleChange = (val: any) => {
    modelValue.value = {
      field: '',
      value: val ? String(val) : '',
    };
  };

  const handleTextareaChange = (val: string) => {
    if (props.useFieldInsert) {
      handleChange(val);
    } else {
      handlerChange(val);
    }
    adjustTextareaHeight();
  };

  const handlerSelectChange = (val: string | number) => {
    const isValidValue = val !== undefined && val !== null;
    selectTypeValue.value = isValidValue ? val : '';
    modelValue.value = {
      field: '',
      value: isValidValue ? val : '',
    };
  };

  const handlerUserChange = (val: string | string[]) => {
    modelValue.value = {
      field: '',
      value: val,
    };
  };

  const handlerChange = (val: string) => {
    if (props.riskFieldList.find((item: { id: string; }) => item.id === val)) {
      modelValue.value = {
        field: val,
        value: '',
      };
      isShowtip.value = true;
      return;
    }

    if (props.eventDataList.find((item: { text: string; }) => item.text === val)) {
      isShowtip.value = true;
      modelValue.value = {
        field: '',
        value: props.eventDataList.find((item: { text: string; }) => item.text === val).value,
      };
      return;
    }
    isShowtip.value = false;
    modelValue.value = {
      field: '',
      value: val,
    };
  };

  const formatTooltipData = (type: string | number, value: string | string[] | number) => {
    if (Array.isArray(value)) {
      return value.join(', ');
    }
    if (typeof value === 'object') {
      return JSON.stringify(value);
    }
    if (type === 'datetime' && props.config.type === 'self') {
      const date = new Date(String(value));
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      const seconds = String(date.getSeconds()).padStart(2, '0');
      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    } if (type === 'datetime' && props.config.type === 'field') {
      return  props.detailData[modelValue.value.field];
    }  if (type === 'select') {
      return value;
    }
    if (modelValue.value.field === '' && modelValue.value.value !== '' && type !== 'datetime' && type !== 'select') {
      return value;
    }
    if (modelValue.value.field !== '' && modelValue.value.value === '' && type !== 'datetime' && type !== 'select') {
      return props.detailData[modelValue.value.field];
    }
    return value;
  };

  watch(() => modelValue.value, (val) => {
    const valueToFormat = val.value || val.field;
    tipText.value = formatTooltipData(props.config.custom_type, valueToFormat);
    adjustTextareaHeight();
  }, {
    deep: true,
  });

  watch(() => props.config.custom_type, () => {
    setupTextareaResizeObserver();
  });

  onMounted(() => {
    setupTextareaResizeObserver();
    nextTick(() => {
      adjustTextareaHeight();
    });
  });

  watch(canInsertField, () => {
    nextTick(() => {
      adjustTextareaHeight();
    });
  });

  watch(() => props.config.custom_type, () => {
    if (props.config.custom_type === 'bk_user_selector') {
      modelValue.value = {
        field: props.config.default_value || [],
        value: props.config.default_value || [],
      };
    } else if (props.config.custom_type === 'select') {
      const defaultVal = props.config.default_value;
      selectTypeValue.value = (defaultVal !== undefined && defaultVal !== null) ? defaultVal : '';
      modelValue.value = {
        field: '',
        value: selectTypeValue.value,
      };
    } else {
      modelValue.value = {
        field: props.config.default_value || '',
        value: props.config.default_value || '',
      };
    }
  }, {
    immediate: true,
    deep: true,
  });

</script>

<style lang="postcss" scoped>
.field-insert-wrapper {
  display: flex;
  width: 100%;
  align-items: stretch;
}

.field-insert-wrapper.has-suffix {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 32px;
  align-items: stretch;

  :deep(.field-insert-wrapper__control .bk-input--text) {
    border-right: none;
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
  }

  :deep(.field-insert-wrapper__control .bk-textarea textarea) {
    border-right: none;
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
  }

  :deep(.field-insert-wrapper__control.bk-date-picker .bk-date-picker-rel .bk-date-picker-editor) {
    border-right: none;
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
  }
}

.field-insert-wrapper.is-textarea.has-suffix {
  align-items: stretch;

  .field-insert-wrapper__suffix {
    height: 100%;
    max-height: 32.5px;
    min-height: 32.5px;
    margin-top: 1.5px;
  }
}

.field-insert-wrapper__suffix-host {
  display: flex;
  width: 32px;
  height: 100%;
  min-width: 32px;
  flex-direction: column;
  align-self: stretch;

  :deep(> *) {
    display: flex;
    width: 100%;
    height: 100%;
    min-height: 100%;
    flex: 1;
    flex-direction: column;
  }
}

.field-insert-wrapper__main {
  flex: 1;
  min-width: 0;
}

.field-insert-wrapper__control {
  width: 100%;
}

.field-insert-wrapper.is-textarea {
  :deep(.field-insert-wrapper__control.bk-input) {
    height: auto;
    min-height: 32px;
  }
}

.auto-grow-textarea-input,
.field-insert-wrapper.is-textarea .auto-grow-textarea-input {
  :deep(.bk-textarea textarea) {
    height: 32px;
    max-height: 200px;
    min-height: 32px;
    padding-right: 30px !important;
    overflow: hidden hidden;
    line-height: 20px;
    box-sizing: border-box;
    resize: none;
  }
}

.auto-grow-textarea {
  width: 100%;

  :deep(.auto-grow-textarea-input .bk-textarea textarea) {
    height: 32px;
    max-height: 200px;
    min-height: 32px;
    padding-right: 30px !important;
    overflow: hidden hidden;
    box-sizing: border-box;
    resize: none;
  }
}

.field-insert-wrapper__suffix {
  display: flex;
  width: 32px;
  height: 100%;
  min-height: 32px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  color: #979ba5;
  cursor: pointer;
  background: #fff;
  border: 1px solid #c4c6cc;
  border-left: 1px solid #c4c6cc;
  border-radius: 0 2px 2px 0;
  box-sizing: border-box;

  &:hover,
  &.is-active {
    color: #3a84ff;
  }
}

:deep(.pa-user-selector.bk-user-selector) {
  width: 100%;
  min-width: 0;

  .custom-tag {
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.field-insert-wrapper__icon {
  display: block;
  width: 14px;
  height: 14px;
}

.field-insert-panel {
  width: 300px;
  padding: 0 0 4px;
}

.field-insert-panel__search {
  display: flex;
  align-items: center;
  padding: 4px 12px;
  margin-bottom: 2px;
  border-bottom: 1px solid #dcdee5;
}

.field-insert-panel__search-icon {
  margin-right: 6px;
  font-size: 15px;
  color: #979ba5;
  flex-shrink: 0;
}

.field-insert-panel__search-input {
  width: 100%;
  height: 24px;
  padding: 0;
  font-size: 12px;
  color: #63656e;
  background: transparent;
  border: none;
  outline: none;
  flex: 1;

  &::placeholder {
    color: #c4c6cc;
  }
}

.field-insert-panel__list {
  max-height: 280px;
  overflow-y: auto;
}

.field-insert-group__title {
  padding: 4px 12px;
  font-size: 12px;
  line-height: 20px;
  color: #979ba5;
}

.field-insert-item {
  display: flex;
  min-width: 0;
  padding: 6px 12px;
  font-size: 12px;
  line-height: 20px;
  color: #313238;
  cursor: pointer;
  align-items: center;

  &:hover {
    background: #f0f5ff;
  }

  &.is-disabled {
    color: #c4c6cc;
    cursor: not-allowed;

    &:hover {
      background: transparent;
    }

    .field-insert-item__name,
    .field-insert-item__value {
      color: #c4c6cc;
    }
  }
}

.field-insert-item__name {
  flex-shrink: 0;
  color: #63656e;
}

.field-insert-item__sep {
  flex-shrink: 0;
  margin: 0 4px;
}

.field-insert-item__value {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.field-insert-panel__empty {
  padding: 16px 12px;
  font-size: 12px;
  color: #979ba5;
  text-align: center;
}

.item-value {
  width: 100%;
  height: auto;
  padding: 3px;
  padding-bottom: 5px;
  margin-top: 3px;
  font-size: 12px;
  line-height: 16px;
  word-break: break-all;
  background: #fff;
}

.current-value {
  height: auto;
  max-width: 50vw;
  max-height: 50vh;
  padding: 3px;
  padding-bottom: 5px;
  margin-top: 3px;
  overflow: auto;
  font-size: 12px;
  line-height: 16px;
  word-break: break-all;
  background: #fff;
}
</style>

<style lang="postcss">
.field-insert-item-tooltips {
  max-width: 30vw !important;
  word-break: break-all;
  white-space: pre-wrap;
}
</style>
