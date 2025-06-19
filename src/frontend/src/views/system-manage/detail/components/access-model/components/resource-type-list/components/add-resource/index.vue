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
    :title="isEdit ? t('编辑资源') : t('添加资源')"
    :width="920">
    <template #header>
      <span>{{ isEdit ? t('编辑资源') : t('添加资源') }}</span>
      <bk-radio-group
        v-model="addType"
        class="add-resource-type"
        type="capsule">
        <bk-radio-button label="single">
          {{ t('单个模式') }}
        </bk-radio-button>
        <bk-radio-button
          :disabled="isEdit"
          label="batch">
          {{ t('批量模式') }}
        </bk-radio-button>
      </bk-radio-group>
    </template>
    <add-single-resource
      v-if="addType === 'single'"
      :edit-data="editData"
      :is-edit="isEdit"
      @update-resource="handleUpdateResource" />
    <add-batch-resource
      v-else
      @update-resource="handleUpdateResource" />
  </audit-sideslider>
</template>
<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import SystemResourceTypeModel from '@model/meta/system-resource-type';

  import addBatchResource from './components/add-batch-resource.vue';
  import addSingleResource from './components/add-single-resource.vue';

  interface Emits {
    (e: 'updateResource'): void;
  }

  interface Exposes {
    handleOpen: (isBatch?: boolean, resourceTypeData?: SystemResourceTypeModel) => void,
  }

  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const isShowAdd = ref(false);
  const addType = ref('single');
  const editData = ref<SystemResourceTypeModel>(new SystemResourceTypeModel());
  const isEdit = ref(false);

  const handleUpdateResource = () => {
    emits('updateResource');
  };

  defineExpose<Exposes>({
    handleOpen(isBatch?: boolean, resourceTypeData?: SystemResourceTypeModel) {
      // 设置资源类型模式（批量/单个）
      addType.value = isBatch ? 'batch' : 'single';

      // 处理编辑/新增逻辑
      isEdit.value = !!resourceTypeData;
      editData.value = resourceTypeData || new SystemResourceTypeModel();

      // 显示侧边栏
      isShowAdd.value = true;
    },
  });
</script>
<style scoped lang="postcss">
.add-resource-type {
  margin-left: 220px;
}
</style>
