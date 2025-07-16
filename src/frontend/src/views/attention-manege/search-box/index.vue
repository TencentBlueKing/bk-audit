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
        v-model="searchModel"
        @clear="handleClear"
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

  import FieldConfig from './components/render-field-config/config';
  import RenderKey from './components/render-key.vue';
  import RenderValue from './components/render-value/index.vue';


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

  // 解析 url 上面附带的查询参数
  Object.keys(urlSearchParams).forEach((searchFieldName) => {
    const config = FieldConfig[searchFieldName as keyof typeof FieldConfig];
    if (!config) {
      return;
    }
    if (!urlSearchParams[searchFieldName]) return;
    if (config.type !== 'string') {
      searchModel.value[searchFieldName] = urlSearchParams[searchFieldName].split(',');
    } else {
      searchModel.value[searchFieldName] = urlSearchParams[searchFieldName];
    }
  });
  if (urlSearchParams.start_time && urlSearchParams.end_time) {
    searchModel.value.datetime = [urlSearchParams.start_time, urlSearchParams.end_time];
  }
  if (urlSearchParams.datetime_origin) {
    searchModel.value.datetime_origin = urlSearchParams.datetime_origin.split(',');
  }

  const handleRenderTypeChange = () => {
    renderType.value = renderType.value === 'key' ? 'value' : 'key';
    appendSearchParams({
      [SEARCH_TYPE_QUERY_KEY]: renderType.value,
    });
  };

  // 提交搜索条件
  const handleSubmit = () => {
    const result = Object.keys(searchModel.value).reduce((result, key) => {
      const value = searchModel.value[key];
      if (key === 'datetime') {
        return {
          ...result,
          start_time: value[0],
          end_time: value[1],
        };
      }
      if (!_.isEmpty(value)) {
        return {
          ...result,
          [key]: _.isArray(value) ? value.join(',') : value,
        };
      }
      return result;
    }, {} as Record<string, any>);
    emit('change', result);
  };
  const handleClear = () => {
    searchModel.value = {
      datetime: ['', ''],
      datetime_origin: ['', ''],
    };
    handleSubmit();
  };
  onMounted(() => {
    handleSubmit();
  });

  defineExpose<Exposes>({
    clearValue() {
      handleClear();
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
