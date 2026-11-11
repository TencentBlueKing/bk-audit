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
              :user-group-list="userGroupList"
              v-bind="item.name === 'riskDetection' ? { tagEditable, tagList, tagSave } : {}" />
          </div>
        </bk-tab-panel>
      </bk-tab>
    </bk-loading>
  </div>
</template>
<script setup lang="ts">
  import {
    computed,
    onMounted,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import BksecManageService from '@service/bksec-manage';

  import type StrategyModel from '@model/strategy/strategy';

  import RiskDetection from './risk-detection.vue';
  import RiskDiscoveryRules from './risk-discovery-rules.vue';
  import RiskDisplay from './risk-display.vue';
  import RiskOther from './risk-other.vue';
  import BksecTicket from './bksec-ticket.vue';
  import StrategyEventReport from './strategy-event-report.vue';

  import { isPlatformStrategyRoute } from '../../utils/strategy-routes';

  interface Props {
    data: StrategyModel,
    strategyMap: Record<string, string>,
    userGroupList: Array<{id: number, name: string}>,
    detailLoading?: boolean,
    tagEditable?: boolean,
    tagList?: Array<{ tag_id: string | number, tag_name: string }>,
    tagSave?: (tags: string[]) => Promise<unknown>,
  }

  const props = withDefaults(defineProps<Props>(), {
    detailLoading: false,
    tagEditable: false,
    tagList: () => [],
    tagSave: undefined,
  });
  const emits = defineEmits(['tab-change']);
  const { t } = useI18n();
  const route = useRoute();

  const comMap: Record<string, any> = {
    riskDetection: RiskDetection,
    riskDiscoveryRules: RiskDiscoveryRules,
    riskDisplay: RiskDisplay,
    eventReport: StrategyEventReport,
    bksecTicket: BksecTicket,
    riskOther: RiskOther,
  };

  const bksecFeatureEnabled = ref(!isPlatformStrategyRoute(route.name));
  const panels = computed(() => {
    const list = [
      { name: 'riskDetection', label: t('基础信息') },
      { name: 'riskDiscoveryRules', label: t('风险发现规则') },
      { name: 'riskDisplay', label: t('单据展示') },
      { name: 'eventReport', label: t('事件调查报告') },
    ];
    if (!isPlatformStrategyRoute(route.name) && bksecFeatureEnabled.value) {
      list.push({ name: 'bksecTicket', label: t('BKSEC安全工单') });
    }
    if (isPlatformStrategyRoute(route.name)) {
      list.push({ name: 'riskOther', label: t('风险分派规则') });
    }
    return list;
  });
  const active = ref<keyof typeof comMap>('riskDetection');

  onMounted(() => {
    if (isPlatformStrategyRoute(route.name)) return;
    BksecManageService.fetchFeature()
      .then((data) => {
        bksecFeatureEnabled.value = !!data?.enabled;
      })
      .catch(() => {
        bksecFeatureEnabled.value = false;
      });
  });

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
  min-height: 0;
  padding-top: var(--bk-theme-space-24);
  overflow: hidden;
  background-color: var(--bk-theme-surface-subtle);
  box-sizing: border-box;
  display: flex;
  flex-direction: column;

  .strategy-detail-loading {
    display: flex;
    height: 100%;
    min-height: 0;
    overflow: hidden;
    flex: 1;
    flex-direction: column;
  }

  :deep(.bk-loading-wrapper) {
    display: flex;
    height: 100%;
    min-height: 0;
    overflow: hidden;
    flex: 1;
    flex-direction: column;
  }

  :deep(.bk-tab) {
    display: flex;
    flex: 1;
    min-height: 0;
    overflow: hidden;
    flex-direction: column;

    .bk-tab-header {
      margin-left: var(--bk-theme-space-24);
      font-size: 14px;
      flex-shrink: 0;
    }

    .bk-tab-content {
      flex: 1;
      min-height: 0;padding: var(--bk-theme-space-24) var(--bk-theme-space-32) var(--bk-theme-space-24);
      overflow-y: auto;
      background: var(--bk-theme-surface-default);
      box-sizing: border-box;
    }

    .bk-tab-panel {
      height: auto;
      min-height: 100%;
    }
  }

  .strategy-detail-body {
    overflow: visible;
  }

  :deep(.render-info-block) {
    margin: 0;
  }

  :deep(.render-info-item) {
    display: flex;
    gap: var(--bk-theme-space-8);
    align-items: flex-start;
    min-height: 32px;
    padding: var(--bk-theme-space-6) 0;
    font-size: var(--bk-theme-font-size-sm);
    line-height: var(--bk-theme-line-height-sm);
  }

  :deep(.info-label) {
    flex: 0 0 84px;
    width: 84px;
    min-width: 84px;
    overflow: visible;
    color: var(--bk-theme-text-default);
    text-align: right;
    white-space: nowrap;
  }

  :deep(.info-value) {
    padding-left: 0;
    overflow: visible;
    color: var(--bk-theme-text-strong);
    text-overflow: unset;
    word-break: break-all;
  }
}
</style>
