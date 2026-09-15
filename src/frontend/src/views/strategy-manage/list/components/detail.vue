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
    <bk-loading
      class="strategy-detail-loading"
      :loading="detailLoading"
      mode="spin"
      size="small">
      <bk-tab
        v-model:active="active"
        type="card-grid">
        <bk-tab-panel
          v-for="item in panels"
          :key="item.name"
          :label="item.label"
          :name="item.name">
          <div class="strategy-detail-body">
            <component
              :is="comMap[item.name]"
              v-show="active === item.name"
              :active-tab="active"
              :data="data"
              :detail-loading="detailLoading"
              :strategy-map="strategyMap"
              :user-group-list="userGroupList" />
          </div>
        </bk-tab-panel>
      </bk-tab>
    </bk-loading>
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
  import RiskDiscoveryRules from './risk-discovery-rules.vue';
  import RiskDisplay from './risk-display.vue';
  import RiskOther from './risk-other.vue';
  import StrategyEventReport from './strategy-event-report.vue';

  import { isPlatformStrategyRoute } from '../../utils/strategy-routes';

  interface Props {
    data: StrategyModel,
    strategyMap: Record<string, string>,
    userGroupList: Array<{id: number, name: string}>,
    detailLoading?: boolean,
  }

  const props = withDefaults(defineProps<Props>(), {
    detailLoading: false,
  });
  const emits = defineEmits(['tab-change']);
  const { t } = useI18n();
  const route = useRoute();

  const comMap: Record<string, any> = {
    riskDetection: RiskDetection,
    riskDiscoveryRules: RiskDiscoveryRules,
    riskDisplay: RiskDisplay,
    eventReport: StrategyEventReport,
    riskOther: RiskOther,
  };

  const panels = computed(() => {
    const list = [
      { name: 'riskDetection', label: t('基础信息') },
      { name: 'riskDiscoveryRules', label: t('风险发现规则') },
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
    () => props.data?.strategy_id,
    () => {
      active.value = 'riskDetection';
    },
  );

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
  height: 100%;
  padding-top: 24px;
  background-color: #f5f7fa;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;

  .strategy-detail-loading {
    display: flex;
    height: 100%;
    min-height: 360px;
    flex: 1;
    flex-direction: column;
  }

  :deep(.bk-loading-wrapper) {
    display: flex;
    height: 100%;
    flex: 1;
    flex-direction: column;
  }

  :deep(.bk-tab) {
    display: flex;
    flex: 1;
    min-height: 0;
    flex-direction: column;

    .bk-tab-header {
      margin-left: 24px;
      font-size: 14px;
      flex-shrink: 0;
    }

    .bk-tab-content {
      flex: 1;
      min-height: 0;
      padding: 0 24px 0;
      overflow-y: auto;
      background: #fff;
      box-sizing: border-box;
    }

    :deep(.bk-tab-panel) {
      height: auto;
      min-height: 0;
    }
  }

  .strategy-detail-body {
    overflow: visible;
  }
}
</style>
