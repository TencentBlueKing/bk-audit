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
  <div class="step3">
    <div class="step3-box">
      <div class="system-manage-detail-header">
        <system-info
          id="bk-audit"
          ref="appRef" />
      </div>
      <data-report
        ref="dataReportRef"
        @data-enabled="handleGetDataEnabled" />
    </div>
  </div>
</template>
<script setup lang="ts">
  import { ref } from 'vue';

  import DataReport from '@views/system-manage/detail/components/data-report/index.vue';
  import SystemInfo from '@views/system-manage/detail/components/system-info/index.vue';

  interface Emits {
    (e: 'isDataEnabled', value: boolean): void
  }
  const emit = defineEmits<Emits>();
  const appRef = ref();

  const handleGetDataEnabled  = (val: boolean) => {
    emit('isDataEnabled', val);
  };

</script>
<style scoped lang="postcss">
  .step3 {
    position: relative;
    width: 100%;
    height: calc(100vh - 120px);
    overflow: auto;

    .step3-box {
      position: absolute;
      left: 50%;
      width: 60%;
      margin-top: 10px;
      transform: translateX(-50%);
    }
  }
</style>
