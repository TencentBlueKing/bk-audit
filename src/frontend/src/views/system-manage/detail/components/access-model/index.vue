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
      ref="resourceTypeListRef"
      :can-edit-system="canEditSystem"
      @update-action="handleUpdateAction"
      @update-list-length="handleUpdateList" />
    <action-list
      ref="actionListRef"
      :can-edit-system="canEditSystem"
      @add-resource-type="handleAddResourceType"
      @update-list-length="handleUpdateListLength"
      @update-resource="handleUpdateResource" />
  </div>
</template>
<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
  import { useRoute } from 'vue-router';

  import ActionList from './components/action-list/index.vue';
  import ResourceTypeList from './components/resource-type-list/index.vue';

  interface Props {
    canEditSystem: boolean;
  }
  interface Emits {
    (e: 'getIsDisabledBtn', val: Record<string, any>): void;
  }
  defineProps<Props>();

  const emits = defineEmits<Emits>();

  const route = useRoute();
  const resourceTypeListRef = ref();
  const actionListRef = ref();

  const ListLength = ref<{
    resourceTypeListLength: number | null;
    actionListListLength: number | null;
  }>({
    resourceTypeListLength: null,
    actionListListLength: null,
  });

  const isShowreSource =  computed(() => {
    if ('type' in route.query) {
      return route.query.type !== 'simple';
    }
    return true;
  });

  const handleUpdateAction = () => {
    actionListRef.value?.updateAction();
  };

  const handleUpdateResource = () => {
    resourceTypeListRef.value?.updateResource();
  };

  const handleUpdateList = (length: number) => {
    ListLength.value.resourceTypeListLength = length;
  };

  const handleUpdateListLength = (length: number) => {
    ListLength.value.actionListListLength = length;
  };

  // 如果没有资源和操作，不能下一步
  watch(() => ListLength.value, (newData) => {
    emits('getIsDisabledBtn', newData);
  }, {
    deep: true,
  });

  const handleAddResourceType = () => {
    resourceTypeListRef.value?.addResourceType();
  };
</script>
