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

    <!-- 条件标签区域 + 添加条件 + 操作按钮 -->
    <div class="nl-search-condition-area">
      <!-- 解析后的条件标签 -->
      <condition-tags
        :field-config="fieldConfig"
        :search-model="searchModel"
        @clear-all="handleClear"
        @remove="handleRemoveCondition"
        @update="handleUpdateCondition" />

      <!-- 事件字段条件列表 -->
      <div
        v-if="selectedItemList.length > 0"
        class="nl-event-filters">
        <div
          v-for="item in selectedItemList"
          :key="item.id"
          class="event-filter-item">
          <div class="filter-item-label">
            <span>{{ `${item.display_name}[${item.field_name}]` }}</span>
            <audit-icon
              class="close-btn"
              type="close"
              @click="handleRemoveEventField(item.id)" />
          </div>
          <div class="filter-item-value">
            <bk-select
              v-model="item.operator"
              class="bk-select"
              :clearable="false"
              :placeholder="t('请选择')"
              style="width: 150px; padding-right: 5px;"
              @change="handleOperatorChange(item)">
              <bk-option
                v-for="condition in conditionList"
                :id="condition.id"
                :key="condition.id"
                :name="condition.name" />
            </bk-select>
            <bk-tag-input
              v-if="item.operator === 'IN' || item.operator === 'NOT IN'"
              v-model="item.value"
              allow-create
              collapse-tags
              has-delete-icon
              :list="[]"
              :paste-fn="pasteFn"
              :placeholder="t('请输入并按回车键结束')"
              style="width: 100%;"
              @change="(val: any) => handleEventValueChange(val, item)" />
            <bk-input
              v-else
              v-model="item.value"
              :placeholder="t('')" />
          </div>
        </div>
      </div>

      <!-- 添加条件 + 操作按钮 -->
      <div class="nl-search-actions">
        <add-condition
          :event-fields="selectedItems"
          :field-config="fieldConfig"
          :selected-event-field-ids="selectedVal"
          :selected-fields="selectedFieldNames"
          @add-event-field="handleAddEventField"
          @add-field="handleAddField"
          @remove-event-field="handleRemoveEventField" />

        <div class="nl-search-buttons">
          <bk-button
            class="mr8"
            theme="primary"
            @click="handleSubmit">
            {{ t('查询') }}
          </bk-button>
          <bk-button
            class="mr8"
            @click="handleClear">
            {{ t('重置') }}
          </bk-button>
          <bk-button
            v-if="isReassignment"
            class="mr8"
            @click="handleBatch">
            {{ t('批量转单') }}
          </bk-button>
          <bk-button
            v-if="isExport"
            class="mr8"
            :loading="isExportLoading"
            @click="handleExport">
            {{ t('批量导出') }}
          </bk-button>
        </div>
      </div>
    </div>

    <!-- NLP 解析结果提示 -->
    <div
      v-if="parseMessage"
      class="nl-search-tips">
      <audit-icon
        style="margin-right: 4px; color: #3a84ff;"
        type="info" />
      <span>{{ parseMessage }}</span>
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

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';
  import useUrlSearch from '@hooks/use-url-search';

  import type { IFieldConfig } from '@components/search-box/components/render-field-config/config';

  import AddCondition from './components/add-condition.vue';
  import ConditionTags from './components/condition-tags.vue';
  import NlInput from './components/nl-input.vue';
  import useNLParse from './hooks/use-nl-parse';
  import type { INLSearchBoxExposes } from './types';

  interface Emits {
    (e: 'change', value: Record<string, any>, otherValue?: any, isClear?: boolean): void;
    (e: 'export'): void;
    (e: 'batch'): void;
    (e: 'modelValueWatch', value: Record<string, any>): void;
  }
  interface Props {
    fieldConfig: Record<string, IFieldConfig>;
    isReassignment?: boolean;
    isExport?: boolean;
  }

  const props = withDefaults(defineProps<Props>(), {
    isReassignment: false,
    isExport: false,
  });
  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const nlInputRef = ref();
  const isExportLoading = ref(false);

  // ========================
  // URL 参数同步（与 search-box 保持一致）
  // ========================
  const {
    getSearchParamsPost,
    replaceSearchParams,
  } = useUrlSearch();
  const urlSearchParams = getSearchParamsPost('event_filters');

  // ========================
  // 搜索模型（与 search-box 完全一致的数据结构）
  // ========================
  const searchModel = ref<Record<string, any>>({
    datetime: [
      dayjs(Date.now() - (86400000 * 182)).format('YYYY-MM-DD'),
      dayjs().format('YYYY-MM-DD'),
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

  // ========================
  // 事件字段相关（与 search-box 完全一致）
  // ========================
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

  const pasteFn = (value: string) => ([{ id: value, name: value }]);

  // ========================
  // NLP 自然语言解析
  // ========================
  const {
    isParsing,
    parseMessage,
    parse,
    clearParseResult,
  } = useNLParse(props.fieldConfig);

  // 自然语言搜索提交
  const handleNLSubmit = async (query: string) => {
    const conditions = await parse(query);
    if (!conditions) return;

    // 将 NLP 解析结果合并到 searchModel
    // 先重置非 datetime 字段
    const newModel: Record<string, any> = {
      datetime: searchModel.value.datetime,
      datetime_origin: searchModel.value.datetime_origin,
    };

    // 合并解析出的条件
    Object.entries(conditions).forEach(([key, value]) => {
      if (key === 'datetime' || key === 'datetime_origin') {
        newModel[key] = value;
      } else if (props.fieldConfig[key]) {
        newModel[key] = value;
      }
    });

    searchModel.value = newModel;

    // 通知父组件字段变化（用于获取事件字段）
    emit('modelValueWatch', searchModel.value);

    // 触发搜索
    handleSubmit();
  };

  // ========================
  // 手动添加/编辑/删除条件
  // ========================
  // 添加风险字段条件
  const handleAddField = (fieldName: string, config: IFieldConfig) => {
    if (searchModel.value[fieldName] !== undefined) {
      // 已存在，移除
      const newModel = { ...searchModel.value };
      delete newModel[fieldName];
      searchModel.value = newModel;
    } else {
      // 添加默认空值
      let defaultValue: any = '';
      if (config.type === 'select') {
        defaultValue = [];
      } else if (config.type === 'datetimerange') {
        defaultValue = [
          dayjs(Date.now() - (86400000 * 182)).format('YYYY-MM-DD'),
          dayjs().format('YYYY-MM-DD'),
        ];
      } else if (config.type === 'user-selector') {
        defaultValue = [];
      }
      searchModel.value = {
        ...searchModel.value,
        [fieldName]: defaultValue,
      };
    }
  };

  // 移除单个条件
  const handleRemoveCondition = (fieldName: string) => {
    const newModel = { ...searchModel.value };
    delete newModel[fieldName];
    searchModel.value = newModel;
    handleSubmit();
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
        searchModel.value.datetime_origin = formatted;
      }
    } else {
      searchModel.value[fieldName] = value;
    }
  };

  // ========================
  // 事件字段操作（与 search-box 一致）
  // ========================
  const handleOperatorChange = (val: Record<string, any>) => {
    const isNewOperatorInOrNotIn = val.operator === 'IN' || val.operator === 'NOT IN';
    const currentItem = selectedItemListOperator.value.find((item: Record<string, any>) => item.id === val.id);
    const isOldOperatorInOrNotIn = currentItem?.operator === 'IN' || currentItem?.operator === 'NOT IN';

    selectedItemList.value = selectedItemList.value.map((item) => {
      if (item.id === val.id) {
        if (isOldOperatorInOrNotIn && isNewOperatorInOrNotIn) {
          return { ...item, operator: val.operator, value: item.value };
        } if (isOldOperatorInOrNotIn && !isNewOperatorInOrNotIn) {
          return { ...item, operator: val.operator, value: '' };
        } if (!isOldOperatorInOrNotIn && isNewOperatorInOrNotIn) {
          return { ...item, operator: val.operator, value: [] };
        }
        return { ...item, operator: val.operator, value: item.value };
      }
      return item;
    });
    selectedItemListOperator.value = selectedItemList.value.map(item => ({
      id: item.id,
      operator: item.operator,
    }));
  };

  const handleEventValueChange = (val: any[], changeItem: Record<string, any>) => {
    let processedVal = val;
    if (Array.isArray(val)) {
      const flattenedValues: any[] = [];
      val.forEach((item) => {
        if (typeof item === 'string' && item.includes(',')) {
          const splitItems = item.split(',').map(s => s.trim())
            .filter(s => s !== '');
          flattenedValues.push(...splitItems);
        } else {
          flattenedValues.push(item);
        }
      });
      processedVal = [...new Set(flattenedValues)];
    }

    selectedItemList.value = selectedItemList.value.map((item) => {
      if (item.id === changeItem.id) {
        return { ...item, value: processedVal };
      }
      return item;
    });
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

  // ========================
  // 搜索参数序列化（与 search-box 完全一致）
  // ========================
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
    emit('change', getSearchParams(), eventFiltersParams.value, isClear);
  };

  // 重置
  const handleClear = () => {
    searchModel.value = {
      datetime: [
        dayjs(Date.now() - (86400000 * 182)).format('YYYY-MM-DD'),
        dayjs().format('YYYY-MM-DD'),
      ],
      datetime_origin: [
        'now-6M',
        'now',
      ],
    };
    selectedItemList.value = selectedItemList.value.map(item => ({
      ...item,
      value: '',
      operator: '=',
    }));
    selectedVal.value = selectedItemList.value.map(item => item.id);
    clearParseResult();
    nlInputRef.value?.clear();
    handleSubmit(true);
  };

  // 批量转单
  const handleBatch = () => {
    emit('batch');
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

  const handleExport = () => {
    emit('export');
  };

  const handleExportData = (val: string[], type: string) => {
    isExportLoading.value = true;
    batchExport({ risk_ids: val, risk_view_type: type }).finally(() => {
      isExportLoading.value = false;
    });
  };

  // ========================
  // URL 事件字段初始化（与 search-box 一致）
  // ========================
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

  // ========================
  // Expose（与 search-box 完全一致的对外接口）
  // ========================
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

    .nl-event-filters {
      display: grid;
      margin-bottom: 12px;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px 16px;

      .event-filter-item {
        .filter-item-label {
          display: flex;
          align-items: center;
          justify-content: space-between;
          width: 100%;
          font-size: 12px;
          line-height: 20px;
          color: #63656e;

          .close-btn {
            color: #63656e;
            cursor: pointer;
          }
        }

        .filter-item-value {
          display: flex;
          padding-top: 6px;
        }
      }
    }

    .nl-search-actions {
      display: flex;
      align-items: center;
      justify-content: space-between;

      .nl-search-buttons {
        display: flex;
        align-items: center;
      }
    }

    .nl-search-tips {
      position: relative;
      z-index: 1;
      display: flex;
      padding: 8px 16px;
      font-size: 12px;
      color: #63656e;
      background: #f5f7fa;
      border-top: 1px solid #f0f1f5;
      align-items: center;
    }
  }
</style>
