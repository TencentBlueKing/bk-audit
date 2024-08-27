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
  <div class="risk-detection">
    <collapse-panel
      class="collapse-card-title"
      :label="t('基础配置')"
      style="margin-top: 14px;">
      <render-info-block class="mt16">
        <render-info-item :label="t('策略名称')">
          {{ data.strategy_name }}
        </render-info-item>
      </render-info-block>
      <render-info-block>
        <render-info-item :label="t('策略标签')">
          <span v-if="data.tags.length">
            <span
              v-for="tagItem in data.tags"
              :key="tagItem"
              class="label-item"> {{ strategyMap[tagItem] }}</span>
          </span>
          <span v-else>
            --
          </span>
        </render-info-item>
      </render-info-block>
      <render-info-block>
        <render-info-item :label="t('风险等级')">
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
        </render-info-item>
      </render-info-block>
      <render-info-block
        class="flex "
        style="margin-bottom: 12px;">
        <render-info-item
          :label="t('风险危害')">
          {{ data.risk_hazard || '--' }}
        </render-info-item>
      </render-info-block>
      <render-info-block
        class="flex "
        style="margin-bottom: 12px;">
        <render-info-item
          :label="t('处理指引')">
          {{ data.risk_guidance || '--' }}
        </render-info-item>
      </render-info-block>
    </collapse-panel>
    <collapse-panel
      class="collapse-card-title"
      :label="t('方案')"
      style="margin-top: 24px;">
      <render-info-block class="mt16">
        <render-info-item :label="t('方案名称')">
          {{ controlName }} - V{{ data.control_version }}
        </render-info-item>
      </render-info-block>

      <bk-loading :loading="controlLoading">
        <component
          :is="comMap[controlTypeId]"
          ref="comRef"
          :data="data" />
      </bk-loading>
    </collapse-panel>
  </div>
</template>
<script setup lang="ts">
  import {
    computed,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import type StrategyModel from '@model/strategy/strategy';

  import useRequest from '@hooks/use-request';

  import RenderAiops from './aiops/index.vue';
  import collapsePanel from './collapse-panel.vue';
  import FilterCondition from './normal/filter-condition.vue';
  import RenderInfoBlock from './render-info-block.vue';
  import RenderInfoItem from './render-info-item.vue';

  interface Props {
    data: StrategyModel,
    strategyMap: Record<string, string>
  }

  const props = defineProps<Props>();
  const { t } = useI18n();
  const controlTypeId = computed(() => controlList.value
    .find(item => item.control_id === props.data.control_id)?.control_type_id || '');// 方案类型id
  const controlName = computed(() => controlList.value
    .find(item => item.control_id === props.data.control_id)?.control_name || '--');// 方案名称
  const comMap: Record<string, any> = {
    BKM: FilterCondition,
    AIOps: RenderAiops,
  };

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

  // 获取方案列表
  const {
    data: controlList,
    loading: controlLoading,
  } = useRequest(StrategyManageService.fetchControlList, {
    defaultValue: [],
    manual: true,
  });

</script>
