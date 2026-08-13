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
  <div class="bkvision-param-config">
    <div class="param-card-title">
      {{ t('参数配置') }}
    </div>
    <div class="param-card-body">
      <div
        v-if="!hasReport"
        class="param-empty-state">
        <bk-exception
          class="param-empty-exception"
          :description="t('请先选择BKVision报表')"
          scene="part"
          :title="t('暂无参数配置')"
          type="empty" />
      </div>

      <div
        v-else-if="hasNoParam"
        class="param-empty-state">
        <bk-exception
          class="param-empty-exception"
          :description="t('当前报表暂无参数配置')"
          scene="part"
          type="empty" />
      </div>

      <div v-else>
        <!-- 交互组件 -->
        <div
          v-if="comList.length > 0"
          class="param-section">
          <div
            class="section-header"
            @click="isComExpanded = !isComExpanded">
            <audit-icon
              class="section-arrow"
              :class="{ 'is-collapsed': !isComExpanded }"
              type="angle-fill-down" />
            <span class="title-text">{{ t('交互组件') }}</span>
            <img
              class="title-info-icon"
              src="@/images/info-gray.svg">
            <span class="title-desc">
              {{ t('设置BKVision交互组件的默认值，用户打开图表后，可通过交互组件调整该值') }}
            </span>
          </div>
          <div
            v-show="isComExpanded"
            class="param-list">
            <div
              v-for="item in comList"
              :key="item.raw_name"
              class="param-item">
              <div class="param-label">
                <span
                  v-bk-tooltips="{
                    disabled: getPanelTooltip(item) === '',
                    content: getPanelTooltip(item)
                  }">{{ item.display_name || item.raw_name }}</span>
                <bk-popover
                  :is-show="defaultTipVisibleMap[item.raw_name] === true"
                  placement="top"
                  theme="light"
                  trigger="manual"
                  :z-index="10050"
                  @after-hidden="hideDefaultTip(item.raw_name)">
                  <bk-checkbox
                    class="title-right"
                    :disabled="false"
                    :model-value="item.is_default_value"
                    size="small"
                    @change="checked => handleDefaultValueToggle(checked, item)">
                    {{ t('使用默认值') }}
                  </bk-checkbox>
                  <template #content>
                    <div class="default-value-tip-popover">
                      <div class="default-value-tip-text">
                        {{ t('勾选后，若在 BKVision 嵌入管理页面中对变量值进行修改，当前工具会有参数更新提示') }}
                      </div>
                      <div class="default-value-tip-actions">
                        <bk-button
                          size="small"
                          theme="primary"
                          @click="handleConfirmDefaultTip(item)">
                          {{ t('知道了') }}
                        </bk-button>
                      </div>
                    </div>
                  </template>
                </bk-popover>
              </div>

              <div class="param-content">
                <bk-date-picker
                  v-if="isTimePicker(item)"
                  append-to-body
                  class="param-date-picker"
                  :class="{ 'is-hide-placeholder': shouldHidePlaceholder(item) }"
                  clearable
                  :disabled="item.is_default_value"
                  :editable="false"
                  ext-popover-cls="scene-report-date-picker-dropdown"
                  :format="getDatePickerFormat(item)"
                  :model-value="getDateValue(item)"
                  :placeholder="getDatePlaceholder(item)"
                  :shortcuts="dateShortCut"
                  :type="resolveDatePickerMode(item)"
                  :use-shortcut-text="resolveDatePickerMode(item) === 'datetime'"
                  @change="val => updateItemDefaultValue(val, item)" />
                <div
                  v-else-if="isTimeRanger(item)"
                  class="range-wrapper"
                  @mouseenter="hoverDeleteKey = item.raw_name"
                  @mouseleave="hoverDeleteKey = ''">
                  <date-picker
                    :id="TIME_RANGE_PICKER_ID"
                    :disabled="item.is_default_value"
                    :model-value="getRangeValue(item)"
                    style="width: 100%;"
                    @update:model-value="(val: string[]) => updateItemDefaultValue(val, item)" />
                  <audit-icon
                    v-if="hoverDeleteKey === item.raw_name && !item.is_default_value"
                    class="delete"
                    type="delete-fill"
                    @click="updateItemDefaultValue([], item)" />
                </div>
                <bk-input
                  v-else
                  :class="{ 'is-hide-placeholder': shouldHidePlaceholder(item) }"
                  :disabled="item.is_default_value"
                  :model-value="getInputValue(item)"
                  :placeholder="getInputPlaceholder(item)"
                  @change="val => updateItemDefaultValue(val, item)" />
              </div>
            </div>
          </div>
        </div>

        <!-- 变量 -->
        <div
          v-if="variableList.length > 0"
          class="param-section">
          <div
            class="section-header"
            @click="isVarExpanded = !isVarExpanded">
            <audit-icon
              class="section-arrow"
              :class="{ 'is-collapsed': !isVarExpanded }"
              type="angle-fill-down" />
            <span class="title-text">{{ t('变量') }}</span>
            <img
              class="title-info-icon"
              src="@/images/info-gray.svg">
            <span class="title-desc">
              {{ t('设置BKVision变量的值，该值在图表打开后不可修改') }}
            </span>
          </div>
          <div
            v-show="isVarExpanded"
            class="param-list">
            <div
              v-for="item in variableList"
              :key="item.raw_name"
              class="param-item">
              <div class="param-label">
                <span>{{ item.display_name || item.raw_name }}</span>
                <bk-popover
                  :is-show="defaultTipVisibleMap[item.raw_name] === true"
                  placement="top"
                  theme="light"
                  trigger="manual"
                  :z-index="10050"
                  @after-hidden="hideDefaultTip(item.raw_name)">
                  <bk-checkbox
                    class="title-right"
                    :disabled="false"
                    :model-value="item.is_default_value"
                    size="small"
                    @change="checked => handleDefaultValueToggle(checked, item)">
                    {{ t('使用默认值') }}
                  </bk-checkbox>
                  <template #content>
                    <div class="default-value-tip-popover">
                      <div class="default-value-tip-text">
                        {{ t('勾选后，若在 BKVision 嵌入管理页面中对变量值进行修改，当前工具会有参数更新提示') }}
                      </div>
                      <div class="default-value-tip-actions">
                        <bk-button
                          size="small"
                          theme="primary"
                          @click="handleConfirmDefaultTip(item)">
                          {{ t('知道了') }}
                        </bk-button>
                      </div>
                    </div>
                  </template>
                </bk-popover>
              </div>

              <div class="param-content">
                <bk-date-picker
                  v-if="isTimePicker(item)"
                  append-to-body
                  class="param-date-picker"
                  :class="{ 'is-hide-placeholder': shouldHidePlaceholder(item) }"
                  clearable
                  :disabled="item.is_default_value"
                  :editable="false"
                  ext-popover-cls="scene-report-date-picker-dropdown"
                  :format="getDatePickerFormat(item)"
                  :model-value="getDateValue(item)"
                  :placeholder="getDatePlaceholder(item)"
                  :shortcuts="dateShortCut"
                  :type="resolveDatePickerMode(item)"
                  :use-shortcut-text="resolveDatePickerMode(item) === 'datetime'"
                  @change="val => updateItemDefaultValue(val, item)" />
                <div
                  v-else-if="isTimeRanger(item)"
                  class="range-wrapper"
                  @mouseenter="hoverDeleteKey = item.raw_name"
                  @mouseleave="hoverDeleteKey = ''">
                  <date-picker
                    :id="TIME_RANGE_PICKER_ID"
                    :disabled="item.is_default_value"
                    :model-value="getRangeValue(item)"
                    style="width: 100%;"
                    @update:model-value="(val: string[]) => updateItemDefaultValue(val, item)" />
                  <audit-icon
                    v-if="hoverDeleteKey === item.raw_name && !item.is_default_value"
                    class="delete"
                    type="delete-fill"
                    @click="updateItemDefaultValue([], item)" />
                </div>
                <bk-input
                  v-else
                  :class="{ 'is-hide-placeholder': shouldHidePlaceholder(item) }"
                  :disabled="item.is_default_value"
                  :model-value="getInputValue(item)"
                  :placeholder="getInputPlaceholder(item)"
                  @change="val => updateItemDefaultValue(val, item)" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  export interface InputVariableItem {
    raw_name: string;
    display_name: string;
    description: string;
    required: boolean;
    field_category: string;
    is_default_value: boolean;
    default_value: string | Array<string> | Date;
    raw_default_value?: string | Array<string> | Date;
    choices: Array<{
      key: string;
      name: string;
    }>;
  }

  interface Props {
    hasReport: boolean;
    inputVariables: InputVariableItem[];
    reportListsPanels: Array<Record<string, any>>;
  }

  const props = defineProps<Props>();
  // eslint-disable-next-line func-call-spacing
  const emit = defineEmits<{
    change: [value: InputVariableItem[]]
  }>();
  const { t } = useI18n();

  /** 侧滑 z-index=9999，用 id 限定弹出层作用域并抬升层级 */
  const TIME_RANGE_PICKER_ID = 'scene-report-param-config';

  const now = new Date();
  const isComExpanded = ref(true);
  const isVarExpanded = ref(true);
  const hoverDeleteKey = ref('');
  const defaultTipVisibleMap = ref<Record<string, boolean>>({});
  const localFields = ref<InputVariableItem[]>([]);

  const cloneItem = (item: InputVariableItem): InputVariableItem => ({
    ...item,
    default_value: Array.isArray(item.default_value) ? [...item.default_value] : item.default_value,
    raw_default_value: Array.isArray(item.raw_default_value) ? [...item.raw_default_value] : item.raw_default_value,
    choices: Array.isArray(item.choices) ? [...item.choices] : [],
  });

  watch(() => props.inputVariables, (list) => {
    localFields.value = Array.isArray(list) ? list.map(cloneItem) : [];
  }, {
    immediate: true,
    deep: true,
  });

  const panelUidSet = computed(() => new Set((props.reportListsPanels || []).map(item => item.uid)));

  const comList = computed(() => localFields.value.filter(item => panelUidSet.value.has(item.description)));
  const variableList = computed(() => localFields.value.filter(item => !panelUidSet.value.has(item.description)));
  const hasNoParam = computed(() => localFields.value.length === 0);

  const getLastMillisecondOfDate = (ts: number) => {
    const date = new Date(ts);
    date.setHours(0, 0, 0, 0);
    return date;
  };

  const dateShortCut: any = [
    { text: '今天', value: () => getLastMillisecondOfDate(now.getTime()), short: 'now/d' },
    { text: '昨天', value: () => getLastMillisecondOfDate(now.getTime() - 24 * 60 * 60 * 1000), short: 'now-1d/d' },
    { text: '前天', value: () => getLastMillisecondOfDate(now.getTime() - 2 * 24 * 60 * 60 * 1000), short: 'now-2d/d' },
    { text: '一星期前', value: () => getLastMillisecondOfDate(now.getTime() - 7 * 24 * 60 * 60 * 1000), short: 'now-7d/d' },
    { text: '一个月前', value: () => getLastMillisecondOfDate(now.getTime() - 30 * 24 * 60 * 60 * 1000), short: 'now-1M/d' },
    { text: '一年前', value: () => getLastMillisecondOfDate(now.getTime() - 365 * 24 * 60 * 60 * 1000), short: 'now-1y/d' },
  ];

  const getPanelTooltip = (item: InputVariableItem) => {
    const matched = props.reportListsPanels.find(panel => panel.uid === item.description);
    return matched?.description || '';
  };

  const DATE_ONLY_CATEGORIES = new Set([
    'date',
    'date-picker',
    'date_picker',
    'datepicker',
  ]);
  const DATETIME_CATEGORIES = new Set([
    'time-picker',
    'time_picker',
    'time_select',
    'time-select',
    'datetime',
  ]);
  const TIME_PICKER_CATEGORIES = new Set([
    ...DATE_ONLY_CATEGORIES,
    ...DATETIME_CATEGORIES,
  ]);
  const TIME_RANGER_CATEGORIES = new Set([
    'time-ranger',
    'time_ranger',
    'time_range_select',
    'time-range-select',
  ]);
  type DatePickerMode = 'date' | 'datetime';

  /** 优先取 panel.type，兼容 field_category；时间类别优先 */
  const resolveFieldCategory = (item: InputVariableItem) => {
    const panel = props.reportListsPanels.find(p => p.uid === item.description);
    const candidates = [panel?.type, item.field_category]
      .filter(Boolean)
      .map((v: string) => String(v).trim()
        .toLowerCase());
    const timeHit = candidates.find(c => TIME_PICKER_CATEGORIES.has(c) || TIME_RANGER_CATEGORIES.has(c));
    return timeHit || candidates[0] || '';
  };

  const looksLikeDateOnlyValue = (value: unknown) => {
    if (typeof value !== 'string' || !value.trim()) {
      return false;
    }
    const v = value.trim();
    if (/^\d{8}$/.test(v)) {
      return true;
    }
    if (/^\d{4}-\d{2}-\d{2}$/.test(v)) {
      return true;
    }
    return false;
  };

  const looksLikeDateTimeValue = (value: unknown) => {
    if (typeof value !== 'string' || !value.trim()) {
      return false;
    }
    const v = value.trim();
    return /\d{1,2}:\d{2}/.test(v) || /^\d{4}-\d{2}-\d{2}[ T]\d/.test(v);
  };

  /**
   * 自动选择 date / datetime：
   * 1) 明确类型优先
   * 2) 模糊类型看原始默认值形态
   * 3) 都没有则默认 date
   */
  const resolveDatePickerMode = (item: InputVariableItem): DatePickerMode => {
    const cat = resolveFieldCategory(item);
    if (DATE_ONLY_CATEGORIES.has(cat)) {
      return 'date';
    }
    if (DATETIME_CATEGORIES.has(cat)) {
      return 'datetime';
    }
    // 用 raw_default_value 推断，避免用户编辑后模式翻转
    const sample = item.raw_default_value ?? item.default_value;
    if (looksLikeDateTimeValue(sample)) {
      return 'datetime';
    }
    if (looksLikeDateOnlyValue(sample)) {
      return 'date';
    }
    return 'date';
  };

  const getDatePickerFormat = (item: InputVariableItem) => (
    resolveDatePickerMode(item) === 'datetime' ? 'yyyy-MM-dd HH:mm:ss' : 'yyyy-MM-dd'
  );

  /** 严格按 BKVision panel.type / field_category 渲染，不做名称启发式（避免「数据时间」等 inputer 被误判为日期） */
  const isTimeRanger = (item: InputVariableItem) => {
    const cat = resolveFieldCategory(item);
    return TIME_RANGER_CATEGORIES.has(cat);
  };

  const isTimePicker = (item: InputVariableItem) => {
    if (isTimeRanger(item)) {
      return false;
    }
    const cat = resolveFieldCategory(item);
    return TIME_PICKER_CATEGORIES.has(cat);
  };

  const findFieldIndex = (rawName: string) => localFields.value.findIndex(item => item.raw_name === rawName);

  const updateField = (rawName: string, patch: Partial<InputVariableItem>) => {
    const index = findFieldIndex(rawName);
    if (index < 0) {
      return;
    }
    localFields.value[index] = {
      ...localFields.value[index],
      ...patch,
    };
    emit('change', localFields.value);
  };

  const hideDefaultTip = (rawName: string) => {
    defaultTipVisibleMap.value = {
      ...defaultTipVisibleMap.value,
      [rawName]: false,
    };
  };

  const handleConfirmDefaultTip = (item: InputVariableItem) => {
    hideDefaultTip(item.raw_name);
    updateField(item.raw_name, {
      is_default_value: true,
      default_value: item.raw_default_value ?? '',
    });
  };

  const handleDefaultValueToggle = (checked: boolean | string | number, item: InputVariableItem) => {
    if (checked === true) {
      defaultTipVisibleMap.value = {
        ...defaultTipVisibleMap.value,
        [item.raw_name]: true,
      };
      return;
    }
    hideDefaultTip(item.raw_name);
    updateField(item.raw_name, {
      is_default_value: false,
    });
  };

  const pad2 = (n: number) => String(n).padStart(2, '0');

  const parseDateValue = (value: string | Array<string> | Date | undefined | null) => {
    if (value instanceof Date) {
      return Number.isNaN(value.getTime()) ? '' : value;
    }
    if (typeof value !== 'string' || !value) {
      return '';
    }
    if (/^\d{8}$/.test(value)) {
      const parsed = new Date(`${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`);
      return Number.isNaN(parsed.getTime()) ? '' : parsed;
    }
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? '' : parsed;
  };

  /** 按模式格式化提交值；纯日期若原始为 yyyyMMdd 则保持该格式 */
  const formatDateOutput = (val: Date | string, item: InputVariableItem) => {
    const date = val instanceof Date ? val : parseDateValue(val);
    if (!date || !(date instanceof Date)) {
      return '';
    }
    const y = date.getFullYear();
    const m = pad2(date.getMonth() + 1);
    const d = pad2(date.getDate());
    if (resolveDatePickerMode(item) === 'datetime') {
      return `${y}-${m}-${d} ${pad2(date.getHours())}:${pad2(date.getMinutes())}:${pad2(date.getSeconds())}`;
    }
    const rawSample = item.raw_default_value;
    if (typeof rawSample === 'string' && /^\d{8}$/.test(rawSample.trim())) {
      return `${y}${m}${d}`;
    }
    return `${y}-${m}-${d}`;
  };

  const updateItemDefaultValue = (val: any, item: InputVariableItem) => {
    let next = val;
    if (isTimePicker(item)) {
      next = val ? formatDateOutput(val, item) : '';
    }
    updateField(item.raw_name, {
      default_value: next,
    });
  };

  const getDateValue = (item: InputVariableItem) => parseDateValue(item.default_value);
  const getRangeValue = (item: InputVariableItem) => (Array.isArray(item.default_value) ? item.default_value : []);
  const getInputValue = (item: InputVariableItem) => {
    if (typeof item.default_value === 'string' || typeof item.default_value === 'number') {
      return String(item.default_value);
    }
    if (Array.isArray(item.default_value)) {
      return item.default_value.join(',');
    }
    return '';
  };

  /** 勾选「使用默认值」且当前无展示值时，不展示 placeholder */
  const shouldHidePlaceholder = (item: InputVariableItem) => {
    if (!item.is_default_value) {
      return false;
    }
    if (isTimePicker(item)) {
      return !getDateValue(item);
    }
    if (isTimeRanger(item)) {
      return getRangeValue(item).length === 0;
    }
    return getInputValue(item) === '';
  };

  // bk-input 内部是 `props.placeholder || t.placeholder`，空字符串会回退成「请输入」
  const HIDDEN_PLACEHOLDER = '\u00A0';
  const getInputPlaceholder = (item: InputVariableItem) => (
    shouldHidePlaceholder(item) ? HIDDEN_PLACEHOLDER : t('请输入')
  );
  const getDatePlaceholder = (item: InputVariableItem) => (
    shouldHidePlaceholder(item) ? HIDDEN_PLACEHOLDER : t('请选择')
  );

  const getFields = () => localFields.value;

  defineExpose({
    getFields,
  });
</script>

<style scoped lang="postcss">
.bkvision-param-config {
  margin-bottom: 16px;
  background: #fff;
  border-radius: 2px;
  box-shadow: 0 1px 2px 0 #00000029;
}

.param-empty-state {
  min-height: 180px;
  padding: 16px 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.param-empty-exception {
  width: 100%;

  :deep(.bk-exception-img) {
    width: 260px;
    height: 130px;
  }
}

.param-card-title {
  display: flex;
  height: 52px;
  padding: 0 24px;
  font-size: 14px;
  font-weight: 600;
  color: #313238;
  align-items: center;
}

.param-card-body {
  padding: 0 24px 16px;
}

.param-section {
  & + .param-section {
    margin-top: 8px;
  }
}

.section-header {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 32px;
  gap: 6px;
  cursor: pointer;

  .section-arrow {
    flex: 0 0 auto;
    font-size: 12px;
    color: #4D4F56;
    transition: transform .2s ease;

    &.is-collapsed {
      transform: rotate(-90deg);
    }
  }

  .title-text {
    flex: 0 0 auto;
    font-size: 12px;

    color: #313238;
  }

  .title-info-icon {
    width: 14px;
    height: 14px;
    margin-left: 3px; /* 与标题间距 9px（含父级 gap 6px） */
    flex: 0 0 auto;
  }

  .title-desc {
    flex: 1;
    overflow: hidden;
    font-size: 12px;
    line-height: 18px;
    color: #979ba5;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.param-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 12px;
}

.param-item {
  width: 100%;
}

.param-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 5px;
  font-size: 12px;
  line-height: 20px;
  color: #4d4f56;
}

.title-right {
  flex: 0 0 auto;
  margin-left: 8px;
  color: #313238 !important;
  cursor: pointer;

  :deep(.bk-checkbox) {
    margin-right: 0 !important;
    margin-left: 0 !important;
  }

  :deep(.bk-checkbox-label),
  :deep(span) {
    margin-left: 4px;
    color: #313238 !important;
  }
}

.param-content {
  width: 100%;

  .param-date-picker {
    width: 100%;
  }

  /* 勾选默认值且无值时，强制隐藏 placeholder 文案 */
  .is-hide-placeholder {
    :deep(input::placeholder),
    :deep(.bk-input--text::placeholder),
    :deep(.bk-input--textarea::placeholder),
    :deep(.bk-date-picker-editor::placeholder) {
      color: transparent !important;
      opacity: 0 !important;
    }
  }
}

.range-wrapper {
  position: relative;
}

.delete {
  position: absolute;
  top: 8px;
  right: 10px;
  font-size: 14px;
  color: #c4c6cc;
  cursor: pointer;
}

.default-value-tip-popover {
  width: 230px;
  padding: 0;

  .default-value-tip-text {
    margin: 0 8px 12px;
    font-size: 12px;
    line-height: 20px;
    color: #313238;
    white-space: normal;
  }

  .default-value-tip-actions {
    display: flex;
    justify-content: flex-end;
    padding: 0 8px 8px;
  }
}
</style>

<!-- 侧滑 z-index=9999，日期 / 时间范围面板需挂到更高层才能点开 -->
<style lang="postcss">
.scene-report-date-picker-dropdown,
.scene-report-date-picker-dropdown.bk-date-picker-dropdown,
.scene-report-date-picker-dropdown.bk-picker-dropdown {
  z-index: 10050 !important;
}

body > .scene-report-date-picker-dropdown,
body > .bk-date-picker-dropdown.scene-report-date-picker-dropdown {
  z-index: 10050 !important;
}

/* @blueking/date-picker 时间范围选择器弹出层 */
.__bk-date-picker-popover__.__bk-date-picker-popover__scene-report-param-config {
  z-index: 10050 !important;
}

/* 组件内置 hover tip，侧滑内需抬高层级 */
.__date-tooltips__,
.bk-popper:has(.__date-tooltips__),
.bk-popover:has(.__date-tooltips__),
.bk-pop2-content:has(.__date-tooltips__) {
  z-index: 10050 !important;
}
</style>

