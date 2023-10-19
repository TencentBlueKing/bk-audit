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
  <div class="collector-create-header">
    <bk-steps
      v-model:cur-step="currentStep"
      :steps="steps"
      style="width: 640px;" />
  </div>
  <component
    :is="renderStepCom"
    @change="handleStepChange"
    @change-environment="handleRenderSteps"
    @change-report-method="handleRenderSteps" />
</template>
<script setup lang="ts">
  import {
    computed,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
    useRouter,
  } from 'vue-router';

  import useRouterBack from '@hooks/use-router-back';
  import useUrlSearch from '@hooks/use-url-search';

  import { changeConfirm } from '@utils/assist';

  import Step1 from './pages/step1/index.vue';
  import Step2 from './pages/step2/index.vue';
  import Step3 from './pages/step3/index.vue';

  const { t } = useI18n();
  const initSteps = [
    {
      title: t('采集配置'),
    },
    {
      title: t('采集下发'),
    },
    {
      title: t('字段清洗'),
    },
  ];
  const containerSteps = [
    {
      title: t('采集配置'),
    },
    {
      title: t('字段清洗'),
    },
  ];

  const steps = ref(initSteps);
  const route = useRoute();
  const comMap = {
    1: Step1,
    2: Step2,
    3: Step3,
  };

  type StepType = keyof typeof comMap

  const router = useRouter();
  const { appendSearchParams } = useUrlSearch();
  let step: StepType = 1;
  const routeQueryStep = parseInt(route.query.step as string, 10) as StepType;
  const { environment } = route.query;


  if (comMap[routeQueryStep]) {
    step = routeQueryStep;
  }
  if (route.name === 'dataIdEdit')   {
    step = 3;
  }

  if (environment === 'container'
    || route.name === 'dataIdEdit') {
    steps.value = containerSteps;
  }

  const currentStep = ref<StepType>(step);

  const renderStepCom = computed(() => comMap[currentStep.value]);

  const handleStepChange = (step: StepType) => {
    changeConfirm()
      .then(() => {
        appendSearchParams({
          step,
        });
        currentStep.value = step;
      });
  };

  const handleRenderSteps = (value: string) => {
    steps.value = value === 'container'
      || value === 'bkbase' ? containerSteps : initSteps;
  };

  useRouterBack(() => {
    router.push({
      name: 'systemDetail',
      params: {
        id: route.params.systemId,
      },
      query: {
        contentType: 'dataReport',
      },
    });
  });
</script>
<style lang="postcss" scoped>
  .collector-create-header {
    display: flex;
    justify-content: center;
    padding: 4px 0 24px;
  }
</style>
