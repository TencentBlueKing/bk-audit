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
  <teleport to="#teleport-nav-step">
    <bk-steps
      v-model:cur-step="currentStep"
      class="strategy-upgrade-step"
      :steps="steps" />
  </teleport>

  <component
    :is="renderCom"
    style="margin-bottom: 24px;"
    @change="handleUpdate" />
</template>

<script setup lang='ts'>

  import {
    computed,
    ref,
  } from 'vue';
  import {
    useRoute,
    useRouter,
  } from 'vue-router';

  import useRouterBack from '@hooks/use-router-back';

  import Step1 from './components/step1/index.vue';
  import Step2 from './components/step2/index.vue';

  const comMap = {
    1: Step1,
    2: Step2,
  };
  const steps = [
    { title: '确认升级差异' },
    { title: '更新方案配置' },
  ];
  const router = useRouter();
  const route = useRoute();
  const currentStep = ref(1);
  const renderCom = computed(() => comMap[currentStep.value as keyof typeof comMap]);

  const handleUpdate = (step: number) => {
    currentStep.value = step;
  };
  useRouterBack(() => {
    router.push({
      name: 'strategyEdit',
      params: {
        id: route.params.strategyId,
      },
    });
  });
</script>
<style scoped>
.strategy-upgrade-step {
  width: 450px;
  margin: 0 auto;
  transform: translateX(-86px);

  :deep(.bk-step ) {
    display: flex;

    .bk-step-content {
      display: flex;
    }
  }
}
</style>
