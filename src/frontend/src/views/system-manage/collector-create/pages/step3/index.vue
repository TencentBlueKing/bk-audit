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
    :is="comMap[currentStep]"
    @change="attrs.onChange" />
</template>

<script setup lang='ts'>
  import {
    computed,
    useAttrs,
  } from 'vue';
  import {
    useRoute,
  } from 'vue-router';

  import useUrlSearch from '@hooks/use-url-search';

  import CollectorStep3 from './pages/collector-index/index.vue';
  import DataIdStep3 from './pages/data-id-index/index.vue';

  const comMap = {
    1: CollectorStep3,
    2: DataIdStep3,
  };
  const { searchParams } = useUrlSearch();
  const route = useRoute();
  const attrs = useAttrs();

  const currentStep = computed(() => (
    searchParams.get('bk_data_id')
    || route.params.bkDataId ? 2 : 1));
</script>

