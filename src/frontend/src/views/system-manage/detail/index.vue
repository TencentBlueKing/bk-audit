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
  <skeleton-loading
    fullscreen
    :loading="isLoading"
    :name="skeletonLoadingName">
    <div class="system-manage-detail-header">
      <system-info ref="appRef" />
      <content-tab v-model="contentType" />
    </div>
    <component
      :is="renderContentComponent"
      v-if="!isLoading" />
  </skeleton-loading>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import {
    computed,
    ref,
  } from 'vue';
  import { useRouter } from 'vue-router';

  import useRouterBack from '@hooks/use-router-back';
  import useUrlSearch from '@hooks/use-url-search';

  import AccessModel from './components/access-model/index.vue';
  import ContentTab from './components/content-tab/index.vue';
  import DataReport from './components/data-report/index.vue';
  import SystemDiagnosis from './components/system-diagnosis/index.vue';
  import SystemInfo from './components/system-info/index.vue';

  const contentComponentMap = {
    accessModel: AccessModel,
    dataReport: DataReport,
    systemDiagnosis: SystemDiagnosis,
  };
  const contentType = ref<keyof typeof contentComponentMap>('accessModel');
  const appRef = ref();

  const { getSearchParams } = useUrlSearch();
  const searchParams = getSearchParams();
  if (searchParams.contentType
    && _.has(contentComponentMap, searchParams.contentType)) {
    contentType.value = searchParams.contentType as keyof typeof contentComponentMap;
  }

  const renderContentComponent = computed(() => contentComponentMap[contentType.value]);

  const skeletonLoadingName = computed(() => (contentType.value === 'accessModel'
    ? 'systemDetailList'
    : 'systemDetail'));

  const isLoading = computed(() => (appRef.value ? appRef.value.loading : true));


  const router = useRouter();

  useRouterBack(() => {
    router.push({
      name: 'systemList',
    });
  });
</script>
<style lang="postcss">
  .system-manage-detail-header {
    margin: -20px -24px 0;
    background: #fff;
    box-shadow: 0 2px 4px 0 rgb(25 25 41 / 5%);
  }
</style>
