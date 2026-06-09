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
        ref="renderComRef"
        v-model="searchModel"
        @submit="handleSubmit" />
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
    onMounted,
    ref,
  } from 'vue';

  import useUrlSearch from '@hooks/use-url-search';

  import EsQueryService from '@service/es-query';

  import FieldConfig from './components/render-field-config/config';
  import RenderKey from './components/render-key.vue';
  import RenderValue from './components/render-value/index.vue';

  interface FieldConfigItem {
    field_name: string;
    field_type: string;
    allow_operators: string[];
    category: string;
    is_json?: boolean;
    property?: Record<string, any>;
  }

  interface Emits {
    (e: 'change', value: Record<string, any>): void;
    (e: 'changeTableHeight'): void
  }
  interface Exposes {
    clearValue: () => void;
  }
  const emit = defineEmits<Emits>();
  const SEARCH_TYPE_QUERY_KEY = 'searchType';

  const comMap = {
    key: RenderKey,
    value: RenderValue,
  };

  const {
    getSearchParams,
    appendSearchParams,
  } = useUrlSearch();
  const urlSearchParams = getSearchParams();

  const renderType = ref<keyof typeof comMap>('key');
  if (comMap[urlSearchParams[SEARCH_TYPE_QUERY_KEY] as keyof typeof comMap]) {
    renderType.value = urlSearchParams[SEARCH_TYPE_QUERY_KEY] as keyof typeof comMap;
  }

  const renderComponent = computed(() => comMap[renderType.value]);
  const renderComRef = ref();

  const searchModel = ref<Record<string, any>>({
    datetime: [
      dayjs(Date.now() - 3600000).format('YYYY-MM-DDTHH:mm:ssZ'),
      dayjs().format('YYYY-MM-DDTHH:mm:ssZ'),
    ],
    datetime_origin: [
      'now-1h',
      'now',
    ],
  });

  // 从 search_config 接口获取的完整字段配置映射
  const fieldConfigMap = ref<Map<string, FieldConfigItem>>(new Map());

  // 获取 search_config 配置
  const fetchSearchConfig = async () => {
    try {
      const configList = await EsQueryService.fetchSearchConfig();
      const configMap = new Map<string, FieldConfigItem>();
      configList.forEach((item) => {
        if (item.field_name && item.allow_operators?.length) {
          configMap.set(item.field_name, {
            field_name: item.field_name,
            field_type: item.field_type || 'string',
            allow_operators: item.allow_operators,
            category: item.category || 'system',
            is_json: item.is_json,
            property: item.property,
          });
        }
      });
      fieldConfigMap.value = configMap;
    } catch (error) {
      console.error('Failed to fetch search config:', error);
      fieldConfigMap.value = new Map();
    }
  };

  // 获取字段的操作符，优先从 search_config 接口获取，否则使用 FieldConfig 的默认配置
  const getFieldOperator = (fieldName: string): string => {
    // 优先从 search_config 接口获取
    const fieldConfigItem = fieldConfigMap.value.get(fieldName);
    if (fieldConfigItem?.allow_operators?.length) {
      return fieldConfigItem.allow_operators[0]; // 返回第一个允许的操作符
    }
    // 其次从 FieldConfig 获取
    const defaultFieldConfigItem = FieldConfig()[fieldName as keyof ReturnType<typeof FieldConfig>];
    return defaultFieldConfigItem?.operator || 'include';
  };

  // 根据字段名获取字段的完整配置信息
  const getFieldConfig = (fieldName: string): FieldConfigItem | undefined => {
    // 优先从 search_config 接口获取
    const searchConfig = fieldConfigMap.value.get(fieldName);
    if (searchConfig) {
      return searchConfig;
    }
    // 尝试从 FieldConfig 获取
    const defaultFieldConfigItem = FieldConfig()[fieldName as keyof ReturnType<typeof FieldConfig>];
    if (defaultFieldConfigItem) {
      return {
        field_name: fieldName,
        field_type: defaultFieldConfigItem.type || 'string',
        allow_operators: [defaultFieldConfigItem.operator || 'include'],
        category: 'standard',
      };
    }
    return undefined;
  };

  // 将 field_type 转换为后端合法值：object 转为 string，其他保持不变
  const normalizeFieldType = (fieldType: string | undefined): string => {
    if (!fieldType || fieldType === 'object') {
      return 'string';
    }
    return fieldType;
  };

  // 解析嵌套字段的最终 field_type，递归查找 property.sub_keys
  const resolveFieldType = (fieldName: string, keys: string[]): string | undefined => {
    const config = fieldConfigMap.value.get(fieldName);
    if (!config) {
      return undefined;
    }
    if (keys.length === 0) {
      return config.field_type;
    }
    // 递归查找 property.sub_keys
    let currentSubs: Array<Record<string, any>> = config.property?.sub_keys || [];
    for (let i = 0; i < keys.length; i++) {
      const key = keys[i];
      const sub = currentSubs.find(item => item.field_name === key);
      if (!sub) {
        return config.field_type;
      }
      if (i === keys.length - 1) {
        return sub.field_type;
      }
      currentSubs = sub.property?.sub_keys || [];
    }
    return config.field_type;
  };
  // 添加时间格式转换函数
  const formatTimeWithTimezone = (timeStr: string) => {
    // 如果已经是标准格式，直接返回
    if (timeStr.includes('+')) {
      return timeStr;
    }

    return timeStr.replace(/\s(\d{2}:\d{2})$/, '+$1');
  };
  const normalizeParamArray = (value: unknown) => {
    if (_.isArray(value)) {
      return value.map(item => (item === null ? '' : item.toString())).filter(item => item !== '');
    }
    if (value === null || value === '') {
      return [];
    }
    return value?.toString().split(',');
  };
  // 解析 url 上面附带的查询参数
  Object.keys(urlSearchParams).forEach((searchFieldName) => {
    const config = FieldConfig()[searchFieldName as keyof ReturnType<typeof FieldConfig>];
    if (!config) {
      return;
    }
    if (urlSearchParams[searchFieldName] === undefined
      || urlSearchParams[searchFieldName] === null
      || urlSearchParams[searchFieldName] === '') {
      return;
    }
    if (config.type !== 'string') {
      searchModel.value[searchFieldName] = normalizeParamArray(urlSearchParams[searchFieldName]);
    } else {
      const value = urlSearchParams[searchFieldName];
      searchModel.value[searchFieldName] = value === null ? '' : value.toString();
    }
  });
  if (urlSearchParams.start_time && urlSearchParams.end_time) {
    searchModel.value.datetime = [urlSearchParams.start_time, urlSearchParams.end_time];
    searchModel.value.datetime = [
      formatTimeWithTimezone(urlSearchParams.start_time),
      formatTimeWithTimezone(urlSearchParams.end_time),
    ];
  }
  if (urlSearchParams.datetime_origin) {
    searchModel.value.datetime_origin = normalizeParamArray(urlSearchParams.datetime_origin);
  }

  const handleRenderTypeChange = () => {
    renderType.value = renderType.value === 'key' ? 'value' : 'key';
    appendSearchParams({
      [SEARCH_TYPE_QUERY_KEY]: renderType.value,
    });
    emit('changeTableHeight');
  };

  // 解析字段key，获取raw_name和keys（支持嵌套字段如JSON数组字符串）
  const parseFieldKey = (key: string): { raw_name: string; keys: string[] } => {
    try {
      const parsed = JSON.parse(key);
      if (Array.isArray(parsed) && parsed.length > 0) {
        const [fieldName, ...keys] = parsed;
        return { raw_name: fieldName, keys };
      }
    } catch (e) {
      // 不是JSON数组字符串，直接返回key
    }
    return { raw_name: key, keys: [] };
  };

  // 提交搜索条件
  const handleSubmit = () => {
    const conditions: Array<{
      field: {
        raw_name: string;
        field_type?: string;
        keys: any[];
      };
      operator: string;
      filters: any[];
    }> = [];

    const result = Object.keys(searchModel.value).reduce((result, key) => {
      const value = searchModel.value[key];
      if (key === 'datetime') {
        return {
          ...result,
          start_time: value[0],
          end_time: value[1],
        };
      }
      if (!_.isEmpty(value) && key !== 'datetime_origin') {
        // 解析字段key，获取raw_name和keys（支持嵌套字段）
        const { raw_name, keys } = parseFieldKey(key);
        // 获取字段的操作符，优先从 search_config 接口获取
        const operator = getFieldOperator(raw_name);
        // 获取字段的完整配置
        const fieldConfig = getFieldConfig(raw_name);

        let filters: any[] = [];
        if (_.isArray(value)) {
          filters = value;
        } else if (typeof value === 'string') {
          filters = value.split(',').filter((item: string) => item.trim() !== '');
        } else {
          filters = [value];
        }

        if (filters.length > 0) {
          // 获取最终的 field_type（对嵌套字段递归查找 property.sub_keys）
          const rawFieldType = resolveFieldType(raw_name, keys) || fieldConfig?.field_type;
          // 转换为 search 接口需要的 field_type 格式
          const fieldType = normalizeFieldType(rawFieldType);
          conditions.push({
            field: {
              raw_name,
              field_type: fieldType,
              keys,
            },
            operator,
            filters,
          });
        }
      }
      return result;
    }, {} as Record<string, any>);

    // 添加conditions数组到结果中
    if (conditions.length > 0) {
      result.conditions = conditions;
    }

    emit('change', result);
  };

  onMounted(() => {
    // 获取 search_config 配置
    fetchSearchConfig();
    handleSubmit();
  });

  defineExpose<Exposes>({
    clearValue() {
      // 重置搜索模型
      searchModel.value = {
        // 用于查询的date参数
        datetime: [
          dayjs(Date.now() - 3600000).format('YYYY-MM-DDTHH:mm:ssZ'),
          dayjs().format('YYYY-MM-DDTHH:mm:ssZ'),
        ],
        // 用于now语法的date参数（只用使用now语法，选择最近时间才会实时更新）
        datetime_origin: [
          'now-1h',
          'now',
        ],
      };
      // 同时重置子组件的字段配置（清除自定义字段、收藏字段等）
      renderComRef.value?.clearValue?.();
      handleSubmit();
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
</style>
