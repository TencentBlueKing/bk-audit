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
  <div style="padding-bottom: 24px;">
    <resource-type-list
      v-if="isShowreSource"
      :can-edit-system="canEditSystem" />
    <action-list :can-edit-system="canEditSystem" />
  </div>
</template>
<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { useRoute } from 'vue-router';

  import ActionList from './components/action-list/index.vue';
  import ResourceTypeList from './components/resource-type-list/index.vue';

  interface Props {
    canEditSystem: boolean;
  }

  defineProps<Props>();
  const route = useRoute();

  const isShowreSource =  ref(computed(() => {
    if (route.name === 'systemAccessSteps') {
      if ('type' in route.query) {
        return route.query.type !== 'simple';
      }
      return true;
    }
    return true;
  }));

</script>
