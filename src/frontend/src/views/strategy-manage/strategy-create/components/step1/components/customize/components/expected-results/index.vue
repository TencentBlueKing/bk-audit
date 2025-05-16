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
  <vuedraggable
    class="panel-edit flex"
    item-key="name"
    :list="expectedResultList">
    <template #item="{ element, index }: { element: DatabaseTableFieldModel, index: number }">
      <div
        :key="element.raw_name + element.aggregate + element.display_name"
        class="query-field flex-center-wrap">
        <div
          class="edit-field"
          @click="handleEdit(element, index)">
          <audit-icon
            style="margin-left: 7px;"
            type="edit-fill" />
        </div>
        <tooltips
          class="dragging-handle"
          :data="getMetricName(element)" />
        <audit-icon
          class="query-field-remove"
          type="delete-fill"
          @click.stop="() => handleDelete(index)" />
      </div>
    </template>
    <template #footer>
      <!-- 新增 -->
      <add-fields
        ref="addFieldsRef"
        v-model="isEdit"
        :aggregate-list="aggregateList"
        :config-type="configType"
        :expected-result-list="expectedResultList"
        :table-fields="localTableFields"
        @add-expected-result="handleAdd" />
      <div
        v-if="expectedResultList.length"
        v-bk-tooltips="t('清空选项')"
        class="clear-fields-btn flex-center-wrap">
        <audit-icon
          class="clear-field-icon"
          type="delete"
          @click="handleClear" />
      </div>
      <div
        v-else
        style="margin-left: 8px; color: #979ba5; user-select: none;">
        {{ t('未配置时，默认查询语句为 select *') }}
      </div>
    </template>
  </vuedraggable>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import Vuedraggable from 'vuedraggable';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';

  import Tooltips from '@components/show-tooltips-text/index.vue';

  import AddFields from './add-fields.vue';

  interface Expose {
    resetFormData: () => void,
    setSelect: (select: Array<DatabaseTableFieldModel>) => void;
  }
  interface Emits {
    (e: 'updateExpectedResult', value: Array<DatabaseTableFieldModel>): void;
  }
  interface Props {
    aggregateList: Array<Record<string, any>>
    tableFields: Array<DatabaseTableFieldModel>
    configType: string,
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const addFieldsRef = ref();

  const expectedResultList = ref<Array<DatabaseTableFieldModel>>([]);
  const isEdit = ref(false);
  const editItem = ref<DatabaseTableFieldModel>(new DatabaseTableFieldModel());

  const localTableFields = computed(() => {
    if (isEdit.value) {
      return props.tableFields
        .filter(field => field.table === editItem.value.table
          && field.raw_name === editItem.value.raw_name)
        .map(field => ({
          ...field,
          display_name: editItem.value.display_name,
          aggregate: editItem.value.aggregate,
        }));
    }
    return _.cloneDeep(props.tableFields);
  });

  const updateExpectedResult = () => {
    emits('updateExpectedResult', expectedResultList.value);
  };

  const handleEdit = (element: DatabaseTableFieldModel, index: number) => {
    isEdit.value = true;
    editItem.value = element;
    addFieldsRef.value.handleEditShowPop(index);
  };

  const getMetricName = (element: DatabaseTableFieldModel) => {
    const item = props.aggregateList.find(item => item.value === element.aggregate);
    return `[${item?.label}] ${element.display_name}`;
  };

  const handleAdd = (item: DatabaseTableFieldModel, editIndex: number | undefined) => {
    if (editIndex !== undefined) {
      expectedResultList.value.splice(editIndex, 1, item);
    } else {
      expectedResultList.value.push(item);
    }
    updateExpectedResult();
  };

  const handleDelete = (index: number) => {
    expectedResultList.value.splice(index, 1);
    updateExpectedResult();
  };

  const handleClear = () => {
    expectedResultList.value = [];
    updateExpectedResult();
  };

  defineExpose<Expose>({
    resetFormData: () => {
      expectedResultList.value = [];
    },
    setSelect(select: Array<DatabaseTableFieldModel>) {
      expectedResultList.value = select;
    },
  });
</script>
<style scoped lang="postcss">
.panel-edit {
  position: relative;
  min-height: 32px;
  padding: 0 3px;
  background: #f5f7fa;
  border-radius: 2px;
  flex-wrap: wrap;

  .query-field {
    position: relative;
    width: 180px;
    height: 26px;
    margin: 3px 4px 3px 0;
    line-height: 26px;
    color: #fff;
    white-space: nowrap;
    background: #29bc9e;
    border-radius: 2px;

    .edit-field {
      width: 26px;
      cursor: pointer;
      background-color: #0eac8c;
      border-bottom-left-radius: 2px;
      border-top-left-radius: 2px;
    }

    &:hover {
      .query-field-remove {
        visibility: visible;
      }
    }

    .dragging-handle {
      width: 130px;
      padding: 0 4px;
      cursor: move;
    }

    .query-field-remove {
      padding: 0 4px;
      text-align: center;
      visibility: hidden;
    }
  }

  .flex-center-wrap {
    display: flex;
    align-items: center;

    /* justify-content: center; */
    flex-wrap: wrap;
  }

  .clear-fields-btn {
    width: 26px;
    height: 26px;
    margin: 3px 0 3px 4px;
    font-size: 16px;
    cursor: pointer;
    background: #eaebf0;
    border-radius: 2px;
    justify-content: center;
  }
}
</style>
