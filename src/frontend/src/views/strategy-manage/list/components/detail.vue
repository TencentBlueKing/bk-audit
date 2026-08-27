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
  <div class="strategy-detail">
    <bk-tab
      v-model:active="active"
      type="card-grid">
      <bk-tab-panel
        v-for="item in panels"
        :key="item.name"
        :label="item.label"
        :name="item.name">
        <scroll-faker>
          <component
            :is="comMap[item.name]"
            v-if="active === item.name"
            :active-tab="active"
            :data="data"
            :strategy-map="strategyMap"
            style="height: calc(100% - 50px)"
            :user-group-list="userGroupList" />
        </scroll-faker>
      </bk-tab-panel>
    </bk-tab>
  </div>
</template>
<script setup lang="ts">
  import {
    computed,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import type StrategyModel from '@model/strategy/strategy';

  import RiskDetection from './risk-detection.vue';
  import RiskDisplay from './risk-display.vue';
  import RiskOther from './risk-other.vue';
  import StrategyEventReport from './strategy-event-report.vue';

  import { isPlatformStrategyRoute } from '../../utils/strategy-routes';

  interface Props {
    data: StrategyModel,
    strategyMap: Record<string, string>,
    userGroupList: Array<{id: number, name: string}>
  }

  defineProps<Props>();
  const emits = defineEmits(['tab-change']);
  const { t } = useI18n();
  const route = useRoute();

  const comMap: Record<string, any> = {
    riskDetection: RiskDetection,
    riskDisplay: RiskDisplay,
    eventReport: StrategyEventReport,
    riskOther: RiskOther,
  };

  // 全局策略详情展示「风险分派规则」；审计策略不展示
  const panels = computed(() => {
    const list = [
      { name: 'riskDetection', label: t('基础信息') },
      { name: 'riskDisplay', label: t('单据展示') },
      { name: 'eventReport', label: t('事件调查报告') },
    ];
    if (isPlatformStrategyRoute(route.name)) {
      list.push({ name: 'riskOther', label: t('风险分派规则') });
    }
    return list;
  });
  const active = ref<keyof typeof comMap>('riskDetection');

  watch(
    active,
    (val) => {
      emits('tab-change', val);
    },
    { immediate: true },
  );

</script>
<style scoped lang="postcss">
.strategy-detail {
  padding-top: 24px;
  background-color: #f5f7fa;

  :deep(.bk-tab) {
    height: calc(100vh - 115px);

    .bk-tab-header {
      margin-left: 24px;
      font-size: 14px;
    }

    .bk-tab-content {
      height: 100%;
      padding: 24px;
    }
  }
}
</style>
