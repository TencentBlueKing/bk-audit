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
    <div class="system-manage-detail-header">
      <system-info
        id="bk-audit"
        ref="appRef" />
      <content-tab
        v-model="contentType"
        :is-show-system-diagnosis="false" />
    </div>
    <component
      :is="renderContentComponent"
      id="bk-audit" />
  </div>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import {
    computed,
    ref,
  } from 'vue';

  // import { useRouter } from 'vue-router';
  import useUrlSearch from '@hooks/use-url-search';

  import AccessModel from '@views/system-manage/detail/components/access-model/index.vue';
  import ContentTab from '@views/system-manage/detail/components/content-tab/index.vue';
  import DataReport from '@views/system-manage/detail/components/data-report/index.vue';
  import SystemInfo from '@views/system-manage/detail/components/system-info/index.vue';

  const contentComponentMap = {
    accessModel: AccessModel,
    dataReport: DataReport,
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

  // const router = useRouter();

</script>
<style lang="postcss">
  .step3 {
    position: absolute;
    left: 50%;
    width: 60%;
    margin-top: 10px;
    transform: translateX(-50%);
  }
</style>
