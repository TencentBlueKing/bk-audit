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
        <component
          :is="renderCom"
          :data="data"
          :strategy-map="strategyMap"
          :user-group-list="userGroupList" />
      </bk-tab-panel>
    </bk-tab>
  </div>
</template>
<script setup lang="ts">
  import {
    computed,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type StrategyModel from '@model/strategy/strategy';

  import RiskDetection from './risk-detection.vue';
  import RiskDisplay from './risk-display.vue';
  import RiskOther from './risk-other.vue';

  interface Props {
    data: StrategyModel,
    strategyMap: Record<string, string>,
    userGroupList: Array<{id: number, name: string}>
  }

  defineProps<Props>();
  const { t } = useI18n();

  const renderCom = computed(() => comMap[active.value]);
  const comMap: Record<string, any> = {
    riskDetection: RiskDetection,
    riskDisplay: RiskDisplay,
    riskOther: RiskOther,
  };

  const panels = [
    { name: 'riskDetection', label: t('风险发现') },
    { name: 'riskDisplay', label: t('单据展示') },
    { name: 'riskOther', label: t('其他配置') },
  ];
  const active = ref<keyof typeof comMap>('riskDetection');

</script>
<style scoped lang="postcss">
.strategy-detail {
  padding-top: 24px;
  background-color: #f5f7fa;

  :deep(.bk-tab) {
    height: calc(100vh - 100px);

    .bk-tab-header {
      margin-left: 24px;
    }
  }
}
</style>
