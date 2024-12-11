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
    <template #item="{ element, index }: { element: ResultItem, index: number }">
      <div
        :key="element.name + element.aggregate + element.display_name"
        class="query-field flex-center-wrap">
        <tooltips
          class="dragging-handle"
          :data="getMetricName(element)" />
        <audit-icon
          class="query-field-remove"
          type="delete-fill"
          @click="() => handleDelete(index)" />
      </div>
    </template>
    <template #footer>
      <!-- 新增 -->
      <add-fields
        :aggregate-list="aggregateList"
        :expected-result-list="expectedResultList"
        @add-expected-result="handleAdd" />
      <div
        v-bk-tooltips="t('清空选项')"
        class="clear-fields-btn flex-center-wrap">
        <audit-icon
          class="clear-field-icon"
          type="delete"
          @click="handleClear" />
      </div>
    </template>
  </vuedraggable>
</template>
<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import Vuedraggable from 'vuedraggable';

  import Tooltips from '@components/show-tooltips-text/index.vue';

  import AddFields from './add-fields.vue';

  interface ResultItem {
    uid: string,
    name: string,
    type: string,
    aggregate: string,
    display_name: string,
    is_joined: boolean,
  }
  interface Emits {
    (e: 'updateExpectedResult', value: Array<ResultItem>): void;
  }
  interface Props {
    aggregateList: Array<Record<string, any>>
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  // {
  //   uid: 'fr93yxgtrUtMCZ8DjkTh7F',
  //   name: 'dtEventTime',
  //   type: 'datetime',
  //   aggregate: 'SUM',
  //   display_name: '时间',
  //   is_joined: false,
  // }
  const expectedResultList = ref<Array<ResultItem>>([]);

  const updateExpectedResult = () => {
    emits('updateExpectedResult', expectedResultList.value);
  };

  const getMetricName = (element: ResultItem) => {
    const item = props.aggregateList.find(item => item.value === element.aggregate);
    return t(`[${item?.label}] ${element.display_name}`);
  };

  const handleAdd = (item: ResultItem) => {
    expectedResultList.value.push(item);
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
    height: 26px;
    margin: 3px 4px 3px 0;
    line-height: 26px;
    color: #fff;
    white-space: nowrap;
    background: #1eab8b;
    border-radius: 2px;

    &:hover {
      .query-field-remove {
        visibility: visible;
      }
    }

    .dragging-handle {
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
    justify-content: center;
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
  }
}
</style>
