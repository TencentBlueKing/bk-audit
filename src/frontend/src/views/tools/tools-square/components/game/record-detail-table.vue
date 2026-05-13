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
  <div
    class="record-detail-table"
    :class="{ 'simple-mode': simple }">
    <div
      v-if="title && !simple"
      class="detail-title">
      {{ title }}
    </div>
    <div
      v-if="!simple"
      class="detail-filter">
      <!-- 额外筛选控件插槽（放在最前） -->
      <slot name="extra-filter" />
      <bk-date-picker
        v-if="showDatePicker"
        v-model="localDateRange"
        class="date-picker"
        :clearable="false"
        :placeholder="t('最近半年')"
        :shortcut-selected-index="shortcutSelectedIndex"
        :shortcuts="dateShortcuts"
        type="daterange"
        use-shortcut-text
        @change="handleDateChange"
        @shortcut-change="handleShortcutChange" />
      <!-- 搜索框：点击弹出三段式筛选浮层 -->
      <div
        v-if="searchFields.length > 0"
        ref="searchBoxRef"
        class="search-condition-box"
        @click="handleBoxClick">
        <!-- 已生成的条件 tag -->
        <div
          v-for="(tag, index) in conditionTags"
          :key="index"
          v-bk-tooltips="{
            content: t('点击可编辑'),
            placement: 'top',
          }"
          class="condition-tag"
          @click.stop="handleEditTag(index)">
          <span class="tag-field">{{ tag.fieldName }}</span>
          <span class="tag-operator">{{ tag.operatorName }}</span>
          <span class="tag-value">{{ tag.value }}</span>
          <span
            class="tag-close"
            @click.stop="handleRemoveTag(index)">×</span>
        </div>
        <!-- placeholder -->
        <span
          v-if="conditionTags.length === 0"
          class="search-placeholder">
          {{ searchBoxPlaceholder }}
        </span>
        <!-- 搜索图标 -->
        <audit-icon
          class="search-icon"
          type="search1" />
        <!-- 三段式筛选浮层 -->
        <div
          v-if="showPopover"
          class="condition-popover"
          @click.stop>
          <bk-select
            v-model="selectedFieldId"
            class="field-select"
            :clearable="false"
            filterable
            :placeholder="t('请选择')"
            @change="handleFieldChange">
            <bk-option
              v-for="field in availableSearchFields"
              :id="field.id"
              :key="field.id"
              :name="field.name" />
          </bk-select>
          <bk-select
            v-model="selectedOperator"
            class="operator-select"
            :clearable="false"
            :placeholder="t('操作符')">
            <bk-option
              v-for="op in currentOperators"
              :id="op.id"
              :key="op.id"
              :name="op.name" />
          </bk-select>
          <!-- 枚举类型使用下拉选择 -->
          <bk-select
            v-if="currentFieldHasChildren"
            v-model="inputValue"
            class="value-input"
            :clearable="false"
            filterable
            :placeholder="t('多个值之间用逗号分隔')"
            @change="handleValueSelectChange">
            <bk-option
              v-for="child in currentFieldChildren"
              :id="child.id"
              :key="child.id"
              :name="child.name" />
          </bk-select>
          <!-- 普通文本输入 -->
          <bk-input
            v-else
            v-model="inputValue"
            class="value-input"
            :placeholder="t('多个值之间用逗号分隔')"
            @enter="handleConfirm" />
          <bk-button
            class="confirm-btn"
            theme="primary"
            @click="handleConfirm">
            {{ t('确定') }}
          </bk-button>
        </div>
      </div>
      <!-- 无 searchFields 时降级为普通搜索框 -->
      <bk-input
        v-else
        v-model="localKeyword"
        class="search-input"
        :placeholder="searchPlaceholder"
        right-icon="bk-icon icon-search"
        type="search"
        @enter="handleSearch" />
    </div>
    <bk-table
      :columns="processedColumns"
      :data="data"
      :pagination="simple ? false : localPagination"
      stripe
      @page-limit-change="handlePageLimitChange"
      @page-value-change="handlePageChange" />
  </div>
</template>

<script setup lang="ts">
  import {
    computed, onBeforeUnmount, onMounted, ref, watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type { SearchFieldItem } from './game-search-fields';

  // 条件 tag 数据结构
  interface ConditionTag {
    fieldId: string;      // 字段ID
    fieldName: string;    // 字段显示名
    operator: string;     // 操作符ID
    operatorName: string; // 操作符显示名
    value: string;        // 值
  }

  interface Props {
    title?: string;
    columns: Array<Record<string, any>>;
    data: Array<Record<string, any>>;
    pagination?: {
      count: number;
      current: number;
      limit: number;
    };
    searchPlaceholder?: string;
    showDatePicker?: boolean;
    simple?: boolean;
    initialDateRange?: [string, string];
    searchFields?: SearchFieldItem[];
    /**
     * 外部注入的搜索条件 tags（例如饼图图例点击联动）
     * 传入后会覆盖表格内部的 conditionTags，实现双向同步
     */
    externalConditions?: ConditionTag[];
  }
  const props = withDefaults(defineProps<Props>(), {
    title: '',
    pagination: undefined,
    searchPlaceholder: '',
    showDatePicker: true,
    simple: false,
    initialDateRange: () => ['', ''],
    searchFields: () => [],
    externalConditions: () => [],
  });

  const emit = defineEmits<{
    'page-change': [page: number];
    'page-limit-change': [limit: number];
    'search': [keyword: string];
    'date-change': [range: [string, string]];
    'search-condition-change': [conditions: ConditionTag[]];
  }>();

  const { t } = useI18n();

  // 本地分页：使用前端分页，让 bk-table 自身管理 sort/filter/pagination
  // count 始终跟随当前 data 长度（已经过外部 searchConditions 过滤后的数据）
  const localPagination = computed(() => ({
    count: props.data?.length || 0,
    current: props.pagination?.current || 1,
    limit: props.pagination?.limit || 10,
  }));

  // 通用比较器：优先按数字 / 时间戳比较，否则退化为字符串本地比较
  const compareValues = (a: any, b: any): number => {
    // null / undefined / '' 统一视为最小
    const isEmpty = (v: any) => v === null || v === undefined || v === '';
    if (isEmpty(a) && isEmpty(b)) return 0;
    if (isEmpty(a)) return -1;
    if (isEmpty(b)) return 1;

    // 纯数字
    const numA = Number(a);
    const numB = Number(b);
    if (!Number.isNaN(numA) && !Number.isNaN(numB)
      && String(a).trim() !== '' && String(b).trim() !== '') {
      return numA - numB;
    }

    // 时间字符串：用 Date.parse 尝试解析
    const tA = Date.parse(String(a));
    const tB = Date.parse(String(b));
    if (!Number.isNaN(tA) && !Number.isNaN(tB)) {
      return tA - tB;
    }

    // 字符串
    return String(a).localeCompare(String(b));
  };

  // 处理列定义：
  // 1. 将 filter: true 自动展开为 { list, filterFn }（list 来源于当前 data 中该列所有非空唯一值）
  //    这样点击表头筛选图标时才能展示候选项，而不是出现"暂无数据"
  // 2. 将 sort: true 自动展开为 { sortFn }，使用通用比较器（兼容数字、时间、字符串），
  //    避免 bk-table 默认的字符串字典序对"赠送时间"等格式不友好导致点击无效
  // 3. 其他属性（render 等）原样保留
  const processedColumns = computed(() => (props.columns || []).map((col) => {
    const next: Record<string, any> = { ...col };

    // 处理 filter
    if (col.filter === true && col.field) {
      const field = col.field as string;
      const valueSet = new Set<string>();
      (props.data || []).forEach((row) => {
        const v = row?.[field];
        if (v !== null && v !== undefined && v !== '') {
          valueSet.add(String(v));
        }
      });
      const list = Array.from(valueSet).map(v => ({ text: v, value: v }));
      next.filter = {
        list,
        filterFn: (checked: string[], row: Record<string, any>) => {
          if (!checked || checked.length === 0) return true;
          return checked.includes(String(row?.[field] ?? ''));
        },
      };
    }

    // 处理 sort：提供显式 sortFn，确保点击表头排序立即生效
    if (col.sort === true && col.field) {
      const field = col.field as string;
      next.sort = {
        sortFn: (rowA: Record<string, any>, rowB: Record<string, any>, type: 'asc' | 'desc' | 'null') => {
          if (type === 'null') return 0;
          const r = compareValues(rowA?.[field], rowB?.[field]);
          return type === 'desc' ? -r : r;
        },
      };
    }

    return next;
  }));

  // 默认操作符（文本类型）
  const defaultConditions = [
    { id: 'like', name: t('包含') },
    { id: 'eq', name: t('等于') },
    { id: 'neq', name: t('不等于') },
    { id: 'in', name: 'IN' },
    { id: 'not_in', name: 'NOT IN' },
  ];

  // 日期快捷选项
  interface DateShortcut {
    text: string;
    value: () => [Date, Date];
  }
  const dateShortcuts: DateShortcut[] = [
    {
      text: t('最近一周'),
      value: () => {
        const end = new Date();
        const start = new Date();
        start.setDate(start.getDate() - 7);
        return [start, end];
      },
    },
    {
      text: t('最近一个月'),
      value: () => {
        const end = new Date();
        const start = new Date();
        start.setMonth(start.getMonth() - 1);
        return [start, end];
      },
    },
    {
      text: t('最近三个月'),
      value: () => {
        const end = new Date();
        const start = new Date();
        start.setMonth(start.getMonth() - 3);
        return [start, end];
      },
    },
    {
      text: t('最近半年'),
      value: () => {
        const end = new Date();
        const start = new Date();
        start.setMonth(start.getMonth() - 6);
        return [start, end];
      },
    },
    {
      text: t('最近一年'),
      value: () => {
        const end = new Date();
        const start = new Date();
        start.setFullYear(start.getFullYear() - 1);
        return [start, end];
      },
    },
  ];
  // 默认选中"最近半年"（index = 3）
  const shortcutSelectedIndex = ref(3);

  // 计算默认日期范围（最近半年）
  const getDefaultDateRange = (): [Date, Date] => dateShortcuts[3].value();

  // 若外部未传入 initialDateRange，则使用最近半年作为默认值
  const computeInitialRange = (): [Date | string, Date | string] => {
    const [s, e] = props.initialDateRange || ['', ''];
    if (s && e) return [s, e];
    return getDefaultDateRange();
  };

  const localDateRange = ref<[Date | string, Date | string]>(computeInitialRange());
  const localKeyword = ref('');

  // 三段式搜索状态
  const searchBoxRef = ref<HTMLElement | null>(null);
  const showPopover = ref(false);
  const selectedFieldId = ref('');
  const selectedOperator = ref('');
  const inputValue = ref('');
  const conditionTags = ref<ConditionTag[]>([]);
  const editingIndex = ref(-1); // -1 表示新增模式

  // 搜索框 placeholder（显示所有可搜索字段名）
  const searchBoxPlaceholder = computed(() => {
    const names = props.searchFields.map(f => f.name).join('、');
    return `${t('搜索')} ${names}`;
  });

  // 可用的搜索字段（剔除已选条件中的字段，编辑模式下保留当前编辑的字段）
  const availableSearchFields = computed(() => {
    const usedFieldIds = conditionTags.value
      .filter((_, idx) => idx !== editingIndex.value) // 编辑模式下排除当前编辑的 tag
      .map(tag => tag.fieldId);
    return props.searchFields.filter(f => !usedFieldIds.includes(f.id));
  });

  // 当前选中字段的配置
  const currentField = computed(() => props.searchFields.find(f => f.id === selectedFieldId.value));

  // 当前字段的操作符列表
  const currentOperators = computed(() => {
    if (currentField.value?.conditions?.length) {
      return currentField.value.conditions;
    }
    return defaultConditions;
  });

  // 当前字段是否有枚举子选项
  const currentFieldHasChildren = computed(() => !!(currentField.value?.children?.length
    && currentField.value?.onlyRecommendChildren));

  // 当前字段的子选项
  const currentFieldChildren = computed(() => currentField.value?.children || []);

  // 初始化默认选中第一个字段
  watch(() => props.searchFields, (fields) => {
    if (fields.length > 0 && !selectedFieldId.value) {
      selectedFieldId.value = fields[0].id;
    }
  }, { immediate: true });

  // 同步外部注入的搜索条件（例如饼图联动传入的条件）到表格内部的 conditionTags
  // 实现联动：点击饼图图例 -> 父组件计算出搜索条件 -> 传入表格 -> tag 渲染到搜索框
  watch(() => props.externalConditions, (val) => {
    const next = Array.isArray(val) ? val : [];
    // 浅比较避免不必要的赋值导致 watch 循环
    const sameLen = next.length === conditionTags.value.length;
    const sameContent = sameLen && next.every((tag, idx) => {
      const cur = conditionTags.value[idx];
      return cur && cur.fieldId === tag.fieldId
        && cur.operator === tag.operator
        && cur.value === tag.value;
    });
    if (!sameContent) {
      conditionTags.value = next.map(tag => ({ ...tag }));
    }
  }, { immediate: true, deep: true });

  // 字段变化时，重置操作符为该字段的默认操作符
  const handleFieldChange = () => {
    const operators = currentOperators.value;
    if (operators.length > 0) {
      selectedOperator.value = operators[0].id;
    }
    inputValue.value = '';
  };

  // 初始化默认操作符
  watch(currentOperators, (ops) => {
    if (ops.length > 0 && !selectedOperator.value) {
      selectedOperator.value = ops[0].id;
    }
  }, { immediate: true });

  // 点击搜索框，显示浮层
  const handleBoxClick = () => {
    if (!showPopover.value) {
      showPopover.value = true;
      editingIndex.value = -1;
      // 自动选中第一个可用字段
      if (availableSearchFields.value.length > 0) {
        const currentAvailable = availableSearchFields.value.find(f => f.id === selectedFieldId.value);
        if (!currentAvailable) {
          selectedFieldId.value = availableSearchFields.value[0].id;
          handleFieldChange();
        }
      }
    }
  };

  // 点击外部关闭浮层
  const handleClickOutside = (e: MouseEvent) => {
    if (
      searchBoxRef.value
      && !searchBoxRef.value.contains(e.target as Node)
    ) {
      showPopover.value = false;
      editingIndex.value = -1;
    }
  };

  onMounted(() => {
    document.addEventListener('click', handleClickOutside);
  });
  onBeforeUnmount(() => {
    document.removeEventListener('click', handleClickOutside);
  });

  // 枚举值选择变化
  const handleValueSelectChange = () => {
    // 选择后不自动确认，等用户点击确定
  };

  // 确定按钮
  const handleConfirm = () => {
    if (
      !selectedFieldId.value
      || !selectedOperator.value
      || !inputValue.value
    ) {
      return;
    }
    const field = currentField.value;
    const operator = currentOperators.value.find(op => op.id === selectedOperator.value);
    if (!field || !operator) return;

    const tag: ConditionTag = {
      fieldId: field.id,
      fieldName: field.name,
      operator: operator.id,
      operatorName: operator.name,
      value: inputValue.value,
    };

    if (editingIndex.value >= 0) {
      // 编辑模式：替换已有 tag
      conditionTags.value[editingIndex.value] = tag;
      editingIndex.value = -1;
    } else {
      // 新增模式
      conditionTags.value.push(tag);
    }

    // 重置输入并关闭浮层
    inputValue.value = '';
    showPopover.value = false;
    emitConditions();
  };

  // 删除 tag
  const handleRemoveTag = (index: number) => {
    conditionTags.value.splice(index, 1);
    if (editingIndex.value === index) {
      editingIndex.value = -1;
    }
    emitConditions();
  };

  // 点击 tag 进入编辑模式
  const handleEditTag = (index: number) => {
    const tag = conditionTags.value[index];
    selectedFieldId.value = tag.fieldId;
    showPopover.value = true;
    // 等字段变化后再设置操作符和值
    setTimeout(() => {
      selectedOperator.value = tag.operator;
      inputValue.value = tag.value;
      editingIndex.value = index;
    });
  };

  // 触发条件变化事件
  const emitConditions = () => {
    emit('search-condition-change', [...conditionTags.value]);
  };

  const handlePageChange = (page: number) => {
    emit('page-change', page);
  };

  const handlePageLimitChange = (limit: number) => {
    emit('page-limit-change', limit);
  };

  const handleSearch = () => {
    emit('search', localKeyword.value);
  };

  const handleDateChange = (val: [string, string]) => {
    emit('date-change', val);
  };

  // 快捷选项变化
  const handleShortcutChange = (value: { text: string; value: () => [Date, Date] }, index: number) => {
    shortcutSelectedIndex.value = index;
    if (value && typeof value.value === 'function') {
      const range = value.value();
      localDateRange.value = range;
    }
  };
</script>

<style scoped lang="postcss">
.record-detail-table {
  padding: 16px;
  background: #fff;
  border-radius: 2px;

  .detail-title {
    margin-bottom: 12px;
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    color: #313238;
  }

  .detail-filter {
    display: flex;
    gap: 12px;
    margin-bottom: 12px;

    .date-picker {
      width: 200px;
    }

    .search-input {
      flex: 1;
    }
  }

  .search-condition-box {
    position: relative;
    display: flex;
    flex: 1;
    flex-wrap: wrap;
    gap: 4px;
    align-items: center;
    height: 32px;
    padding: 0 32px 0 10px;
    cursor: pointer;
    background: #fff;
    border: 1px solid #c4c6cc;
    border-radius: 2px;

    &:hover {
      border-color: #979ba5;
    }

    .search-placeholder {
      overflow: hidden;
      font-size: 12px;
      color: #c4c6cc;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .search-icon {
      position: absolute;
      top: 50%;
      right: 10px;
      font-size: 14px;
      color: #979ba5;
      pointer-events: none;
      transform: translateY(-50%);
    }

    .condition-tag {
      display: inline-flex;
      gap: 2px;
      align-items: center;
      height: 22px;
      padding: 0 4px;
      font-size: 12px;
      line-height: 22px;
      cursor: pointer;
      background: #f0f1f5;
      border-radius: 2px;

      &:hover {
        background: #e1ecff;
      }

      .tag-field {
        color: #3a84ff;
      }

      .tag-operator {
        color: #ff9c01;
      }

      .tag-value {
        color: #3a84ff;
      }

      .tag-close {
        margin-left: 4px;
        font-size: 14px;
        font-style: normal;
        line-height: 1;
        color: #979ba5;
        cursor: pointer;

        &:hover {
          color: #3a84ff;
        }
      }
    }

    .condition-popover {
      position: absolute;
      top: calc(100% + 4px);
      left: 0;
      z-index: 999;
      display: flex;
      gap: 0;
      align-items: center;
      padding: 8px;
      background: #fff;
      border-radius: 2px;
      box-shadow: 0 2px 6px 0 rgb(0 0 0 / 10%);

      .field-select {
        width: 140px;
        flex-shrink: 0;
      }

      .operator-select {
        width: 100px;
        flex-shrink: 0;
        margin-left: 8px;
      }

      .value-input {
        width: 200px;
        flex-shrink: 0;
        margin-left: 8px;
      }

      .confirm-btn {
        flex-shrink: 0;
        margin-left: 8px;
      }
    }
  }

  /* simple 模式下去掉内边距，让外部容器控制 */
  &.simple-mode {
    padding: 0;
    background: transparent;
  }
}
</style>
