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
    :title="isEdit ? t('编辑操作') : t('添加操作')"
    :width="920">
    <template #header>
      <span>{{ isEdit ? t('编辑操作') : t('添加操作') }}</span>
      <bk-radio-group
        v-model="addType"
        class="add-resource-type"
        type="capsule">
        <bk-radio-button
          :disabled="isEdit"
          label="batch">
          {{ t('批量模式') }}
        </bk-radio-button>
        <bk-radio-button label="single">
          {{ t('单个模式') }}
        </bk-radio-button>
      </bk-radio-group>
    </template>
    <add-single-action
      v-if="addType === 'single'"
      :action-list="actionList"
      :edit-data="editData"
      :is-edit="isEdit"
      :sensitivity-list="sensitivityList"
      @add-resource-type="handleAddResourceType"
      @update-action="handleUpdateAction" />
    <add-batch-action
      v-else
      :action-list="actionList"
      :sensitivity-list="sensitivityList"
      @update-action="handleUpdateAction" />
  </audit-sideslider>
</template>
<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import SystemActionModel from '@model/meta/system-action';

  import addBatchAction from './components/add-batch-action.vue';
  import addSingleAction from './components/add-single-action.vue';

  interface Emits {
    (e: 'updateAction'): void;
    (e: 'addResourceType'): void;
  }

  interface Props {
    actionList: SystemActionModel[],
  }

  interface Exposes {
    handleOpen: (actionData?: SystemActionModel) => void,
  }

  defineProps<Props>();
  const emits = defineEmits<Emits>();

  const sensitivityList = [
    {
      value: 1,
      label: t('一级(不敏感)'),
    },
    {
      value: 2,
      label: t('二级(低)'),
    },
    {
      value: 3,
      label: t('三级(中)'),
    },
    {
      value: 4,
      label: t('四级(高)'),
    },
  ];

  const { t } = useI18n();
  const isShowAdd = ref(false);
  const addType = ref('batch');
  const editData = ref<SystemActionModel>(new SystemActionModel());
  const isEdit = ref(false);

  const handleUpdateAction = () => {
    emits('updateAction');
  };

  const handleAddResourceType = () => {
    emits('addResourceType');
  };

  defineExpose<Exposes>({
    handleOpen(actionData?: SystemActionModel) {
      // 设置操作模式（批量/单个）
      if (actionData) {
        addType.value = 'single';
      }

      // 处理编辑/新增状态
      isEdit.value = !!actionData;
      editData.value = actionData || new SystemActionModel();

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
