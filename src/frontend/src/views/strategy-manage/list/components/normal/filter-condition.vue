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
        <render-info-item :label="t('触发规则')">
          <!-- {{ t('在') }} {{ time.join('-') }} {{ t('的时段内,') }} {{ t('每') }} -->
          {{ convertInterval }} {{ t(intervalUnit) }} {{ t('为一个统计周期,') }}
          {{ t('数据匹配次数') }}
          {{ equations.algorithm_operator.filter((item) => item.value === algorithms.method)[0]?.label }}
          {{ algorithms.threshold }}
        </render-info-item>
      </render-info-block>
      <render-info-block>
        <render-info-item
          class="condition-render-item"
          :label="t('检测条件')">
          <div
            v-for="(item, index) in aggConditions"
            :key="index"
            class="condition-item">
            <div
              v-if="index"
              class="condition-equation mr4 mb4">
              {{ item.condition.toUpperCase() }}
            </div>
            <div class="condition-key mr4 mb4">
              {{ conditions.find((list) => list.field_name === item.key)?.description || item.key }}
            </div>
            <div class="condition-method mr4 mb4">
              {{ operators.strategy_operator
                .filter((list: Record<string,string>)=> list.value === item.method)[0]?.label
                || item.method }}
            </div>
            <div
              v-for="(value, valIndex) in item.value"
              :key="valIndex"
              class="condition-value mr4 mb4">
              {{ getVal(item.key,value) }}
            </div>
          </div>
        </render-info-item>
      </render-info-block>
      <render-info-block v-if="aggDimensions && aggDimensions.length">
        <render-info-item :label="t('统计字段')">
          <span>
            {{ aggDimensions.map((aggDimension: any) =>
              conditions.filter((list) => list.field_name === aggDimension)[0]?.description).join(',') }}
          </span>
        </render-info-item>
      </render-info-block>
    </bk-loading>
  </div>
</template>
<script setup lang="ts">
  import {
    onMounted,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import CommonDataModel from '@model/strategy/common-data';
  import type StrategyModel from '@model/strategy/strategy';

  // import type StrategyConfigListModel from '@model/strategy/strategy-config-list';
  import useRequest from '@hooks/use-request';

  import RenderInfoBlock from '../render-info-block.vue';
  import RenderInfoItem from '../render-info-item.vue';

  interface Props{
    data: StrategyModel
  }
  interface DataType{
    label: string;
    value: string;
    children?: Array<DataType>
  }
  const props = defineProps<Props>();
  const { t } = useI18n();
  // const algorithms = ref<Record<string, string>>({});

  const dicts = ref<Record<string, Array<DataType>>>({});
  // eslint-disable-next-line vue/no-setup-props-destructure
  const aggConditions = props.data.configs.agg_condition;
  // eslint-disable-next-line vue/no-setup-props-destructure
  const aggDimensions = props.data.configs.agg_dimension;
  const convertInterval = ref(0);
  // eslint-disable-next-line vue/no-setup-props-destructure
  const interval = props.data.configs.agg_interval;
  // eslint-disable-next-line vue/no-setup-props-destructure
  const [algorithms] = props.data.configs.algorithms;

  const intervalUnit = ref('秒');
  if (Number(interval) % (60 * 60 * 24) === 0) {
    convertInterval.value = Number(interval) / (60 * 60 * 24);
    intervalUnit.value = '天';
  } else if (Number(interval) % (60 * 60) === 0) {
    convertInterval.value = Number(interval) / (60 * 60);
    intervalUnit.value = '小时';
  } else if (Number(interval) % 60 === 0) {
    intervalUnit.value = '分钟';
    convertInterval.value = Number(interval) / 60;
  }

  type conditionData = typeof aggConditions;

  // 获取次数下拉
  const {
    data: equations,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonDataModel(),
    manual: true,
  });
  // 筛选条件
  const {
    loading,
    data: conditions,
  } =  useRequest(StrategyManageService.fetchStrategyFields, {
    defaultValue: [],
    manual: true,
  });

  // 筛选条件值
  const {
    run: fetchStrategyFieldValue,
  } = useRequest(StrategyManageService.fetchStrategyFieldValue, {
    defaultValue: [],
  });

  // 获取条件类型
  const {
    data: operators,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonDataModel(),
    manual: true,
  });


  // 回显值
  const  initDictValue = (conditions: conditionData) => {
    conditions.forEach((item:Record<string, string>) => {
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
  const getVal = (key: string, value: string) => {
    let res = value;
    if (dicts.value[key] && dicts.value[key].length) {
      dicts.value[key].forEach((list) => {
        if (list.value === value) {
          res = list.label;
          return;
        } if (list.children && list.children.length) {
          list.children.forEach((childData) => {
            if (childData.value === value) {
              res =   `${list.label} / ${childData.label}`;
              return;
            }
          });
        }
      });
    }
    return res;
  };

  onMounted(() => {
    initDictValue(aggConditions);
  });
</script>
<style lang="postcss">
.filter-condition {
  .mr4 {
    margin-right: 4px;
  }

  .mb4 {
    margin-bottom: 4px;
  }

  .condition-render-item {
    .info-label {
      margin-top: 2px;
    }
  }

  .condition-item {
    display: flex;
    margin-bottom: 8px;
    flex-wrap: wrap;

    .condition-equation {
      padding: 2px 8px;
      color: #3a84ff;
      text-align: center;
      background: #edf4ff;
      border-radius: 2px;
    }

    .condition-key {
      padding: 2px 8px;
      color: #788779;
      background: #dde9de;
      border-radius: 2px;
    }

    .condition-method {
      padding: 2px 8px;
      color: #fe9c00;
      background: #fff1db;
      border-radius: 2px;
    }

    .condition-value {
      padding: 2px 8px;
      color: #63656e;
      background: #f0f1f5;
      border-radius: 2px;
    }
  }

  .condition-item:last-child {
    /* margin-top: -2px; */
    margin-bottom: 0;
  }
}
</style>
