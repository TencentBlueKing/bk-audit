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
  <audit-sideslider
    v-model:is-show="isShowAdd"
    show-footer
    show-header-slot
    :title="t('添加资源')"
    :width="920">
    <template #header>
      <span>{{ t('添加资源') }}</span>
      <bk-radio-group
        v-model="addType"
        class="add-resource-type"
        type="capsule">
        <bk-radio-button label="single">
          {{ t('单个模式') }}
        </bk-radio-button>
        <bk-radio-button label="batch">
          {{ t('批量模式') }}
        </bk-radio-button>
      </bk-radio-group>
    </template>
    <component :is="addComponents" />
  </audit-sideslider>
</template>
<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import addBatchResource from './components/add-batch-action.vue';
  import addSingleResource from './components/add-single-action.vue';

  interface Exposes {
    handleOpen: () => void,
  }

  const comMap = {
    single: addSingleResource,
    batch: addBatchResource,
  };

  const { t } = useI18n();
  const isShowAdd = ref(false);
  const addType = ref<keyof typeof comMap>('single');

  const addComponents = computed(() =>  comMap[addType.value]);

  defineExpose<Exposes>({
    handleOpen() {
      isShowAdd.value = true;
    },
  });
</script>
<style scoped lang="postcss">
.add-resource-type {
  margin-left: 220px;
}
</style>
