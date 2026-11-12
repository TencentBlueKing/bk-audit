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
  <div
    v-if="data.description"
    class="reopen-mis-report-wrap">
    {{ data.description }}
  </div>
</template>

<script setup lang='ts'>
  import type RiskManageModel from '@model/risk/risk';

  interface Props{
    data: RiskManageModel['ticket_history'][0]
  }
  defineProps<Props>();
</script>
<style scoped>
.reopen-mis-report-wrap {padding: var(--bk-theme-space-8) var(--bk-theme-space-16);
  font-size: 12px;
  color: var(--bk-theme-text-default);
  background: var(--bk-theme-surface-default);
  border: 1px solid var(--bk-theme-border-weak);
  border-radius: var(--bk-theme-control-radius);
  box-shadow: var(--bk-theme-card-shadow);
}
</style>
