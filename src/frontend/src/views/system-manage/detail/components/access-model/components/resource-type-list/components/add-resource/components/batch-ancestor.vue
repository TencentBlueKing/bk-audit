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
  <div style="display: flex;">
    <h3>{{ title ? title : t('批量编辑所属父级资源') }}</h3>
    <span style="margin-left: 5px; font-size: 12px; line-height: 20px; color: #979ba5;">
      <slot name="subTitle" />
    </span>
  </div>
  <audit-form
    ref="formRef"
    form-type="vertical"
    :model="formData">
    <bk-form-item
      :label="label ? label : t('所属父级资源')"
      label-width="160"
      property="ancestor"
      required>
      <bk-select
        ref="selectRef"
        v-model="formData.ancestor"
        :auto-height="false"
        custom-content
        display-key="name"
        id-key="resource_type_id"
        :placeholder="placeholder ? placeholder :t('请选择所属父级资源')"
        :popover-options="{ boundary: 'parent' }"
        @search-change="handleSearch">
        <bk-tree
          ref="treeRef"
          children="children"
          :data="parentResourceList"
          :empty-text="t('数据搜索为空')"
          :search="searchValue"
          :show-node-type-icon="false"
          @node-click="handleBatchNodeClick">
          <template #default="{ data }: { data: SystemResourceTypeTree }">
            <span> {{ data.name }}</span>
          </template>
        </bk-tree>
      </bk-select>
    </bk-form-item>
  </audit-form>
  <div style="margin-top: 8px; font-size: 14px; line-height: 22px; color: #3a84ff; text-align: right;">
    <bk-button
      class="mr8"
      size="small"
      theme="primary"
      @click="handleSubmitBatch">
      {{ t('确定') }}
    </bk-button>
    <bk-button
      size="small"
      @click="handleCancelBatch">
      {{ t('取消') }}
    </bk-button>
  </div>
</template>
<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type SystemResourceTypeTree from '@model/meta/system-resource-type-tree';

  interface Props {
    parentResourceList: Array<SystemResourceTypeTree>
    title?: string,
    label?: string,
    placeholder?: string
  }

  interface Emits {
    (e: 'updateAncestor', value: string, selectedItems: Array<{
      value: string,
      label: string,
    }>): void
    (e: 'cancel'): void
  }

  defineProps<Props>();
  const emit = defineEmits<Emits>();
  const { t } = useI18n();

  const selectRef = ref();
  const treeRef = ref();
  const formRef = ref();

  const formData  = ref<{
    ancestor: string,
  }>({
    ancestor: '',
  });
  const searchValue = ref('');
  const selectedItems = ref<Array<{
    value: string,
    label: string,
  }>>([]);

  const handleSearch = (keyword: string) => {
    searchValue.value = keyword;
  };

  const handleBatchNodeClick = (nodeData: SystemResourceTypeTree) => {
    formData.value.ancestor = nodeData.resource_type_id;
    selectRef.value.selected = [{
      value: nodeData.resource_type_id,
      label: nodeData.name,
    }];
    selectedItems.value = [{
      value: nodeData.resource_type_id,
      label: nodeData.name,
    }];

    selectRef.value.hidePopover();
  };

  const handleSubmitBatch = () => {
    formRef.value.validate().then(() => {
      emit('updateAncestor', formData.value.ancestor, selectedItems.value);
    });
  };

  const handleCancelBatch = () => {
    formData.value.ancestor = '';
    emit('cancel');
  };
</script>
