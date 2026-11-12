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
  <div class="filter-condition">
    <bk-loading
      :loading="loading">
      <render-info-block>
        <render-info-item :label="t('筛选输入数据')">
          <div
            v-for="(item, index) in list"
            :key="index"
            class="condition-item">
            <div
              v-if="index"
              class="condition-equation mr4 mb4">
              {{ item.connector.toUpperCase() }}
            </div>
            <div class="condition-key mr4 mb4">
              {{ rtFieldsMap[item.key] || item.key }}
            </div>
            <div class="condition-method mr4 mb4">
              {{ operators.filter_operator
                ?.find((list: DictType)=> list.value === item.method)?.label
                || item.method }}
            </div>
            <div
              v-for="(value, valIndex) in item.value"
              :key="valIndex"
              class="condition-value mr4 mb4">
              {{ dicts[item.key]?.filter((list: DictType)=> list.value === value)[0]?.label || value }}
            </div>
          </div>
          <div v-if="!list.length">
            --
          </div>
        </render-info-item>
      </render-info-block>
    </bk-loading>
  </div>
</template>
<script lang="ts">
  const lists = [
    {
      connector: 'and', // AND / OR
      key: '', // 统计字段
      method: '', //  等式
      value: [] as Array<string>, // 对应值
    },
  ];
  type ConditionData = typeof lists;
</script>
<script setup lang="ts">
  import {
    computed,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import CommonDataModel from '@model/strategy/common-data';
  import type StrategyModel from '@model/strategy/strategy';

  import useRequest from '@hooks/use-request';

  import RenderInfoBlock from '../render-info-block.vue';
  import RenderInfoItem from '../render-info-item.vue';

  interface Props{
    data: StrategyModel;
    rtFieldsMap: Record<string, string>,
    loading: boolean,
  }
  interface DictType{
    label: string,
    value: string
  }
  const props = defineProps<Props>();

  const dicts = ref<Record<string, any>>({});
  const list = computed(() => props.data?.configs?.data_source?.filter_config || []);


  const { t } = useI18n();


  // 获取条件类型
  const {
    data: operators,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonDataModel(),
    manual: true,
  });
  // 筛选条件值
  const {
    run: fetchStrategyFieldValue,
  } = useRequest(StrategyManageService.fetchStrategyFieldValue, {
    defaultValue: [],
  });
  // 回显值
  const  handleValueDicts = (conditions: ConditionData) => {
    conditions.forEach((item) => {
      dicts.value[item.key] = [];
    });
    Object.keys(dicts.value).forEach((item) => {
      if (item) {
        fetchStrategyFieldValue({
          field_name: item,
        }).then((data) => {
          dicts.value[item] = data;
        });
      }
    });
  };
  watch(() => props.data, (data) => {
    if (data) {
      const config = data.configs.data_source?.filter_config;
      if (config) {
        handleValueDicts(config);
      }
    }
  }, {
    deep: true,
    immediate: true,
  });
</script>
<style lang="postcss">
.filter-condition {
  .mr4 {
    margin-right: var(--bk-theme-space-4);
  }

  .mb4 {
    margin-bottom: var(--bk-theme-space-4);
  }

  .condition-item {
    display: flex;
    margin-bottom: var(--bk-theme-space-8);
    flex-wrap: wrap;

    .condition-equation {
      padding: var(--bk-theme-space-2) var(--bk-theme-space-8);
      color: var(--bk-theme-color-brand-2);
      text-align: center;background: var(--bk-theme-fill-selected);
      border-radius: var(--bk-theme-tag-radius);
    }

    .condition-key {
      padding: var(--bk-theme-space-2) var(--bk-theme-space-8);
      color: #788779;background: var(--bk-theme-status-success-bg);
      border-radius: var(--bk-theme-tag-radius);
    }

    .condition-method {
      padding: var(--bk-theme-space-2) var(--bk-theme-space-8);color: var(--bk-theme-color-warn-2);background: var(--bk-theme-fill-warn);
      border-radius: var(--bk-theme-tag-radius);
    }

    .condition-value {
      padding: var(--bk-theme-space-2) var(--bk-theme-space-8);
      color: var(--bk-theme-text-default);
      background: var(--bk-theme-surface-muted);
      border-radius: var(--bk-theme-tag-radius);
    }
  }

  .condition-item:last-child {
    margin-bottom: 0;
  }
}
</style>
