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
  <div class="nl-search-box">
    <!-- 智能搜索标题 -->
    <div class="nl-search-header">
      <img
        class="nl-search-header-icon"
        src="@/images/aixiaojing.svg">
      <span class="nl-search-header-title">{{ t('智能搜索') }}</span>
    </div>

    <!-- 自然语言搜索输入框 -->
    <nl-input
      ref="nlInputRef"
      :loading="isParsing"
      @submit="handleNLSubmit" />

    <!-- NLP 解析结果提示（未识别搜索条件时的红色警告提示） -->
    <div
      v-if="showParseWarning"
      class="nl-search-warning-tips">
      <div class="nl-search-warning-content">
        <img
          class="nl-search-warning-icon"
          src="@/images/info.svg">
        <span>{{ t('未识别到有效搜索条件，请输入责任人、风险等级、处理状态等关键词') }}</span>
      </div>
      <audit-icon
        class="nl-search-warning-close"
        type="close"
        @click="handleCloseWarning" />
    </div>

    <!-- 条件标签区域 -->
    <div class="nl-search-condition-area">
      <!-- 解析后的条件标签  -->
      <condition-tags
        :condition-list="conditionList"
        :event-field-items="selectedItemList"
        :field-config="fieldConfig"
        :search-model="searchModel"
        @clear-all="handleClear"
        @finish-edit="handleConditionFinishEdit"
        @remove="handleRemoveCondition"
        @remove-event-field="handleRemoveEventField"
        @start-edit="handleConditionStartEdit"
        @update="handleUpdateCondition"
        @update-event-operator="handleUpdateEventOperator"
        @update-event-value="handleUpdateEventValue">
        <add-condition
          :event-fields="selectedItems"
          :field-config="fieldConfig"
          :selected-event-field-ids="selectedVal"
          :selected-fields="selectedFieldNames"
          @add-event-field="handleAddEventField"
          @add-field="handleAddField"
          @remove-event-field="handleRemoveEventField" />
      </condition-tags>
    </div>
  </div>
</template>
<script setup lang="ts">
  import dayjs from 'dayjs';
  import _ from 'lodash';
  import {
    computed,
    onMounted,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';
  import RiskManageService from '@service/risk-manage';
  import StrategyManageService from '@service/strategy-manage';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';
  import useUrlSearch from '@hooks/use-url-search';

  import type { IFieldConfig } from '@components/search-box/components/render-field-config/config';

  import AddCondition from './components/add-condition.vue';
  import ConditionTags from './components/condition-tags.vue';
  import NlInput from './components/nl-input.vue';
  import useNLParse from './hooks/use-nl-parse';
  import type { INLSearchBoxExposes } from './types';

  const props = defineProps<Props>();

  const emit = defineEmits<Emits>();


  interface Emits {
    (e: 'change', value: Record<string, any>, otherValue?: any, isClear?: boolean): void;
    (e: 'export'): void;
    (e: 'batch'): void;
    (e: 'modelValueWatch', value: Record<string, any>): void;
    (e: 'parsing', value: boolean): void;
  }
  interface Props {
    fieldConfig: Record<string, IFieldConfig>;
  }

  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const nlInputRef = ref();
  // URL 参数同步（与 search-box 保持一致）
  const {
    getSearchParamsPost,
    replaceSearchParams,
  } = useUrlSearch();
  const urlSearchParams = getSearchParamsPost('event_filters');
  // 搜索模型（与 search-box 完全一致的数据结构）
  const searchModel = ref<Record<string, any>>({
    datetime: [
      dayjs(Date.now() - (86400000 * 182)).format('YYYY-MM-DD HH:mm:ss'),
      dayjs().format('YYYY-MM-DD HH:mm:ss'),
    ],
    datetime_origin: [
      'now-6M',
      'now',
    ],
  });

  // 解析 URL 上面附带的查询参数（与 search-box 一致）
  const normalizeParamArray = (value: unknown) => {
    if (_.isArray(value)) {
      return value.map(item => (item === null ? '' : item.toString())).filter(item => item !== '');
    }
    if (value === null || value === '') {
      return [];
    }
    return value?.toString().split(',');
  };

  Object.keys(urlSearchParams).forEach((searchFieldName) => {
    const config = props.fieldConfig[searchFieldName];
    if (!config) return;
    if (urlSearchParams[searchFieldName] === undefined
      || urlSearchParams[searchFieldName] === null
      || urlSearchParams[searchFieldName] === '') return;
    if (config.type !== 'string') {
      searchModel.value[searchFieldName] = normalizeParamArray(urlSearchParams[searchFieldName]);
    } else {
      const value = urlSearchParams[searchFieldName];
      searchModel.value[searchFieldName] = value === null ? '' : value.toString();
    }
  });
  if (urlSearchParams.start_time && urlSearchParams.end_time) {
    searchModel.value.datetime = [urlSearchParams.start_time, urlSearchParams.end_time];
  }
  if (urlSearchParams.datetime_origin) {
    searchModel.value.datetime_origin = normalizeParamArray(urlSearchParams.datetime_origin);
  }

  // 事件字段相关（与 search-box 完全一致）
  const selectedVal = ref<string[]>([]);
  const selectedItems = ref<Array<Record<string, any>>>([]);
  const selectedItemList = ref<Array<Record<string, any>>>([]);
  const selectedItemListOperator = ref<Array<Record<string, any>>>([]);

  const {
    data: GlobalChoices,
  } = useRequest(MetaManageService.fetchGlobalChoices, {
    defaultValue: {},
    manual: true,
  });

  const conditionList = computed(() => GlobalChoices.value.event_filter_operator);

  const eventFiltersParams = computed(() => selectedItemList.value.map(item => ({
    field: item.field_name,
    display_name: item.display_name,
    operator: item.operator,
    value: _.isArray(item.value) ? item.value.join(',') : item.value,
  })));

  // 当前已选择的风险字段名列表（用于 add-condition 组件判断哪些已选中）
  const selectedFieldNames = computed(() => Object.keys(searchModel.value).filter(key => key !== 'datetime_origin' && props.fieldConfig[key]));

  // 生成当前搜索条件的快照字符串
  const takeSearchSnapshot = () => JSON.stringify({
    model: searchModel.value,
    eventFilters: selectedItemList.value.map(item => ({
      id: item.id,
      operator: item.operator,
      value: item.value,
    })),
  });
  // 编辑开始前的快照
  let editSnapshot = '';

  // 获取风险标签和策略列表（用于传给 nl2risk_filter 接口）
  const {
    data: riskTagsList,
  } = useRequest(RiskManageService.fetchRiskTags, {
    defaultParams: {
      page: 1,
      page_size: 200,
    },
    defaultValue: [],
    manual: true,
  });

  const {
    data: strategyList,
  } = useRequest(StrategyManageService.fetchAllStrategyList, {
    manual: true,
    defaultValue: [],
  });

  // NLP 自然语言解析
  const {
    isParsing,
    parse,
    clearParseResult,
  } = useNLParse();

  // 是否显示未识别警告提示
  const showParseWarning = ref(false);

  // 关闭警告提示
  const handleCloseWarning = () => {
    showParseWarning.value = false;
  };

  /**
   * 将 filter_conditions 中的字段映射到 searchModel
   * filter_conditions 的结构与 ListRisk 接口请求参数一致
   */

  // 字段转换类型：wrap-array 单值包数组, split-array 逗号分隔转数组, direct 直接赋值, bool-array 布尔转字符串数组
  type FieldTransform = 'wrap-array' | 'split-array' | 'direct' | 'bool-array';

  // 字段映射表：字段名 → 转换类型
  const fieldTransformMap: Record<string, FieldTransform> = {
    risk_level: 'split-array',
    status: 'split-array',
    operator: 'split-array',
    current_operator: 'split-array',
    notice_users: 'split-array',
    risk_label: 'split-array',
    strategy_id: 'split-array',
    tags: 'split-array',
    // 直接赋值的字段
    risk_id: 'direct',
    event_content: 'direct',
    title: 'direct',
    // 布尔值转字符串数组的字段
    has_report: 'bool-array',
  };

  // 根据转换类型对字段值进行转换
  const transformFieldValue = (value: any, transform: FieldTransform) => {
    switch (transform) {
    case 'wrap-array':
      return [value];
    case 'split-array':
      return value.split(',').map((id: string) => id.trim());
    case 'direct':
      return value;
    case 'bool-array':
      return [String(value)];
    default:
      return value;
    }
  };

  const applyFilterConditions = (filterConditions: Record<string, any>) => {
    // 先重置 searchModel，保留默认日期
    const newModel: Record<string, any> = {
      datetime: searchModel.value.datetime,
      datetime_origin: searchModel.value.datetime_origin,
    };

    // 处理时间范围
    if (filterConditions.start_time || filterConditions.end_time) {
      const startTime = filterConditions.start_time
        ? dayjs(filterConditions.start_time).format('YYYY-MM-DD')
        : newModel.datetime[0];
      const endTime = filterConditions.end_time
        ? dayjs(filterConditions.end_time).format('YYYY-MM-DD')
        : newModel.datetime[1];
      newModel.datetime = [startTime, endTime];
      newModel.datetime_origin = [startTime, endTime];
    }

    // 批量处理映射表中的字段
    Object.entries(fieldTransformMap).forEach(([field, transform]) => {
      const value = filterConditions[field];
      // has_report 为布尔值，需要用 undefined 判断；其他字段用 truthiness 判断
      const hasValue = transform === 'bool-array' ? value !== undefined : Boolean(value);
      if (hasValue) {
        newModel[field] = transformFieldValue(value, transform);
      }
    });

    searchModel.value = newModel;

    // 处理事件字段筛选 event_filters
    if (Array.isArray(filterConditions.event_filters)) {
      selectedItemList.value = filterConditions.event_filters.map((ef: any) => ({
        id: `${ef.field}:${ef.display_name}`,
        field_name: ef.field,
        display_name: ef.display_name,
        operator: ef.operator,
        value: (() => {
          const isInOperator = ef.operator === 'IN' || ef.operator === 'NOT IN';
          if (isInOperator && typeof ef.value === 'string') {
            return ef.value.split(',');
          }
          return ef.value;
        })(),
      }));
      selectedVal.value = selectedItemList.value.map(item => item.id);
      selectedItemListOperator.value = selectedItemList.value.map(item => ({
        id: item.id,
        operator: item.operator,
      }));
    } else {
      // API 未返回 event_filters 时，清空上次的事件字段条件
      selectedItemList.value = [];
      selectedVal.value = [];
      selectedItemListOperator.value = [];
    }

    // 处理排序 sort
    if (Array.isArray(filterConditions.sort)) {
      newModel.sort = filterConditions.sort;
    }
  };

  // 自然语言搜索提交
  const handleNLSubmit = async (query: string) => {
    // 通知父组件：NL 解析开始，列表进入 loading 状态
    emit('parsing', true);

    // 构建 tags 参数
    const tags = riskTagsList.value
      .filter((item: any) => item && item.id && item.name)
      .map((item: any) => ({ id: Number(item.id), name: item.name }));

    // 构建 strategies 参数
    const strategies = strategyList.value
      .filter((item: any) => item && (item.value || item.id))
      .map((item: any) => ({
        id: Number(item.value || item.id),
        name: item.label || item.name || '',
      }));

    const result = await parse(query, tags, strategies);
    if (!result) {
      // 解析失败，取消列表 loading
      emit('parsing', false);
      return;
    }

    const { filterConditions, message } = result;

    // AI 服务异常或无法理解：filter_conditions 为空，message 有值
    if (_.isEmpty(filterConditions) && message) {
      // 显示警告提示（红色警告提示框）
      showParseWarning.value = true;
      // 解析结果为空，取消列表 loading
      emit('parsing', false);
      return;
    }

    // AI 正常解析：filter_conditions 有值
    if (!_.isEmpty(filterConditions)) {
      // 隐藏之前的警告提示
      showParseWarning.value = false;

      // 将 filter_conditions 填充到筛选表单
      applyFilterConditions(filterConditions);

      // 通知父组件字段变化（用于获取事件字段）
      emit('modelValueWatch', searchModel.value);

      // 触发搜索（列表 loading 会由 fetchData 接管，无需手动取消）
      handleSubmit();

      // 弹出搜索成功 Message 提示
      messageSuccess(t('智能搜索成功'));
    } else {
      // 兜底：条件为空且无 message，取消列表 loading
      emit('parsing', false);
    }
  };

  // ========================
  // 手动添加/编辑/删除条件
  // ========================
  // 添加风险字段条件（已添加的字段不会出现在下拉列表中，因此仅做添加）
  const handleAddField = (fieldName: string, config: IFieldConfig) => {
    // 添加默认空值
    let defaultValue: any = '';
    if (config.type === 'select') {
      defaultValue = [];
    } else if (config.type === 'datetimerange') {
      defaultValue = [
        dayjs(Date.now() - (86400000 * 182)).format('YYYY-MM-DD HH:mm:ss'),
        dayjs().format('YYYY-MM-DD HH:mm:ss'),
      ];
    } else if (config.type === 'user-selector') {
      defaultValue = [];
    }
    searchModel.value = {
      ...searchModel.value,
      [fieldName]: defaultValue,
    };
  };

  // 移除单个条件
  const handleRemoveCondition = (fieldName: string) => {
    const newModel = { ...searchModel.value };
    delete newModel[fieldName];
    searchModel.value = newModel;
    handleSubmit();
  };
  // 标签开始编辑时记录快照
  const handleConditionStartEdit = () => {
    editSnapshot = takeSearchSnapshot();
  };

  // 更新单个条件值（条件标签编辑态提交）
  // 注意：使用直接属性赋值而非展开运算符，避免 searchModel 引用变化导致 popover 重渲染关闭
  const handleUpdateCondition = (fieldName: string, value: any) => {
    if (fieldName === 'datetime') {
      // 日期字段：bk-date-picker 返回格式化的日期字符串数组
      if (Array.isArray(value) && value.length >= 2) {
        const formatted = value.map((item: any) => (
          typeof item === 'number' || item instanceof Date
            ? dayjs(item).format('YYYY-MM-DD')
            : item
        ));
        searchModel.value.datetime = formatted;
        // 手动选择具体日期时，datetime_origin 设为具体日期（非快捷选项）
        searchModel.value.datetime_origin = formatted;
      }
    } else if (fieldName === 'datetime_origin') {
      // 快捷选项变更时同步 datetime_origin（如 ['now-6M', 'now']）
      searchModel.value.datetime_origin = value;
    } else {
      searchModel.value[fieldName] = value;
    }
    // 仅更新数据，不触发搜索，等待编辑面板关闭时统一触发
  };

  // 编辑面板关闭时统一触发搜索（仅在值实际变化时才触发）
  const handleConditionFinishEdit = () => {
    const currentSnapshot = takeSearchSnapshot();
    if (currentSnapshot === editSnapshot) {
      // 条件值未发生变化，跳过搜索
      return;
    }
    // 通知父组件字段变化（用于获取事件字段）
    emit('modelValueWatch', searchModel.value);
    handleSubmit();
  };

  // 事件字段操作（与 search-box 一致）
  // 事件字段标签 —— 更新操作符
  const handleUpdateEventOperator = (id: string, operator: string) => {
    handleOperatorChange({ id, operator });
    // 仅更新数据，不触发搜索，等待编辑面板关闭时统一触发
  };

  // 事件字段标签 —— 更新值
  const handleUpdateEventValue = (id: string, value: any) => {
    selectedItemList.value = selectedItemList.value.map((item) => {
      if (item.id === id) {
        return { ...item, value };
      }
      return item;
    });
    // 仅更新数据，不触发搜索，等待编辑面板关闭时统一触发
  };

  const handleOperatorChange = (val: Record<string, any>) => {
    const isNewOperatorInOrNotIn = val.operator === 'IN' || val.operator === 'NOT IN';
    const currentItem = selectedItemListOperator.value.find((item: Record<string, any>) => item.id === val.id);
    const isOldOperatorInOrNotIn = currentItem?.operator === 'IN' || currentItem?.operator === 'NOT IN';

    selectedItemList.value = selectedItemList.value.map((item) => {
      if (item.id === val.id) {
        let newValue = item.value;
        if (isOldOperatorInOrNotIn && !isNewOperatorInOrNotIn) {
          newValue = '';
        } else if (!isOldOperatorInOrNotIn && isNewOperatorInOrNotIn) {
          newValue = [];
        }
        return { ...item, operator: val.operator, value: newValue };
      }
      return item;
    });
    selectedItemListOperator.value = selectedItemList.value.map(item => ({
      id: item.id,
      operator: item.operator,
    }));
  };


  const handleAddEventField = (item: Record<string, any>) => {
    selectedItemList.value.push({
      ...item,
      value: '',
      operator: '=',
    });
    selectedVal.value = selectedItemList.value.map(i => i.id);
    selectedItemListOperator.value = selectedItemList.value.map(i => ({
      id: i.id,
      operator: i.operator,
    }));
  };

  const handleRemoveEventField = (id: string) => {
    selectedItemList.value = selectedItemList.value.filter(item => item.id !== id);
    selectedVal.value = selectedItemList.value.map(item => item.id);
    const EventFiltersParams = {
      ...getSearchParams(),
      event_filters: eventFiltersParams.value,
    };
    replaceSearchParams(EventFiltersParams);
  };

  // 搜索参数序列化（与 search-box 完全一致）
  const allText = t('全部');
  const normalizeSearchArray = (value: Array<string | number>) => (
    value
      .map(item => (item === null ? '' : item.toString()))
      .filter(item => item !== '' && item !== allText)
  );

  const getSearchParams = () => {
    const result = Object.keys(searchModel.value).reduce((res, key) => {
      const value = searchModel.value[key];
      if (key === 'datetime') {
        return {
          ...res,
          start_time: value[0],
          end_time: value[1],
        };
      }
      if (value === allText) return res;
      if (!_.isEmpty(value)) {
        if (_.isArray(value)) {
          const normalized = normalizeSearchArray(value);
          if (normalized.length === 0) return res;
          return {
            ...res,
            [key]: normalized.join(','),
          };
        }
        return {
          ...res,
          [key]: value,
        };
      }
      return res;
    }, {} as Record<string, any>);
    return result;
  };

  // 提交搜索
  const handleSubmit = (isClear = false) => {
    // 将搜索参数同步到 URL（刷新后可恢复）
    const searchParams = getSearchParams();
    const replaceUrl: Record<string, any> = { ...searchParams };
    // 同步 datetime_origin
    if (searchModel.value.datetime_origin) {
      const origin = searchModel.value.datetime_origin;
      if (Array.isArray(origin) && origin.length > 0) {
        replaceUrl.datetime_origin = origin.join(',');
      }
    }
    // 同步 event_filters
    if (eventFiltersParams.value.length > 0) {
      replaceUrl.event_filters = eventFiltersParams.value;
    }
    replaceSearchParams(replaceUrl);

    emit('change', searchParams, eventFiltersParams.value, isClear);
  };

  // 重置
  const handleClear = () => {
    searchModel.value = {
      datetime: [
        dayjs(Date.now() - (86400000 * 182)).format('YYYY-MM-DD HH:mm:ss'),
        dayjs().format('YYYY-MM-DD HH:mm:ss'),
      ],
      datetime_origin: [
        'now-6M',
        'now',
      ],
    };
    selectedItemList.value = [];
    selectedItemListOperator.value = [];
    selectedVal.value = [];
    showParseWarning.value = false;
    clearParseResult();
    nlInputRef.value?.clear();
    // 清空 URL 上的搜索参数
    replaceSearchParams({});
    handleSubmit(true);
  };


  // 导出
  const {
    run: batchExport,
  } = useRequest(RiskManageService.batchExport, {
    defaultValue: [],
    onSuccess() {
      messageSuccess(t('导出成功'));
    },
  });

  const handleExportData = (val: string[], type: string) => {
    batchExport({ risk_ids: val, risk_view_type: type });
  };

  // URL 事件字段初始化（与 search-box 一致）
  const findIdByDisplayAndField = (display: string, field: string, ary: Array<Record<string, any>>) => {
    const foundItem = ary.find(item => item
      && item.display_name === display
      && item.field_name === field);
    return foundItem ? foundItem.id : null;
  };

  watch(() => selectedItems.value, (val) => {
    selectedVal.value = eventFiltersParams.value.map((item) => {
      const foundId = findIdByDisplayAndField(item.display_name, item.field, val);
      return foundId;
    });
  });

  onMounted(() => {
    if (urlSearchParams?.event_filters) {
      selectedItemList.value = urlSearchParams?.event_filters?.map((item: Record<string, any>) => ({
        id: item.id ? item.id : `${item.field}:${item.display_name}`,
        field_name: item.field,
        display_name: item.display_name,
        operator: item.operator,
        value: (item.operator === 'IN' || item.operator === 'NOT IN') ? item.value.split(',') : item.value,
      }));
      selectedItemListOperator.value = urlSearchParams?.event_filters?.map((item: Record<string, any>) => ({
        id: item.id ? item.id : `${item.field}:${item.display_name}`,
        operator: item.operator,
      }));
    }
    handleSubmit();
  });

  // Expose（与 search-box 完全一致的对外接口）
  defineExpose<INLSearchBoxExposes>({
    clearValue() {
      handleClear();
    },
    exportData(val, type) {
      handleExportData(val, type);
    },
    initSelectedItems(val) {
      selectedItems.value = val;
    },
    getSelectedItemList() {
      return selectedItemList.value;
    },
    getConditionTags() {
      // 计算当前的条件标签列表，与condition-tags组件中的逻辑保持一致
      const datetimeTags: any[] = [];
      const otherTags: any[] = [];

      // 先处理 datetime 类型（始终展示且排第一）
      Object.entries(props.fieldConfig).forEach(([fieldName, config]) => {
        if (config.type === 'datetimerange') {
          const value = searchModel.value[fieldName] || searchModel.value.datetime || [];
          datetimeTags.push({
            fieldName,
            label: config.label,
            value,
            type: config.type,
            config,
            removable: false, // 日期类型标签不可删除
          });
        }
      });

      // 其他字段：按 searchModel 中 key 的顺序遍历，确保新添加的字段排在最后
      Object.keys(searchModel.value).forEach((fieldName) => {
        // 跳过辅助字段和 datetime 类型
        if (fieldName === 'datetime' || fieldName === 'datetime_origin' || fieldName === 'sort') return;
        const config = props.fieldConfig[fieldName];
        if (!config) return;
        if (config.type === 'datetimerange') return;

        const value = searchModel.value[fieldName];
        otherTags.push({
          fieldName,
          label: config.label,
          value: (value !== undefined && value !== null) ? value : '',
          type: config.type,
          config,
          removable: true, // 可删除
        });
      });

      // 日期标签排第一，其余按 searchModel 中的添加顺序
      return [...datetimeTags, ...otherTags];
    },
  });
</script>
<style lang="postcss">
  .nl-search-box {
    position: relative;
    overflow: hidden;
    background: linear-gradient(90deg, #edeeff 54.99%, #ebe7ff 94.25%);
    border-radius: 8px;
    box-shadow: 0 2px 4px 0 rgb(25 25 41 / 5%);

    /* 右上角下层半圆色块 */
    &::before {
      position: absolute;
      top: -90px;
      right: 60px;
      width: 214px;
      height: 167px;
      pointer-events: none;
      background: radial-gradient(48.2% 48.2% at 74.55% 49.7%, #5392ff 0%, #eae8ff 100%);
      border-radius: 52.8px;
      content: '';
      opacity: 100%;
      filter: blur(12px);
    }

    /* 右上角上层半圆色块 */
    &::after {
      position: absolute;
      top: -127px;
      right: -30px;
      width: 193.54px;
      height: 154.6px;
      pointer-events: none;
      background: linear-gradient(135.4deg, #9e8bff 33.62%, #db82fe 89.39%);
      border-radius: 72.8px;
      content: '';
      opacity: 100%;
      filter: blur(16px);
      transform: rotate(307deg);
    }

    .nl-search-header {
      position: relative;
      z-index: 1;
      display: flex;
      padding: 16px 24px 0;
      align-items: center;

      .nl-search-header-icon {
        width: 24px;
        height: 24px;
        margin-right: 6px;
      }

      .nl-search-header-title {
        font-size: 16px;
        font-weight: 700;
        line-height: 22px;
        color: #313238;
      }
    }

    .nl-search-condition-area {
      position: relative;
      z-index: 1;
      padding: 0 24px 16px;
    }

    .nl-search-warning-tips {
      position: relative;
      z-index: 1;
      display: flex;
      padding: 6px 8px;
      margin: 0 24px 8px;
      font-size: 12px;
      color: #4d4f56;
      background: #ffeded;
      border: 1px solid #f8b4b4;
      border-radius: 2px;
      align-items: center;
      justify-content: space-between;

      .nl-search-warning-content {
        display: flex;
        align-items: center;
        flex: 1;
      }

      .nl-search-warning-icon {
        width: 14px;
        height: 14px;
        margin-right: 4px;
        flex-shrink: 0;
      }

      .nl-search-warning-close {
        margin-left: 8px;
        font-size: 14px;
        color: #979ba5;
        cursor: pointer;
        flex-shrink: 0;
        transition: color .15s;

        &:hover {
          color: #63656e;
        }
      }
    }
  }
</style>
