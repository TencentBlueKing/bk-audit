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
  <div class="base-info">
    <div class="base-content">
      <render-info-block>
        <render-info-item :label="t('风险ID')">
          <tool-tips :data="alarmData.risk_id" />
        </render-info-item>
        <render-info-item :label="t('风险描述')">
          <tool-tips :data="alarmData.event_content" />
        </render-info-item>
      </render-info-block>
      <render-info-block>
        <render-info-item :label="t('策略名称')">
          {{ strategyName }}
        </render-info-item>
        <render-info-item :label="t('风险产生时间')">
          {{ dayjs(alarmData.event_time).format('YYYY-MM-DD HH:mm:ss') || '--' }}
        </render-info-item>
      </render-info-block>
      <render-info-block>
        <render-info-item :label="t('风险来源')">
          {{ alarmData.event_source || '--' }}
        </render-info-item>
        <render-info-item :label="t('责任人')">
          {{ alarmData.operator.join(',') || '--' }}
        </render-info-item>
      </render-info-block>
    </div>
  </div>
</template>
<script setup lang="ts">
  import dayjs from 'dayjs';
  import {
    computed,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import type RiskModel from '@model/event/risk';

  import useRequest from '@hooks/use-request';

  import ToolTips from '@components/show-tooltips-text/index.vue';

  import RenderInfoBlock from './components/render-info-block.vue';
  import RenderInfoItem from './components/render-info-item.vue';

  interface Props{
    alarmData: RiskModel
  }
  const props = defineProps<Props>();
  const { t } = useI18n();
  const strategyName = computed(() => strategyList.value
    .find(item => item.value === props.alarmData?.strategy_id)?.label);

  // 策略列表
  const {
    data: strategyList,
  } = useRequest(StrategyManageService.fetchAllStrategyList, {
    defaultValue: [],
    manual: true,
  });

</script>
<style lang="postcss">
.base-info {
  position: relative;

  .base-operation {
    position: absolute;
    top: -16px;
    right: 0;
    color: #3a84ff;
    cursor: pointer;
  }

  .edit-strategy {
    color: #3a84ff;
  }
}
</style>
