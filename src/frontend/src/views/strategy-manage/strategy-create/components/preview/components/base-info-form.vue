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
  <div class="base-info-form">
    <template
      v-for="(fieldGroup, groupIndex) in renderShowFieldNames"
      :key="groupIndex">
      <render-info-block
        class="flex mt16"
        :style="{ marginBottom: groupIndex === renderShowFieldNames.length - 1 ? '0px' : '12px' }">
        <render-info-item
          v-for="(fieldItem, itemIndex) in fieldGroup"
          :key="itemIndex"
          :label="fieldItem.display_name"
          :label-width="labelWidth"
          :style="getFieldStyle(fieldItem.field_name)">
          <template v-if="fieldItem.field_name === 'risk_level'">
            <span
              v-if="data.risk_level"
              :style="{
                'background-color': riskLevelMap[data.risk_level].color,
                padding: '3px 8px',
                'border-radius': '3px',
                color: 'white'
              }">
              {{ riskLevelMap[data.risk_level].label }}
            </span>
            <span v-else>--</span>
          </template>
          <template v-else-if="fieldItem.field_name === 'strategy_name'">
            {{ data.strategy_name || '--' }}
          </template>
          <template v-else-if="fieldItem.field_name === 'risk_hazard'">
            {{ data.risk_hazard || '--' }}
          </template>
          <template v-else-if="fieldItem.field_name === 'risk_guidance'">
            {{ data.risk_guidance || '--' }}
          </template>
          <template v-else>
            {{ t('以实际内容为准') }}
          </template>
        </render-info-item>
      </render-info-block>
    </template>
  </div>
</template>
<script setup lang='ts'>
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskManageService from '@service/risk-manage';

  import type StrategyInfo from '@model/risk/strategy-info';

  import RenderInfoBlock from '@views/strategy-manage/list/components/render-info-block.vue';

  import RenderInfoItem from './render-info-item.vue';

  import useRequest from '@/hooks/use-request';

  interface Props{
    data: Record<string, any>,

    showFieldNames: Array<StrategyInfo['risk_meta_field_config'][0]>,
  }

  const props = defineProps<Props>();

  const { t, locale } = useI18n();

  const labelWidth = computed(() => (locale.value === 'en-US' ? 120 : 80));

  const strategyTagMap = ref<Record<string, string>>({});

  const riskLevelMap: Record<string, {
    label: string,
    color: string,
  }> =  {
    HIGH: {
      label: t('高'),
      color: '#ea3636',
    },
    MIDDLE: {
      label: t('中'),
      color: '#ff9c01',
    },
    LOW: {
      label: t('低'),
      color: '#979ba5',
    },
  };

  // 转为二维数组
  const group = (array: Array<any>, subGroupLength: number = 2): Array<Array<Props['showFieldNames'][0]>> => {
    let index = 0;
    const newArray = [];
    while (index < array.length) {
      newArray.push(array.slice(index, index += subGroupLength));
    }
    return newArray;
  };

  const renderShowFieldNames = computed(() => group(props.showFieldNames));

  // 获取字段样式
  const getFieldStyle = (fieldName: string) => {
    if (fieldName === 'notice_users') {
      return 'width: 100%;';
    }
    return '';
  };

  // 获取标签列表
  useRequest(RiskManageService.fetchRiskTags, {
    defaultParams: {
      page: 1,
      page_size: 1,
    },
    defaultValue: [],
    manual: true,
    onSuccess: (data) => {
      data.forEach((item) => {
        strategyTagMap.value[item.id] = item.name;
      });
    },
  });
</script>
<style lang="postcss" scoped>
.base-info-form {
  /* background-color: #f5f7fa; */
  padding: 10px;
  margin-bottom: 10px;

  .render-info-item {
    min-width: 50%;
    align-items: flex-start;
  }
}
</style>
