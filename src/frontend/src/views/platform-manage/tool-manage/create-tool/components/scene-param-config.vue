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
  specific language governing permissions and limitations
  under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the product delivered to anyone in the future.
-->
<template>
  <div
    v-if="configList.length > 0"
    class="scene-param-config"
    @mouseover="handleOverflowTagHover">
    <div
      v-for="item in configList"
      :key="item.key"
      class="param-config-block">
      <!-- 区块标题 -->
      <div class="block-header">
        {{ item.name }}
      </div>

      <div class="block-body">
        <!-- 覆盖参数默认值：弹窗内占满，编辑/新建页占 1/3 宽度 -->
        <div
          class="override-section"
          :class="{ 'is-full-width': overrideSelectFullWidth }">
          <label class="form-label">{{ t('覆盖参数默认值') }}</label>
          <div class="form-control">
            <bk-select
              :auto-height="false"
              class="override-param-select"
              :clearable="false"
              collapse-tags
              filterable
              :model-value="item.override_keys"
              multiple
              multiple-mode="tag"
              :placeholder="t('请选择需要覆盖的参数')"
              :popover-options="{
                boundary: 'body',
                zIndex: popoverZIndex,
              }"
              :search-placeholder="t('请输入关键字')"
              @change="(val: string[]) => handleOverrideChange(item, val)">
              <bk-option
                v-for="param in inputVariableList"
                :id="param.raw_name"
                :key="param.raw_name"
                :name="getParamOptionLabel(param)">
                <span
                  v-bk-tooltips="getOverflowTips(
                    getParamOptionLabel(param),
                    `param-option-${param.raw_name}`,
                    'right',
                  )"
                  class="select-option-overflow"
                  @mouseenter="(e: MouseEvent) => checkTextOverflow(`param-option-${param.raw_name}`, e)">
                  {{ getParamOptionLabel(param) }}
                </span>
              </bk-option>
            </bk-select>
          </div>
        </div>

        <!-- 参数表格：参数名 +（可选）显示名 + 默认值 -->
        <div
          v-if="getTableData(item).length > 0"
          class="render-field"
          :class="{ 'is-two-col': !showDisplayName }">
          <div class="field-header-row">
            <div class="field-value col-name">
              {{ t('参数名') }}
            </div>
            <div
              v-if="showDisplayName"
              class="field-value col-display">
              {{ t('显示名') }}
            </div>
            <div class="field-value col-default">
              <span class="col-default-label">
                {{ t('默认值') }}<span class="required-mark">*</span>
              </span>
            </div>
            <div class="field-value field-operation col-action" />
          </div>
          <div
            v-for="row in getTableData(item)"
            :key="row.raw_name"
            class="field-row">
            <div class="field-value col-name">
              <span
                v-bk-tooltips="getOverflowTips(
                  getParamName(row),
                  `param-name-${item.key}-${row.raw_name}`,
                )"
                class="param-name-text"
                @mouseenter="(e: MouseEvent) => checkTextOverflow(`param-name-${item.key}-${row.raw_name}`, e)">
                {{ getParamName(row) }}
              </span>
            </div>
            <div
              v-if="showDisplayName"
              class="field-value col-display">
              <span
                v-bk-tooltips="getOverflowTips(
                  getParamDisplayName(row),
                  `param-display-${item.key}-${row.raw_name}`,
                )"
                class="param-name-text"
                @mouseenter="(e: MouseEvent) => checkTextOverflow(`param-display-${item.key}-${row.raw_name}`, e)">
                {{ getParamDisplayName(row) }}
              </span>
            </div>
            <div
              class="field-value col-default"
              :class="{ 'is-error': isFieldInvalid(item.key, row.raw_name) }"
              :data-override-field="getFieldErrorKey(item.key, row.raw_name)">
              <bk-select
                v-if="isMultiSelectVar(row.raw_name)"
                :auto-height="false"
                class="override-default-multiselect"
                clearable
                filterable
                :loading="isCandidatesLoading(row.raw_name)"
                :model-value="getOverrideValue(item, row.raw_name)"
                multiple
                multiple-mode="tag"
                :placeholder="t('请选择默认值')"
                :search-placeholder="t('搜索或粘贴名称/ID')"
                selected-style="checkbox"
                show-select-all
                show-selected-icon
                @change="(val: any) => handleDefaultValueChange(item, row.raw_name, val)"
                @clear="() => handleDefaultValueChange(item, row.raw_name, [])"
                @search-change="(val: string) => handleDefaultSearchChange(item, row.raw_name, val)"
                @toggle="(open: boolean) => handleDefaultSelectToggle(open, item, row.raw_name)">
                <!-- 自行渲染首项 + +n，避免 collapse-tags 初次回显/候选加载后不折叠 -->
                <template #tag="{ selected }">
                  <template v-if="selected.length">
                    <bk-tag
                      class="override-selected-tag"
                      closable
                      @close="handleRemoveSelectedValue(item, row.raw_name, selected[0].value)">
                      {{ getSelectedChoiceLabel(row.raw_name, selected[0].value) }}
                    </bk-tag>
                    <bk-tag
                      v-if="selected.length > 1"
                      v-bk-tooltips="{
                        content: getOverflowSelectedTipsContent(row.raw_name, selected),
                        theme: 'dark',
                        placement: 'top',
                        extCls: 'override-selected-tips-wrap',
                      }"
                      class="override-selected-overflow-tag">
                      +{{ selected.length - 1 }}
                    </bk-tag>
                  </template>
                </template>
                <bk-option
                  v-for="choice in getMultiSelectChoices(row.raw_name)"
                  :id="choice.key"
                  :key="choice.key"
                  :name="choice.name">
                  <span
                    v-bk-tooltips="getOverflowTips(
                      choice.name,
                      `choice-${row.raw_name}-${choice.key}`,
                      'right',
                    )"
                    class="select-option-overflow"
                    @mouseenter="(e: MouseEvent) => checkTextOverflow(`choice-${row.raw_name}-${choice.key}`, e)">
                    {{ choice.name }}
                  </span>
                </bk-option>
              </bk-select>
              <!-- 时间范围选择器：与第一步参数组件保持一致 -->
              <div
                v-else-if="isTimeRangeVar(row.raw_name)"
                class="time-range-select-wrapper"
                @mouseenter="hoveredTimeRangeKey = getFieldErrorKey(item.key, row.raw_name)"
                @mouseleave="hoveredTimeRangeKey = ''">
                <div class="time-range-inner">
                  <date-picker
                    class="override-time-range-picker"
                    :model-value="getOverrideValue(item, row.raw_name)"
                    :placeholder="t('请选择')"
                    style="width: 100%; height: 100%; border: none;"
                    @update:model-value="(val: any) => handleDefaultValueChange(item, row.raw_name, val)" />
                  <audit-icon
                    v-show="hoveredTimeRangeKey === getFieldErrorKey(item.key, row.raw_name)
                      && normalizeTimeRangeValue(getOverrideValue(item, row.raw_name)).length > 0"
                    class="delete-fill-btn"
                    type="delete-fill"
                    @click.stop="handleDefaultValueChange(item, row.raw_name, [])" />
                </div>
              </div>
              <!-- 时间选择器：与第一步参数组件保持一致 -->
              <bk-date-picker
                v-else-if="isTimePickerVar(row.raw_name)"
                append-to-body
                class="override-time-picker"
                clearable
                :model-value="getOverrideValue(item, row.raw_name)"
                style="width: 100%"
                type="datetime"
                @change="(val: any) => handleDefaultValueChange(item, row.raw_name, val || '')" />
              <!-- 数字输入框 -->
              <bk-input
                v-else-if="isNumberInputVar(row.raw_name)"
                :model-value="getOverrideValue(item, row.raw_name)"
                :placeholder="t('请输入')"
                type="number"
                @change="(val: any) => handleDefaultValueChange(item, row.raw_name, val)" />
              <!-- 人员选择器 -->
              <audit-user-selector-tenant
                v-else-if="isPersonSelectVar(row.raw_name)"
                allow-create
                class="override-person-select"
                :model-value="getOverrideValue(item, row.raw_name)"
                :placeholder="t('请输入人员进行搜索')"
                @change="(val: any) => handleDefaultValueChange(item, row.raw_name, val)" />
              <!-- BKVision 等选择器：tag 输入 -->
              <bk-tag-input
                v-else-if="isTagInputVar(row.raw_name)"
                allow-create
                class="override-tag-input"
                collapse-tags
                has-delete-icon
                :list="[]"
                :model-value="getOverrideValue(item, row.raw_name)"
                @change="(val: any) => handleDefaultValueChange(item, row.raw_name, val)" />
              <bk-input
                v-else
                :model-value="getOverrideValue(item, row.raw_name)"
                :placeholder="t('请输入')"
                @change="(val: any) => handleDefaultValueChange(item, row.raw_name, val)" />
            </div>
            <div class="field-value field-operation col-action">
              <audit-icon
                class="reduce-fill field-icon"
                type="reduce-fill"
                @click="handleRemoveParam(item, row.raw_name)" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import {
    computed,
    defineComponent,
    h,
    nextTick,
    onBeforeUnmount,
    reactive,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ToolManageService from '@service/tool-manage';

  import useMessage from '@hooks/use-message';

  import type { SceneParamOverride, FormData } from '../types';

  interface ConfigItem {
    key: string;             // scene-{id} 或 system-{id}
    id: number | string;
    name: string;
    type: 'scene' | 'system';
    override_keys: string[];
    default_values: Record<string, any>;
  }

  interface InputVarItem {
    raw_name: string;
    display_name: string;
    var_name?: string;
    description?: string;
    required?: boolean;
    field_category?: string;
    default_value?: any;
    raw_default_value?: any;
    choices?: Array<{
      key: string;
      name: string;
    }>;
  }

  interface CandidateChoice {
    key: string;
    name: string;
  }

  const props = withDefaults(defineProps<{
    formData: FormData;
    selectedScenes: Array<{ id: number; name: string }>;
    selectedSystems: Array<{ id: string; name: string }>;
    inputVariables: InputVarItem[];
    /** 当前工具 uid，用于拉取输入变量候选选项 */
    toolUid?: string;
    /** 覆盖参数下拉是否占满容器（弹窗内为 true，编辑/新建页为 false） */
    overrideSelectFullWidth?: boolean;
    /** 是否展示「显示名」列 */
    showDisplayName?: boolean;
    /** 下拉 z-index（侧滑内需高于容器） */
    popoverZIndex?: number;
  }>(), {
    toolUid: '',
    overrideSelectFullWidth: false,
    showDisplayName: true,
    popoverZIndex: 2500,
  });

  // eslint-disable-next-line func-call-spacing
  const emit = defineEmits<{
    (e: 'update:paramOverrides', value: Record<string, SceneParamOverride>): void;
  }>();

  /** 无 display_name 时的硬编码展示名映射（Story 允许临时字典） */
  const PARAM_DISPLAY_NAME_MAP: Record<string, string> = {
    cc_ids: '业务列表',
    game_ids: '游戏列表',
  };

  /** 需通过候选接口拉取选项的参数（与工具详情 input_variable.raw_name 对齐） */
  const CANDIDATE_API_RAW_NAMES = new Set(['cc_ids', 'game_ids']);

  const { t } = useI18n();
  const { messageSuccess, messageWarn } = useMessage();

  const inputVariableList = computed(() => props.inputVariables || []);

  // bk-select +n tips 默认 z-index≈8000，侧滑内需抬高
  const ensureSelectOverflowTipsZIndex = () => {
    const targetZ = Number(props.popoverZIndex) + 10;
    document.querySelectorAll<HTMLElement>('.bk-select-tooltips').forEach((el) => {
      const tipEl = el;
      if ((Number(tipEl.style.zIndex) || 0) < targetZ) {
        tipEl.style.zIndex = String(targetZ);
      }
    });
  };

  const handleOverflowTagHover = (e: MouseEvent) => {
    const target = e.target as HTMLElement | null;
    if (!target?.closest?.('.bk-select-overflow-tag')) return;
    // bk-tooltips 在 mouseenter 内 setTimeout(0) 创建 tips，需延后抬高
    setTimeout(ensureSelectOverflowTipsZIndex, 0);
    setTimeout(ensureSelectOverflowTipsZIndex, 20);
  };

  // 候选选项缓存：raw_name -> choices
  const candidatesMap = ref<Record<string, CandidateChoice[]>>({});
  const candidatesLoadingMap = ref<Record<string, boolean>>({});
  const candidatesFetchedSet = ref<Set<string>>(new Set());
  /** 当前 hover 的时间范围选择器字段 key，用于显示清除图标 */
  const hoveredTimeRangeKey = ref('');

  // 展示第一步「参数名」：API 工具为 var_name，数据查询等为 raw_name
  const getParamName = (param: Pick<InputVarItem, 'raw_name' | 'var_name'>) => param.var_name || param.raw_name;

  // 展示第一步「显示名」，无值时回退硬编码映射
  const getParamDisplayName = (param: Pick<InputVarItem, 'raw_name' | 'display_name'>) => (
    param.display_name || PARAM_DISPLAY_NAME_MAP[param.raw_name] || '--'
  );

  // 覆盖参数下拉：参数名(显示名)，支持按两者搜索
  const getParamOptionLabel = (param: Pick<InputVarItem, 'raw_name' | 'var_name' | 'display_name'>) => {
    const name = getParamName(param);
    const displayName = getParamDisplayName(param);
    if (!displayName || displayName === '--') return name;
    return `${name}(${displayName})`;
  };

  /** 仅文本溢出时展示 tips；delay 配合 mouseenter 量宽，避免首次 hover 读到旧 disabled */
  const textOverflowMap = reactive<Record<string, boolean>>({});

  const isTextOverflow = (key: string) => !!textOverflowMap[key];

  const checkTextOverflow = (key: string, e: MouseEvent) => {
    const el = e.currentTarget as HTMLElement | null;
    if (!el) return;
    textOverflowMap[key] = el.scrollWidth > el.clientWidth + 1;
  };

  const getOverflowTips = (
    content: string,
    key: string,
    placement: 'top' | 'right' = 'top',
  ) => ({
    content,
    placement,
    theme: 'dark' as const,
    delay: 200,
    disabled: !isTextOverflow(key),
  });

  // 构建配置列表：每个选中的场景/系统对应一个配置区块
  const configList = computed<ConfigItem[]>(() => {
    const list: ConfigItem[] = [];
    const overrides = props.formData.scene_param_overrides || {};

    for (const s of props.selectedScenes) {
      const key = `scene-${s.id}`;
      const existing = overrides[key];
      list.push({
        key,
        id: s.id,
        name: s.name,
        type: 'scene',
        override_keys: existing?.override_param_keys || [],
        default_values: existing?.param_default_values || {},
      });
    }

    for (const s of props.selectedSystems) {
      const key = `system-${s.id}`;
      const existing = overrides[key];
      list.push({
        key,
        id: s.id,
        name: s.name,
        type: 'system',
        override_keys: existing?.override_param_keys || [],
        default_values: existing?.param_default_values || {},
      });
    }

    return list;
  });

  // 当前已选中的覆盖参数 raw_name 集合
  const activeOverrideRawNames = computed(() => {
    const names = new Set<string>();
    configList.value.forEach((item) => {
      (item.override_keys || []).forEach(key => names.add(key));
    });
    return names;
  });

  // 获取某个区块的表格数据：只展示已选中覆盖的参数
  const getTableData = (item: ConfigItem) => {
    if (!item.override_keys || item.override_keys.length === 0) return [];
    return item.override_keys.map((key) => {
      const found = inputVariableList.value.find(v => v.raw_name === key);
      return found || { raw_name: key, display_name: key, default_value: '' };
    });
  };

  const getInputVarConfig = (rawName: string) => inputVariableList.value.find(v => v.raw_name === rawName);

  const isMultiSelectVar = (rawName: string) => getInputVarConfig(rawName)?.field_category === 'multiselect'
    || CANDIDATE_API_RAW_NAMES.has(rawName);

  /** 时间范围选择器（API/数据查询 time_range_select，BKVision time-ranger） */
  const isTimeRangeVar = (rawName: string) => {
    const category = getInputVarConfig(rawName)?.field_category;
    return category === 'time_range_select' || category === 'time-ranger';
  };

  /** 时间选择器（API/数据查询 time_select，BKVision time-picker） */
  const isTimePickerVar = (rawName: string) => {
    const category = getInputVarConfig(rawName)?.field_category;
    return category === 'time_select' || category === 'time-picker';
  };

  /** 数字输入框 */
  const isNumberInputVar = (rawName: string) => getInputVarConfig(rawName)?.field_category === 'number_input';

  /** 人员选择器 */
  const isPersonSelectVar = (rawName: string) => getInputVarConfig(rawName)?.field_category === 'person_select';

  /**
   * 文本输入类（走普通 bk-input）
   * 含 API/数据查询 input、BKVision inputer/variable
   */
  const isPlainInputVar = (rawName: string) => {
    const category = getInputVarConfig(rawName)?.field_category;
    return !category
      || category === 'input'
      || category === 'inputer'
      || category === 'variable';
  };

  /**
   * BKVision 等选择器：未单独处理的类型走 tag-input（与 tool-form-item / bk-vision-components 一致）
   */
  const isTagInputVar = (rawName: string) => {
    if (isMultiSelectVar(rawName)
      || isTimeRangeVar(rawName)
      || isTimePickerVar(rawName)
      || isNumberInputVar(rawName)
      || isPersonSelectVar(rawName)
      || isPlainInputVar(rawName)) {
      return false;
    }
    return !!getInputVarConfig(rawName)?.field_category;
  };

  /** 值需按数组处理的覆盖参数（多选 / 时间范围 / 人员 / tag） */
  const isArrayValueVar = (rawName: string) => (
    isMultiSelectVar(rawName)
    || isTimeRangeVar(rawName)
    || isPersonSelectVar(rawName)
    || isTagInputVar(rawName)
  );

  /**
   * 规范化时间范围值：date-picker 需要 string[]；
   * 兼容数组、逗号拼接字符串（如 now-30d,now）、JSON 数组字符串。
   */
  const normalizeTimeRangeValue = (val: unknown): string[] => {
    if (Array.isArray(val)) {
      return val
        .map(item => (item === null || item === undefined ? '' : String(item)))
        .filter(Boolean);
    }
    if (typeof val === 'string') {
      const trimmed = val.trim();
      if (!trimmed) return [];
      if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
        try {
          const parsed = JSON.parse(trimmed);
          if (Array.isArray(parsed)) {
            return parsed
              .map(item => (item === null || item === undefined ? '' : String(item)))
              .filter(Boolean);
          }
        } catch {
          // ignore
        }
      }
      const parts = trimmed.split(',').map(s => s.trim());
      return parts.filter(Boolean);
    }
    if (val === null || val === undefined || val === '') return [];
    return [String(val)];
  };

  /** 人员选择器值归一化为用户名字符串数组 */
  const normalizePersonSelectValue = (val: unknown): string[] => {
    if (val === undefined || val === null || val === '') return [];
    const arr = Array.isArray(val) ? val : [val];
    return arr
      .map((u) => {
        if (!u) return '';
        if (typeof u === 'string') return u;
        const obj = u as Record<string, any>;
        return obj.id
          || obj.bk_username
          || obj.username
          || obj.login_name
          || obj.name
          || obj.display_name
          || '';
      })
      .filter(Boolean)
      .map(String);
  };

  const isCandidatesLoading = (rawName: string) => !!candidatesLoadingMap.value[rawName];

  /** 格式：名称(id)，便于名称/ID 搜索与回显（如 业务A(100)、游戏名称(gameid)） */
  const formatCandidateChoiceName = (name: string, id: number | string) => `${name}(${id})`;

  const getMultiSelectChoices = (rawName: string): CandidateChoice[] => {
    if (candidatesMap.value[rawName]?.length) {
      return candidatesMap.value[rawName];
    }
    const configChoices = getInputVarConfig(rawName)?.choices || [];
    return configChoices.map(item => ({
      key: String(item.key),
      name: item.name,
    }));
  };

  const normalizeMultiSelectValue = (val: unknown): string[] => {
    if (Array.isArray(val)) return val.map(item => String(item));
    if (val === undefined || val === null || val === '') return [];
    if (typeof val === 'string') {
      const trimmed = val.trim();
      if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
        try {
          const parsed = JSON.parse(trimmed);
          return Array.isArray(parsed) ? parsed.map(item => String(item)) : [];
        } catch {
          // ignore
        }
      }
      if (trimmed.includes(',')) {
        const parts = trimmed.split(',').map(s => s.trim());
        return parts.filter(Boolean);
      }
      return trimmed ? [trimmed] : [];
    }
    return [String(val)];
  };

  /** 候选多选提交值为数字数组；下拉展示用字符串 id 匹配 option */
  const normalizeCandidateIdsValue = (val: unknown): number[] => {
    const list = normalizeMultiSelectValue(val);
    return list
      .map((item) => {
        const num = Number(item);
        return Number.isFinite(num) ? num : null;
      })
      .filter((item): item is number => item !== null);
  };

  /** 稳定空数组，避免每次渲染新引用触发 select 重算 */
  const EMPTY_MULTI_VALUE: string[] = [];
  const overrideDisplayCache = new Map<string, string[]>();

  const getStableStringList = (cacheKey: string, next: string[]) => {
    const prev = overrideDisplayCache.get(cacheKey);
    if (prev
      && prev.length === next.length
      && prev.every((item, index) => item === next[index])) {
      return prev;
    }
    overrideDisplayCache.set(cacheKey, next);
    return next;
  };

  const getOverrideValue = (item: ConfigItem, rawName: string) => {
    const raw = item.default_values[rawName];
    if (raw === undefined || raw === null || raw === '') {
      return isArrayValueVar(rawName) ? EMPTY_MULTI_VALUE : '';
    }
    const cacheKey = `${item.key}::${rawName}`;
    // 下拉 option.id 为字符串，回显也统一转成字符串
    if (CANDIDATE_API_RAW_NAMES.has(rawName)) {
      return getStableStringList(cacheKey, normalizeCandidateIdsValue(raw).map(String));
    }
    if (isMultiSelectVar(rawName)) {
      return getStableStringList(cacheKey, normalizeMultiSelectValue(raw));
    }
    if (isTimeRangeVar(rawName)) {
      return getStableStringList(cacheKey, normalizeTimeRangeValue(raw));
    }
    if (isPersonSelectVar(rawName)) {
      return getStableStringList(cacheKey, normalizePersonSelectValue(raw));
    }
    if (isTagInputVar(rawName)) {
      return getStableStringList(cacheKey, normalizeMultiSelectValue(raw));
    }
    return raw;
  };

  /** 回显标签文案：优先候选项名称(id)，避免候选未加载时只显示裸 id */
  const getSelectedChoiceLabel = (rawName: string, value: string | number) => {
    const key = String(value);
    const choice = getMultiSelectChoices(rawName).find(item => item.key === key);
    return choice?.name || key;
  };

  /**
   * bk-tooltips 基于 bk-popper（非 tippy），content 传组件可渲染可滚动内层，
   * 避免把 overflow 写在 popper 根节点上导致箭头被裁切。
   */
  const getOverflowSelectedTipsContent = (
    rawName: string,
    selected: Array<{ value: string | number; label?: string | number }>,
  ) => {
    // 逗号拼接，块内自动换行
    const text = selected
      .slice(1)
      .map(item => getSelectedChoiceLabel(rawName, item.value))
      .join(', ');

    return defineComponent({
      name: 'OverrideSelectedTipsContent',
      setup() {
        return () => h('div', { class: 'override-selected-tips-list' }, text);
      },
    });
  };

  const handleRemoveSelectedValue = (
    item: ConfigItem,
    rawName: string,
    value: string | number,
  ) => {
    const current = normalizeMultiSelectValue(getOverrideValue(item, rawName));
    handleDefaultValueChange(
      item,
      rawName,
      current.filter(id => id !== String(value)),
    );
  };

  // 从第一步工具配置中读取参数原始默认值
  const getParamOriginalDefault = (rawName: string) => {
    const param = inputVariableList.value.find(v => v.raw_name === rawName);
    const emptyDefault = isArrayValueVar(rawName) ? [] : '';
    if (!param) return emptyDefault;

    const pickValue = () => {
      if (param.default_value !== undefined && param.default_value !== '') {
        return param.default_value;
      }
      if (param.raw_default_value !== undefined && param.raw_default_value !== '') {
        return param.raw_default_value;
      }
      return param.default_value ?? emptyDefault;
    };

    const value = pickValue();
    if (isTimeRangeVar(rawName)) return normalizeTimeRangeValue(value);
    if (isPersonSelectVar(rawName)) return normalizePersonSelectValue(value);
    if (isTagInputVar(rawName)) return normalizeMultiSelectValue(value);
    return value;
  };

  const applyCandidateList = (
    rawName: string,
    list: Array<{ id: number | string; name: string }>,
  ) => {
    candidatesMap.value = {
      ...candidatesMap.value,
      [rawName]: list.map(item => ({
        key: String(item.id),
        name: formatCandidateChoiceName(item.name, item.id),
      })),
    };
    candidatesFetchedSet.value = new Set([...candidatesFetchedSet.value, rawName]);
  };

  const fetchCandidates = async (rawName: string) => {
    if (!props.toolUid || !CANDIDATE_API_RAW_NAMES.has(rawName)) return;
    if (candidatesFetchedSet.value.has(rawName) || candidatesLoadingMap.value[rawName]) return;

    candidatesLoadingMap.value = {
      ...candidatesLoadingMap.value,
      [rawName]: true,
    };
    try {
      const list = await ToolManageService.fetchInputVariableCandidates({
        uid: props.toolUid,
        raw_name: rawName,
      });
      applyCandidateList(rawName, list || []);
    } catch {
      applyCandidateList(rawName, []);
    } finally {
      candidatesLoadingMap.value = {
        ...candidatesLoadingMap.value,
        [rawName]: false,
      };
    }
  };

  // 覆盖参数中出现需拉取候选的字段时请求接口
  watch(
    [() => props.toolUid, activeOverrideRawNames],
    () => {
      if (!props.toolUid) return;
      activeOverrideRawNames.value.forEach((rawName) => {
        if (CANDIDATE_API_RAW_NAMES.has(rawName)) {
          fetchCandidates(rawName);
        }
      });
    },
    { immediate: true, deep: true },
  );

  // 工具切换时清空候选缓存
  watch(() => props.toolUid, () => {
    candidatesMap.value = {};
    candidatesLoadingMap.value = {};
    candidatesFetchedSet.value = new Set();
    overrideDisplayCache.clear();
  });

  /** 已选覆盖参数的默认值必填：记录校验失败字段 */
  const invalidFields = ref<Record<string, true>>({});

  const getFieldErrorKey = (itemKey: string, rawName: string) => `${itemKey}::${rawName}`;

  const isFieldInvalid = (itemKey: string, rawName: string) => (
    !!invalidFields.value[getFieldErrorKey(itemKey, rawName)]
  );

  const isEmptyOverrideValue = (value: unknown): boolean => {
    if (value === undefined || value === null || value === '') return true;
    if (Array.isArray(value)) return value.length === 0;
    return false;
  };

  const clearFieldError = (itemKey: string, rawName: string) => {
    const key = getFieldErrorKey(itemKey, rawName);
    if (!invalidFields.value[key]) return;
    const next = { ...invalidFields.value };
    delete next[key];
    invalidFields.value = next;
  };

  const syncFieldError = (itemKey: string, rawName: string, value: unknown) => {
    // 仅在已有错误态时同步：有值则清除；提交校验前不主动标红
    if (!invalidFields.value[getFieldErrorKey(itemKey, rawName)]) return;
    if (!isEmptyOverrideValue(value)) {
      clearFieldError(itemKey, rawName);
    }
  };

  const pruneInvalidFields = (items: ConfigItem[]) => {
    const keys = Object.keys(invalidFields.value);
    if (!keys.length) return;
    const alive = new Set<string>();
    items.forEach((item) => {
      (item.override_keys || []).forEach((rawName) => {
        alive.add(getFieldErrorKey(item.key, rawName));
      });
    });
    const next: Record<string, true> = {};
    keys.forEach((key) => {
      if (alive.has(key)) next[key] = true;
    });
    if (Object.keys(next).length !== keys.length) {
      invalidFields.value = next;
    }
  };

  watch(configList, (list) => {
    pruneInvalidFields(list);
  });

  /** 提交前校验：已选覆盖参数的默认值不可为空；失败时滚到首个未填字段 */
  const validate = (): boolean => {
    const next: Record<string, true> = {};
    let firstInvalidKey = '';
    configList.value.forEach((item) => {
      (item.override_keys || []).forEach((rawName) => {
        if (isEmptyOverrideValue(item.default_values[rawName])) {
          const key = getFieldErrorKey(item.key, rawName);
          next[key] = true;
          if (!firstInvalidKey) {
            firstInvalidKey = key;
          }
        }
      });
    });
    invalidFields.value = next;
    if (!firstInvalidKey) {
      return true;
    }
    nextTick(() => {
      const el = Array.from(document.querySelectorAll('[data-override-field]'))
        .find(node => node.getAttribute('data-override-field') === firstInvalidKey) as HTMLElement | undefined;
      el?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
        inline: 'nearest',
      });
    });
    return false;
  };

  // 覆盖参数选择变更
  const handleOverrideChange = (item: ConfigItem, keys: string[]) => {
    // 清理不再选中的参数；新选中的参数自动代入第一步配置的默认值
    const newValues: Record<string, any> = {};
    const removedKeys = (item.override_keys || []).filter(k => !keys.includes(k));
    removedKeys.forEach(rawName => clearFieldError(item.key, rawName));
    for (const k of keys) {
      if (item.default_values[k] !== undefined) {
        newValues[k] = item.default_values[k];
      } else {
        newValues[k] = getParamOriginalDefault(k);
      }
      if (CANDIDATE_API_RAW_NAMES.has(k)) {
        fetchCandidates(k);
      }
      // 新选入有默认值时，清除此前校验错误
      syncFieldError(item.key, k, newValues[k]);
    }
    emitChange({
      key: item.key,
      override_keys: keys,
      default_values: newValues,
    });
  };

  // 移除单个覆盖参数
  const handleRemoveParam = (item: ConfigItem, rawName: string) => {
    const keys = item.override_keys.filter(k => k !== rawName);
    handleOverrideChange(item, keys);
  };

  // 默认值输入变更：显式 patch 后再 emit，避免 mutate computed item 后被重算覆盖
  const handleDefaultValueChange = (item: ConfigItem, rawName: string, value: any) => {
    const nextValues = { ...item.default_values };
    if (CANDIDATE_API_RAW_NAMES.has(rawName)) {
      nextValues[rawName] = normalizeCandidateIdsValue(value);
    } else if (isTimeRangeVar(rawName)) {
      // date-picker 首次选择可能发出非数组值，统一规范为数组
      nextValues[rawName] = normalizeTimeRangeValue(value);
    } else if (isPersonSelectVar(rawName)) {
      nextValues[rawName] = normalizePersonSelectValue(value);
    } else if (isTagInputVar(rawName)) {
      nextValues[rawName] = normalizeMultiSelectValue(value);
    } else {
      nextValues[rawName] = value;
    }
    overrideDisplayCache.delete(`${item.key}::${rawName}`);
    syncFieldError(item.key, rawName, nextValues[rawName]);
    emitChange({
      key: item.key,
      default_values: nextValues,
    });
  };

  /**
   * 解析 Excel 粘贴文本：按换行/制表符/逗号拆分名称或 ID
   */
  const parsePasteTokens = (text: string): string[] => {
    const tokens = text
      .split(/[\r\n\t,，;；]+/)
      .map(item => item.trim())
      .filter(Boolean);
    return [...new Set(tokens)];
  };

  /** 是否按批量粘贴处理（Excel 多行/多列，或多项分隔） */
  const isBatchPasteText = (text: string, tokens: string[]) => (
    /[\r\n\t]/.test(text) || tokens.length > 1
  );

  /**
   * 用粘贴 token 匹配候选项：支持 id、名称、名称(id)
   */
  const matchChoicesByTokens = (choices: CandidateChoice[], tokens: string[]) => {
    const matchedKeys = new Set<string>();
    const unmatched: string[] = [];

    tokens.forEach((token) => {
      const lower = token.toLowerCase();
      const parenMatch = token.match(/^(.*)\(([^)]+)\)$/);
      const found = choices.find((choice) => {
        if (choice.key === token || choice.key.toLowerCase() === lower) return true;
        if (choice.name === token || choice.name.toLowerCase() === lower) return true;
        const nameOnly = choice.name.replace(/\([^)]*\)$/, '').trim();
        if (nameOnly === token || nameOnly.toLowerCase() === lower) return true;
        if (parenMatch) {
          const [, namePart, idPart] = parenMatch;
          if (choice.key === idPart || choice.key.toLowerCase() === idPart.toLowerCase()) return true;
          if (nameOnly === namePart.trim() || nameOnly.toLowerCase() === namePart.trim().toLowerCase()) return true;
        }
        if (choice.name.endsWith(`(${token})`)) return true;
        return false;
      });

      if (found) {
        matchedKeys.add(found.key);
      } else {
        unmatched.push(token);
      }
    });

    return {
      matched: [...matchedKeys],
      unmatched,
    };
  };

  /** 清空下拉搜索词：同步 Vue v-model，避免过滤残留导致勾选项不可见 */
  const clearDefaultSelectSearch = () => {
    const input = document.querySelector('.bk-select-popover .bk-select-search-input') as HTMLInputElement | null;
    if (!input) return;
    const valueSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
    if (valueSetter) {
      valueSetter.call(input, '');
    } else {
      input.value = '';
    }
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  };

  /** 批量匹配并勾选；成功处理返回 true */
  let lastBatchKey = '';
  let lastBatchAt = 0;
  const applyBatchSelectByText = (item: ConfigItem, rawName: string, text: string) => {
    const normalized = String(text || '').trim();
    if (!normalized) return false;

    const tokens = parsePasteTokens(normalized);
    if (!isBatchPasteText(normalized, tokens) || tokens.length === 0) return false;

    // 粘贴与 search-change 可能连续触发，短时间去重
    const batchKey = `${item.key}::${rawName}::${normalized}`;
    const now = Date.now();
    if (batchKey === lastBatchKey && now - lastBatchAt < 800) return true;
    lastBatchKey = batchKey;
    lastBatchAt = now;

    const choices = getMultiSelectChoices(rawName);
    if (!choices.length) {
      messageWarn(t('选项尚未加载完成，请稍后重试'));
      return true;
    }

    const { matched, unmatched } = matchChoicesByTokens(choices, tokens);
    const current = normalizeMultiSelectValue(getOverrideValue(item, rawName));
    const currentSet = new Set(current);
    const newlyMatched = matched.filter(key => !currentSet.has(key));

    if (newlyMatched.length > 0) {
      const merged = [...new Set([...current, ...matched])];
      handleDefaultValueChange(item, rawName, merged);
      messageSuccess(t('已批量勾选 {n} 项', { n: newlyMatched.length }));
    } else if (matched.length > 0) {
      messageWarn(t('匹配项均已勾选'));
    }

    if (unmatched.length > 0) {
      const preview = unmatched.slice(0, 5).join('、');
      const suffix = unmatched.length > 5 ? '...' : '';
      messageWarn(t('未匹配 {n} 项：{list}', {
        n: unmatched.length,
        list: `${preview}${suffix}`,
      }));
    } else if (matched.length === 0) {
      messageWarn(t('未匹配到可勾选的选项'));
    }
    return true;
  };

  // 粘贴进搜索框后，bk-select 可能先写入搜索词；用 search-change 兜底批量勾选
  const applyingBatchSelect = ref(false);
  const handleDefaultSearchChange = (item: ConfigItem, rawName: string, val: string) => {
    if (applyingBatchSelect.value) return;
    if (!applyBatchSelectByText(item, rawName, val)) return;

    applyingBatchSelect.value = true;
    nextTick(() => {
      clearDefaultSelectSearch();
      // 再清一次，确保 Vue 内部 searchValue 与过滤状态复位
      nextTick(() => {
        clearDefaultSelectSearch();
        applyingBatchSelect.value = false;
      });
    });
  };

  /** 打开下拉时在 document 捕获粘贴，避免只绑到会被重建的 input */
  let activePasteTarget: { key: string; rawName: string } | null = null;
  let defaultSelectPasteCleanup: (() => void) | null = null;

  const resolveActiveConfigItem = (key: string) => configList.value.find(item => item.key === key);

  const handleDocumentPaste = (event: ClipboardEvent) => {
    if (!activePasteTarget) return;
    const target = event.target as HTMLElement | null;
    const isSelectSearch = !!target?.closest?.('.bk-select-popover')
      && (
        target.classList?.contains('bk-select-search-input')
        || !!target.closest?.('.bk-select-search-wrapper')
      );
    if (!isSelectSearch) return;

    const item = resolveActiveConfigItem(activePasteTarget.key);
    if (!item) return;

    const text = event.clipboardData?.getData('text/plain') || '';
    if (!applyBatchSelectByText(item, activePasteTarget.rawName, text)) return;

    event.preventDefault();
    event.stopPropagation();
    applyingBatchSelect.value = true;
    nextTick(() => {
      clearDefaultSelectSearch();
      nextTick(() => {
        clearDefaultSelectSearch();
        applyingBatchSelect.value = false;
      });
    });
  };

  const handleDefaultSelectToggle = (
    open: boolean,
    item: ConfigItem,
    rawName: string,
  ) => {
    defaultSelectPasteCleanup?.();
    defaultSelectPasteCleanup = null;
    activePasteTarget = null;
    if (!open) return;

    activePasteTarget = { key: item.key, rawName };
    document.addEventListener('paste', handleDocumentPaste, true);
    defaultSelectPasteCleanup = () => {
      document.removeEventListener('paste', handleDocumentPaste, true);
    };
  };

  onBeforeUnmount(() => {
    defaultSelectPasteCleanup?.();
    defaultSelectPasteCleanup = null;
    activePasteTarget = null;
  });

  // 向外发出变更；可带 patch，避免依赖已过期的 computed item 引用
  const emitChange = (patch?: {
    key: string;
    override_keys?: string[];
    default_values?: Record<string, any>;
  }) => {
    const normalizeParamDefaults = (values: Record<string, any>) => {
      const next: Record<string, any> = { ...values };
      Object.keys(next).forEach((rawName) => {
        if (isTimeRangeVar(rawName)) {
          next[rawName] = normalizeTimeRangeValue(next[rawName]);
        } else if (isPersonSelectVar(rawName)) {
          next[rawName] = normalizePersonSelectValue(next[rawName]);
        } else if (isTagInputVar(rawName)) {
          next[rawName] = normalizeMultiSelectValue(next[rawName]);
        }
      });
      return next;
    };

    const result: Record<string, SceneParamOverride> = {};
    for (const item of configList.value) {
      const isPatched = patch?.key === item.key;
      result[item.key] = {
        target_id: item.id,
        target_type: item.type,
        target_name: item.name,
        override_param_keys: isPatched && patch?.override_keys
          ? [...patch.override_keys]
          : [...item.override_keys],
        param_default_values: normalizeParamDefaults(isPatched && patch?.default_values
          ? { ...patch.default_values }
          : { ...item.default_values }),
      };
    }
    emit('update:paramOverrides', result);
  };

  defineExpose({
    validate,
  });
</script>

<style lang="postcss" scoped>
  .scene-param-config {
    --param-action-col-width: 50px;
    /* 参数名/显示名偏短，收窄以腾出默认值列宽，减少下拉选项截断 */
    --param-name-col-width: 18%;
    --param-display-col-width: 18%;

    margin-top: 16px;
  }

  .scene-param-config .render-field.is-two-col {
    --param-data-col-width: calc((100% - var(--param-action-col-width)) / 2);
  }

  .param-config-block {
    margin-bottom: 16px;
    overflow: hidden;
    background-color: #fafbfd;
    border: 1px solid #dcdee5;
    border-radius: 2px;

    &:last-child {
      margin-bottom: 0;
    }
  }

  .block-header {
    height: 42px;
    padding: 0 16px;
    font-size: 12px;
    font-weight: 600;
    line-height: 42px;
    color: #313238;
    background-color: #f0f1f5;
    box-shadow: 0 1px 0 0 #dcdee5;
  }

  .block-body {
    padding: 16px;
    background-color: #fafbfd;
  }

  .override-section {
    margin-bottom: 12px;

    .form-label {
      display: block;
      margin-bottom: 8px;
      font-size: 12px;
      line-height: 20px;
      color: #63656e;
    }

    /* 与下方表格参数名列同宽 */
    .form-control {
      width: var(--param-name-col-width);
      max-width: var(--param-name-col-width);
    }

    &.is-full-width .form-control {
      width: 100%;
      max-width: 100%;
    }
  }

  :deep(.override-param-select) {
    width: 100%;
    font-size: 12px;

    .bk-select-trigger {
      width: 100%;
    }

    /* 固定单行高度，保证 collapse-tags 能按换行计算 +n 溢出 */
    .bk-select-tag {
      width: 100%;
      height: 32px;
      max-height: 32px;
      min-height: 32px;
      overflow: hidden;
      font-size: 12px;
      background-color: #fff;
      border-color: #c4c6cc;
      box-sizing: border-box;
    }

    .bk-select-tag-input {
      font-size: 12px;

      &::placeholder {
        font-size: 12px;
      }
    }

    .bk-select-tag-wrapper {
      flex-wrap: wrap;
      gap: 4px;
      height: 30px;
      overflow: hidden;
    }

    .bk-tag {
      flex-shrink: 0;
      margin: 0;
      color: #63656e;
      background-color: #f0f1f5;
      border: 1px solid #dcdee5;
      border-radius: 2px;
    }

    .bk-select-overflow-tag {
      flex-shrink: 0;
      margin: 0;
      color: #63656e;
      background-color: #f0f1f5;
      border: 1px solid #dcdee5;
      border-radius: 2px;
    }
  }

  :deep(.override-default-multiselect) {
    width: 100%;
    height: 100%;
    line-height: normal;

    .bk-select-trigger {
      display: flex;
      width: 100%;
      height: 100%;
      align-items: center;
    }

    .bk-select-trigger .bk-select-tag,
    .bk-select-trigger .bk-select-tag:not(.collapse-tag) {
      display: flex;
      width: 100%;
      height: 42px !important;
      min-height: 42px !important;
      max-height: 42px !important;
      padding: 0 40px 0 10px;
      overflow: hidden;
      flex-wrap: nowrap;
      align-items: center;
      background-color: #fff;
      border: none;
      border-radius: 0;
      box-sizing: border-box;
    }

    .bk-select-trigger .bk-select-tag-wrapper {
      display: flex;
      gap: 4px;
      width: 100%;
      height: 100%;
      padding: 0;
      overflow: hidden;
      flex-wrap: nowrap;
      align-items: center;
    }

    .override-selected-tag,
    .bk-select-trigger .bk-select-tag .bk-tag {
      display: inline-flex;
      flex-shrink: 1;
      max-width: 160px;
      height: 22px;
      margin: 0;
      overflow: hidden;
      color: #63656e;
      text-overflow: ellipsis;
      white-space: nowrap;
      align-items: center;
      background-color: #f0f1f5;
      border: 1px solid #dcdee5;
      border-radius: 2px;
      box-sizing: border-box;
    }

    .override-selected-overflow-tag {
      display: inline-flex;
      flex-shrink: 0;
      height: 22px;
      margin: 0;
      color: #63656e;
      cursor: pointer;
      align-items: center;
      background-color: #f0f1f5;
      border: 1px solid #dcdee5;
      border-radius: 2px;
      box-sizing: border-box;
    }

    /* 关闭组件内置 +n，改用自定义 overflow tag */
    .bk-select-overflow-tag {
      display: none !important;
    }
  }

  /* 校验失败：默认值选择框红色边框（挂在单元格上，避免 select 根节点 class 合并丢失） */
  .field-row .col-default.is-error {
    :deep(.override-default-multiselect .bk-select-trigger .bk-select-tag),
    :deep(.override-default-multiselect .bk-select-trigger .bk-select-tag:not(.collapse-tag)) {
      border: 1px solid #ea3636 !important;
    }

    :deep(.bk-input) {
      border: 1px solid #ea3636 !important;
    }

    :deep(.override-time-range-picker),
    :deep(.override-time-picker),
    :deep(.bk-date-picker-editor),
    :deep(.override-person-select .bk-user-selector),
    :deep(.override-person-select .user-selector-container),
    :deep(.override-tag-input .bk-tag-input),
    :deep(.override-tag-input .bk-tag-input-container) {
      border: 1px solid #ea3636 !important;
    }
  }

  /* 下拉选项超出时 hover tips */
  :deep(.select-option-overflow),
  .select-option-overflow {
    display: block;
    flex: 1;
    min-width: 0;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .render-field {
    overflow: hidden;
    border: 1px solid #dcdee5;
    border-radius: 2px;
    user-select: none;
  }

  .field-header-row,
  .field-row {
    display: flex;
  }

  .col-name {
    flex: 0 0 var(--param-name-col-width);
    width: var(--param-name-col-width);
    max-width: var(--param-name-col-width);
    min-width: 0;
  }

  .col-display {
    flex: 0 0 var(--param-display-col-width);
    width: var(--param-display-col-width);
    max-width: var(--param-display-col-width);
    min-width: 0;
  }

  .col-default {
    flex: 1 1 0;
    min-width: 0;
  }

  .col-action {
    flex: 0 0 var(--param-action-col-width);
    width: var(--param-action-col-width);
  }

  .field-header-row {
    height: 42px;
    font-size: 12px;
    line-height: 40px;
    color: #313238;
    background: #f0f1f5;

    .col-name,
    .col-display,
    .col-default,
    .col-action {
      height: 42px;
      padding-left: 8px;
    }

    .col-display,
    .col-default,
    .col-action {
      border-left: 1px solid #dcdee5;
    }

    .col-action {
      background: #f0f1f5;
    }

    .col-default-label {
      display: inline-block;
      line-height: 20px;
    }

    .required-mark {
      display: inline-block;
      margin-left: 2px;
      font-size: 12px;
      line-height: 12px;
      color: #ea3636;
      vertical-align: top;
    }
  }

  .field-row {
    overflow: hidden;
    font-size: 12px;
    line-height: 42px;
    color: #63656e;
    border-right: 1px solid #dcdee5;
    border-bottom: 1px solid #dcdee5;
    transition: background-color .2s;

    &:hover {
      color: #313238;
      background: #eff5ff;
    }

    .col-name,
    .col-display,
    .col-default,
    .col-action {
      display: flex;
      height: 42px;
      overflow: hidden;
      align-items: center;
    }

    .col-name {
      background: #fafbfd;
    }

    .col-display {
      background: #fafbfd;
      border-left: 1px solid #dcdee5;
    }

    .col-default {
      background: #fff;
      border-left: 1px solid #dcdee5;
    }

    .col-action {
      background: #fafbfd;
      border-left: 1px solid #dcdee5;
    }
  }

  :deep(.field-row:hover .field-value) {
    background: #eff5ff !important;
  }

  :deep(.field-row:hover .bk-input),
  :deep(.field-row:hover .bk-input .bk-input--text),
  :deep(.field-row:hover .bk-input input) {
    color: #313238 !important;
    background: #eff5ff !important;
    border-color: transparent !important;
    transition: none !important;
  }

  :deep(.field-row:hover .override-time-range-picker),
  :deep(.field-row:hover .override-time-picker),
  :deep(.field-row:hover .bk-date-picker-editor),
  :deep(.field-row:hover .date-picker),
  :deep(.field-row:hover .date-picker-input) {
    color: #313238 !important;
    background: #eff5ff !important;
    border-color: transparent !important;
  }

  :deep(.field-row:hover .col-default.is-error .bk-input),
  :deep(.field-row:hover .col-default.is-error .bk-input .bk-input--text),
  :deep(.field-row:hover .col-default.is-error .bk-input input) {
    border-color: #ea3636 !important;
  }

  :deep(.field-row:hover .col-default.is-error .override-default-multiselect .bk-select-trigger .bk-select-tag) {
    border-color: #ea3636 !important;
  }

  :deep(.field-row:hover .col-default.is-error .override-time-range-picker),
  :deep(.field-row:hover .col-default.is-error .override-time-picker),
  :deep(.field-row:hover .col-default.is-error .bk-date-picker-editor) {
    border-color: #ea3636 !important;
  }

  :deep(.field-value) {
    .param-name-text {
      display: block;
      width: 100%;
      max-width: 100%;
      padding: 0 8px;
      overflow: hidden;
      font-size: 12px;
      line-height: 20px;
      color: #4d4f56;
      text-overflow: ellipsis;
      white-space: nowrap;
      box-sizing: border-box;
    }

    .bk-input {
      width: 100%;
      height: 42px !important;
      border: none;
      border-radius: 0;
    }

    .bk-input.is-focused:not(.is-readonly) {
      border: 1px solid #3a84ff;
      outline: 0;
      box-shadow: 0 0 3px #a3c5fd;
    }

    .bk-date-picker,
    .override-time-picker {
      width: 100%;
      height: 42px !important;
    }

    .bk-date-picker-editor {
      width: 100%;
      height: 42px !important;
      border: none;
      border-radius: 0;
    }

    .override-person-select,
    .override-tag-input {
      width: 100%;
      height: 42px !important;
    }

    .override-person-select :deep(.bk-user-selector),
    .override-person-select :deep(.user-selector-container),
    .override-tag-input :deep(.bk-tag-input),
    .override-tag-input :deep(.bk-tag-input-container) {
      width: 100%;
      min-height: 42px;
      border: none;
      border-radius: 0;
      box-sizing: border-box;
    }
  }

  .time-range-select-wrapper {
    width: 100%;
    height: 100%;
    min-height: 42px;
    cursor: pointer;

    .time-range-inner {
      position: relative;
      width: 100%;
      height: 100%;
    }

    .override-time-range-picker {
      width: 100%;
      height: 100%;
      min-height: 42px;

      :deep(.date-content),
      :deep(.date-picker-input) {
        width: 100%;
        height: 100%;
        min-height: 42px;
        cursor: pointer;
        border: none;
        border-radius: 0;
      }
    }

    .delete-fill-btn {
      position: absolute;
      top: 50%;
      right: 10px;
      z-index: 1;
      font-size: 14px;
      color: #c4c6cc;
      cursor: pointer;
      transform: translateY(-50%);

      &:hover {
        color: #979ba5;
      }
    }
  }

  .field-operation {
    justify-content: center;
    background: #fafbfd;
  }

  .field-header-row .field-operation {
    background: #f0f1f5;
  }

  .field-icon {
    font-size: 14px;
    color: #c4c6cc;
    cursor: pointer;

    &:hover {
      color: #ea3636;
    }
  }
</style>
<style lang="postcss">
  /* bk-tooltips 挂载到 body，类名打在 bk-popper 上；滚动放内层 list */
  .bk-popper.override-selected-tips-wrap {
    max-width: 360px;
    padding: 0;
  }

  .bk-popper.override-selected-tips-wrap .override-selected-tips-list {
    max-height: 300px;
    padding: 8px 12px;
    overflow-x: hidden;
    overflow-y: auto;
    font-size: 12px;
    line-height: 20px;
    word-break: break-all;
    white-space: normal;
    scrollbar-width: thin;
    scrollbar-color: #63656e transparent;
  }

  .bk-popper.override-selected-tips-wrap .override-selected-tips-list::-webkit-scrollbar {
    width: 4px;
  }

  .bk-popper.override-selected-tips-wrap .override-selected-tips-list::-webkit-scrollbar-thumb {
    background-color: #63656e;
    border-radius: 2px;
  }

  .bk-popper.override-selected-tips-wrap .override-selected-tips-list::-webkit-scrollbar-track {
    background: transparent;
  }
</style>
