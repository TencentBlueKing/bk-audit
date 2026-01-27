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
  <component
    :is="renderComponent"
    @change="handleStepChange" />
</template>
<script setup lang="ts">
  import {
    computed,
    provide,
    ref,
    watch,
  } from 'vue';
  import { useRoute, useRouter } from 'vue-router';

  import RootManageService from '@service/root-manage';

  import ConfigModel from '@model/root/config';

  import { changeConfirm } from '@utils/assist';

  import Bkbase from './components/bkbase/index.vue';
  import LogCreate from './components/index.vue';
  import NewLogApi from './components/newlog/api/index.vue';
  import NewLogCollector from './components/newlog/collector/index.vue';

  import useRequest from '@/hooks/use-request';
  import useRouterBack from '@/hooks/use-router-back';

  type StepComponentKey = 'logCreate' | 'bkbase' | 'newLogApi' | 'newLogCollector';

  const componentMap: Record<StepComponentKey, any> = {
    logCreate: LogCreate,
    bkbase: Bkbase,
    newLogApi: NewLogApi,
    newLogCollector: NewLogCollector,
  };

  const router = useRouter();
  const route = useRoute();
  const defaultComponentType: StepComponentKey = 'logCreate';
  const getQueryComponentType = () => {
    const routeQueryType = route.query.type as StepComponentKey;
    return componentMap[routeQueryType] ? routeQueryType : defaultComponentType;
  };

  const currentComponentType = ref<StepComponentKey>(getQueryComponentType());

  const renderComponent = computed(() => componentMap[currentComponentType.value]);

  const configData = ref(new ConfigModel());

  provide('configData', configData);
  provide('setLogCreateComponentType', (type: StepComponentKey) => {
    currentComponentType.value = type;
  });

  useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
    onSuccess: (data) => {
      configData.value = data;
    },
  });

  watch(
    () => route.query.type,
    () => {
      currentComponentType.value = getQueryComponentType();
    },
  );

  const handleStepChange = (step: any, formData: Record<string, any>) => {
    const componentType = resolveNextComponent(formData);
    changeConfirm()
      .then(() => {
        router.replace({
          name: route.name!,
          params: route.params,
          query: {
            ...route.query,
            type: componentType,
          },
        });
        currentComponentType.value = componentType;
      });
  };

  const resolveNextComponent = (formData: Record<string, any>): StepComponentKey => {
    if (formData.reportMethod === 'bkbase') {
      return 'bkbase';
    }
    if (formData.reportMethod === 'newlog' && formData.logType === 'apiPush') {
      return 'newLogApi';
    }
    return 'newLogCollector';
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
