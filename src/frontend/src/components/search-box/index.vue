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
  <div class="analysis-search-box">
    <keep-alive>
      <component
        :is="renderComponent"
        ref="searchRef"
        v-model="searchModel"
        :field-config="fieldConfig"
        @clear="handleClear"
        @model-value-watch="handleUpdateModelValue"
        @submit="handleSubmit">
        <template #button>
          <bk-button
            v-if="isReassignment"
            class="mr8"
            @click="handleBatch">
            {{ t('批量转单') }}
          </bk-button>
          <bk-button
            v-if="isExport"
            class="mr8"
            :loading="isLoading"
            @click="handleExport">
            {{ t('批量导出') }}
          </bk-button>
        </template>
        <template #more-list>
          <div class="box-row">
            <div
              v-for="item in selectedItemList"
              :key="item.id"
              class="more-list-item">
              <div class="list-item-lable">
                <span class="item-label">{{ `${item.display_name}[${item.field_name}]` }}</span>
                <audit-icon
                  class="close-btn"
                  type="close"
                  @click="handleRemove(item.id)" />
              </div>
              <div class="item-value">
                <bk-select
                  v-model="item.operator"
                  class="bk-select"
                  :clearable="false"
                  :placeholder="t('请选择')"
                  style="width: 150px;padding-right: 5px;"
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
                  @change="(val: any) => handleValueChange(val, item)" />
                <bk-input
                  v-else
                  v-model="item.value"
                  :placeholder="t('')" />
              </div>
            </div>
          </div>
        </template>
        <template #more-button>
          <bk-select
            ref="selectRef"
            v-model="selectedVal"
            :auto-height="false"
            collapse-tags
            display-key="name"
            filterable
            id-key="id"
            multiple
            :popover-options="{
              'width': 'auto',
              extCls: 'add-search-tree-pop',
              boundary: 'document.body'
            }"
            @change="handleSelectChange">
            <template #trigger>
              <span style="color: #3884ff; cursor: pointer;">
                <audit-icon
                  style="margin-right: 5px;"
                  type="add" />
                <span>{{ t('添加关联事件条件') }}</span>
              </span>
            </template>
            <bk-option
              v-for="item in selectedItems"
              :id="item.id"
              :key="item.id"
              :name="`${item.display_name}[${item.field_name}]`" />
          </bk-select>
        </template>
      </component>
    </keep-alive>
    <div
      class="panel-toggle-btn"
      :class="{
        'is-floded': renderType === 'value'
      }"
      @click="handleRenderTypeChange">
      <audit-icon type="angle-line-up" />
    </div>
  </div>
</template>
<script setup lang="ts">
  import dayjs from 'dayjs';
  import _ from 'lodash';
  import {
    computed,
    // nextTick,
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

  import type { IFieldConfig } from './components/render-field-config/config';
  // import FieldConfig from './components/render-field-config/config';
  import RenderKey from './components/render-key.vue';
  import RenderValue from './components/render-value/index.vue';

  interface Emits {
    (e: 'change', value: Record<string, any>, otherValue?: any, isClear?: boolean): void;
    (e: 'changeTableHeight'): void;
    (e: 'export'): void;
    (e: 'batch'): void;
    (e: 'modelValueWatch', value: Record<string, any>): void;
  }
  interface Props {
    fieldConfig: Record<string, IFieldConfig>;
    isReassignment?: boolean,
    isExport?: boolean,
  }
  interface Exposes {
    clearValue: () => void;
    exportData: (val: string[], type: string) => void;
    initSelectedItems:(val: Array< Record<string, any>>) => void;
    getSelectedItemList: (val: Array< Record<string, any>>) => void;
  }


  const props = withDefaults(defineProps<Props>(), {
    isReassignment: false,
    isExport: false,
  });
  const emit = defineEmits<Emits>();


  const searchRef = ref();
  const SEARCH_TYPE_QUERY_KEY = 'searchType';
  const { t } = useI18n();
  const isLoading = ref(false);
  const comMap = {
    key: RenderKey,
    value: RenderValue,
  };
  const { messageSuccess } = useMessage();
  const selectedVal = ref();
  const selectedItems = ref<Array<Record<string, any>>>([]);
  const selectedItemList = ref<Array<Record<string, any>>>([]);
  const {
    getSearchParamsPost,
    appendSearchParams,
    replaceSearchParams,
  } = useUrlSearch();
  const urlSearchParams = getSearchParamsPost('event_filters');

  const conditionList = computed(() => GlobalChoices.value.event_filter_operator);
  const eventFiltersParams = computed(() => {
    const data = selectedItemList.value.map(item => ({
      field: item.field_name,
      display_name: item.display_name,
      operator: item.operator,
      // 判断 item.value 是否是数组
      value: _.isArray(item.value) ? item.value.join(',') : item.value,
    }));
    return data;
  });

  const selectedItemListOperator = ref();

  const {
    data: GlobalChoices,
  } = useRequest(MetaManageService.fetchGlobalChoices, {
    defaultValue: {},
    manual: true,
  });
  const handleOperatorChange = (val: Record<string, any>) => {
    const isNewOperatorInOrNotIn = val.operator === 'IN' || val.operator === 'NOT IN';
    // 找到当前项的操作符
    const currentItem = selectedItemListOperator.value.find((item: Record<string, any>) => item.id === val.id);
    const isOldOperatorInOrNotIn = currentItem.operator === 'IN' || currentItem.operator === 'NOT IN';

    selectedItemList.value = selectedItemList.value.map((item) => {
      if (item.id === val.id) {
        if (isOldOperatorInOrNotIn && isNewOperatorInOrNotIn) {
          return {
            ...item,
            operator: val.operator,
            value: item.value,
          };
        } if (isOldOperatorInOrNotIn && !isNewOperatorInOrNotIn) {
          return {
            ...item,
            operator: val.operator,
            value: '',
          };
        } if (!isOldOperatorInOrNotIn && isNewOperatorInOrNotIn) {
          return {
            ...item,
            operator: val.operator,
            value: [],
          };
        }
        return {
          ...item,
          operator: val.operator,
          value: item.value,
        };
      }
      return item;
    });
    selectedItemListOperator.value = selectedItemList.value.map(item => ({
      id: item.id,
      operator: item.operator,
    }));
  };
  const pasteFn = (value: string) => ([{ id: value, name: value }]);
  // 删除
  const handleRemove = (val: string) => {
    // 使用filter删除指定项目，filter会保持剩余元素的相对顺序
    selectedItemList.value = selectedItemList.value.filter(item => item.id !== val);
    selectedVal.value = selectedItemList.value.map(item => item.id);
    const EventFiltersParams = {
      ...getSearchParams(),
      event_filters: eventFiltersParams.value,
    };
    replaceSearchParams(EventFiltersParams);
  };
  // 更多选项 选择
  const handleSelectChange = (val: string[]) => {
    // 按照勾选顺序构建新的列表并去重
    const newSelectedItemList = [];
    const seenIds = new Set();

    for (const id of val) {
      if (seenIds.has(id)) continue; // 去重

      const item = selectedItems.value.find(item => item.id === id);
      if (item) {
        const existingItem = selectedItemList.value.find(existing => existing.id === id);
        newSelectedItemList.push({
          ...item,
          value: existingItem?.value || '',
          operator: existingItem?.operator || '=',
        });
        seenIds.add(id);
      }
    }

    selectedItemList.value = newSelectedItemList;
    selectedItemListOperator.value = newSelectedItemList.map((item: Record<string, any>) => ({
      id: item.id,
      operator: item.operator,
    }));
  };
  const renderType = ref<keyof typeof comMap>('key');
  if (comMap[urlSearchParams[SEARCH_TYPE_QUERY_KEY] as keyof typeof comMap]) {
    renderType.value = urlSearchParams[SEARCH_TYPE_QUERY_KEY] as keyof typeof comMap;
  }

  const renderComponent = computed(() => comMap[renderType.value]);
  // 转单
  const handleBatch = () => {
    emit('batch');
  };
  // 批量导出
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
    isLoading.value = true;
    batchExport({ risk_ids: val, risk_view_type: type }).finally(() => {
      isLoading.value = false;
    });
  };


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

  const normalizeParamArray = (value: unknown) => {
    if (_.isArray(value)) {
      return value.map(item => (item == null ? '' : item.toString())).filter(item => item !== '');
    }
    if (value == null || value === '') {
      return [];
    }
    return value.toString().split(',');
  };
  // 解析 url 上面附带的查询参数
  Object.keys(urlSearchParams).forEach((searchFieldName) => {
    const config = props.fieldConfig[searchFieldName];
    if (!config) {
      return;
    }
    if (urlSearchParams[searchFieldName] === undefined
      || urlSearchParams[searchFieldName] === null
      || urlSearchParams[searchFieldName] === '') return;
    if (config.type !== 'string') {
      searchModel.value[searchFieldName] = normalizeParamArray(urlSearchParams[searchFieldName]);
    } else {
      const value = urlSearchParams[searchFieldName];
      searchModel.value[searchFieldName] = value == null ? '' : value.toString();
    }
  });
  if (urlSearchParams.start_time && urlSearchParams.end_time) {
    searchModel.value.datetime = [urlSearchParams.start_time, urlSearchParams.end_time];
  }
  if (urlSearchParams.datetime_origin) {
    searchModel.value.datetime_origin = normalizeParamArray(urlSearchParams.datetime_origin);
  }

  const handleRenderTypeChange = () => {
    renderType.value = renderType.value === 'key' ? 'value' : 'key';
    appendSearchParams({
      [SEARCH_TYPE_QUERY_KEY]: renderType.value,
    });
  };
  const allText = t('全部');
  const normalizeSearchArray = (value: Array<string | number>) => (
    value
      .map(item => (item == null ? '' : item.toString()))
      .filter(item => item !== '' && item !== allText)
  );
  const getSearchParams = () => {
    const result = Object.keys(searchModel.value).reduce((result, key) => {
      const value = searchModel.value[key];
      if (key === 'datetime') {
        return {
          ...result,
          start_time: value[0],
          end_time: value[1],
        };
      }
      if (value === allText) {
        return result;
      }
      if (!_.isEmpty(value)) {
        if (_.isArray(value)) {
          const normalized = normalizeSearchArray(value);
          if (normalized.length === 0) {
            return result;
          }
          return {
            ...result,
            [key]: normalized.join(','),
          };
        }
        return {
          ...result,
          [key]: value,
        };
      }
      return result;
    }, {} as Record<string, any>);
    return result;
  };
  // 提交搜索条件
  const handleSubmit = (isClear = false) => {
    emit('change', getSearchParams(), eventFiltersParams.value, isClear);
  };
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
    selectedItemList.value = selectedItemList.value.map(item => ({
      ...item,
      value: '',
      operator: '=',
    }));

    selectedVal.value = selectedItemList.value.map(item => item.id);
    handleSubmit(true);
  };
  const findIdByDisplayAndField = (display: string, field: string, ary: Array<Record<string, any>>) => {
    const foundItem = ary.find(item => item
      && item.display_name === display
      && item.field_name === field);

    return foundItem ? foundItem.id : null;
  };

  const handleUpdateModelValue = (val: any) => {
    emit('modelValueWatch', val);
  };

  const handleValueChange = (val: any[], changeItem: Record<string, any>) => {
    let processedVal = val;
    if (Array.isArray(val)) {
      // 处理包含逗号分隔的字符串，拆分并去重
      const flattenedValues: any[] = [];
      val.forEach((item) => {
        if (typeof item === 'string' && item.includes(',')) {
          // 拆分逗号分隔的字符串，并去除空白字符
          const splitItems = item.split(',').map(s => s.trim())
            .filter(s => s !== '');
          flattenedValues.push(...splitItems);
        } else {
          flattenedValues.push(item);
        }
      });
      // 去重
      processedVal = [...new Set(flattenedValues)];
    }

    selectedItemList.value = selectedItemList.value.map((item) => {
      if (item.id === changeItem.id) {
        return {
          ...item,
          value: processedVal,
        };
      }
      return item;
    });
  };

  watch(() => selectedItems.value, (val) => {
    selectedVal.value =  eventFiltersParams.value.map((item) => {
      const foundId = findIdByDisplayAndField(item.display_name, item.field, val);
      return foundId;
    });
  });
  onMounted(() => {
    if (urlSearchParams?.event_filters) {
      selectedItemList.value = urlSearchParams?.event_filters?.map((item: Record<string, any>) => ({
        id: item.id ? item.id :  `${item.field}:${item.display_name}`,
        field_name: item.field,
        display_name: item.display_name,
        operator: item.operator,
        value: (item.operator === 'IN' || item.operator === 'NOT IN') ? item.value.split(',') : item.value,
      }));
      selectedItemListOperator.value = urlSearchParams?.event_filters?.map((item: Record<string, any>) => ({
        id: item.id ? item.id :  `${item.field}:${item.display_name}`,
        operator: item.operator,
      }));
    }
    handleSubmit();
  });

  defineExpose<Exposes>({
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
.analysis-search-box {
  position: relative;
  background-color: #fff;
  border-radius: 2px;
  box-shadow: 0 2px 4px 0 rgb(25 25 41 / 5%);

  .panel-toggle-btn {
    position: absolute;
    bottom: 0;
    left: 50%;
    display: flex;
    width: 64px;
    height: 16px;
    justify-content: center;
    align-items: center;
    font-size: 12px;
    color: #fff;
    text-align: center;
    cursor: pointer;
    background: #dcdee5;
    border-radius: 0 0 8px 8px;
    transform: translate(-50%, 100%);
    transition: all .15s;

    &:hover {
      background: #c4c6cc;
    }

    &.is-floded {
      i {
        transform: rotateZ(-180deg);
      }
    }
  }
}


.box-row {
  display: grid;
  margin-bottom: 12px;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px 16px;

  .more-list-item {
    .list-item-lable {
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: 100%;

      .item-label {
        font-size: 12px;
        line-height: 20px;
        color: #63656e;
        vertical-align: top;
      }

      .close-btn {
        color: #63656e;
        cursor: pointer;
      }
    }


    .item-value {
      display: flex;
      padding-top: 6px;
    }
  }
}
</style>
