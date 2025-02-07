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
  <scroll-faker>
    <div
      class="risk-preview"
      style="height: calc(100vh - 60px)">
      <base-info
        :data="riskData"
        :risk-status-common="riskStatusCommon"
        :strategy-list="[]" />
      <!-- 关联事件 -->
      <div class="link-event-wrap">
        <link-event
          :data="riskData"
          :strategy-list="[]" />
      </div>
    </div>
  </scroll-faker>
</template>
<script setup lang="ts">
  import RiskManageService from '@service/risk-manage';

  import StrategyFieldEvent from '@model/strategy/strategy-field-event';

  import BaseInfo from './components/base-info.vue';
  import LinkEvent from './components/link-event.vue';

  import useRequest from '@/hooks/use-request';

  interface IFormData {
    strategy_id?: number,
    strategy_name: string,
    tags: Array<string>,
    description: string,
    control_id: string,
    control_version?: number,
    configs: Record<string, any>,
    status: string,
    risk_level: string,
    risk_hazard: string,
    risk_guidance: string,
    risk_title: string,
    event_data_field_configs: StrategyFieldEvent['event_data_field_configs'],
    event_basic_field_configs: StrategyFieldEvent['event_basic_field_configs'],
    processor_groups: [],
    notice_groups: []
  }

  interface Props {
    riskData: IFormData
  }

  defineProps<Props>();

  const {
    data: riskStatusCommon,
  } = useRequest(RiskManageService.fetchRiskStatusCommon, {
    manual: true,
    defaultValue: [],
  });
</script>
<style lang="postcss" scoped>
.risk-preview {
  padding: 16px 24px;

  .link-event-wrap {
    margin-top: 16px;
  }
}
</style>
