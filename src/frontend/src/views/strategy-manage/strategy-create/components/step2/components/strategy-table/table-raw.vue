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
  <div
    v-for="(eventItem, eventItemIndex) in eventItemArr"
    :key="eventItemIndex"
    class="table-row">
    <template
      v-for="(value, valueKey) in eventItem"
      :key="valueKey">
      <div
        v-if="includesKey.includes(valueKey)"
        class="cell"
        :class="getCellClass(valueKey)">
        <field-cell
          ref="fieldCellRef"
          :all-tools-data="allToolsData"
          :event-item="eventItem"
          :field-key="valueKey"
          :output-fields="outputFields"
          :strategy-name="strategyName"
          :tag-data="tagData"
          @open-tool="handleOpenTool"
          @refresh-tool-list="handleRefreshToolList" />
      </div>
    </template>
  </div>
</template>

<script setup lang='ts'>
  import _ from 'lodash';
  import { ref, watch } from 'vue';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';
  import ToolDetailModel from '@model/tool/tool-detail';

  import FieldCell from './field-cell.vue';

  import type StrategyFieldEvent from '@/domain/model/strategy/strategy-field-event';

  interface Props {
    eventItemArr: StrategyFieldEvent['risk_meta_field_config'];
    select: Array<DatabaseTableFieldModel>;
    strategyName: string;
    outputFields: Array<{
      raw_name: string;
      display_name: string;
      description: string;
      target_field_type: string;
    }>;
    allToolsData: Array<ToolDetailModel>;
    tagData: Array<{
      tag_id: string
      tag_name: string;
      tool_count: number;
    }>;
  }

  interface Emits {
    (e: 'openTool', value: string): void;
    (e: 'refresh-tool-list'): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();

  const fieldCellRef = ref();

  const localSelect = ref<Array<DatabaseTableFieldModel>>([]);

  const includesKey = ['field_name', 'is_priority', 'drill_config', 'display_name'];

  const getCellClass = (valueKey: string) => ({
    'field-name': valueKey === 'field_name',
    'display-name': valueKey === 'display_name',
    'is-priority': valueKey === 'is_priority',
    'drill-config': valueKey === 'drill_config',
    // description: valueKey === 'description',
  });

  // 打开工具
  const handleOpenTool = async (uids: string) => {
    emit('openTool', uids);
  };

  const handleRefreshToolList = () => {
    emit('refresh-tool-list');
  };

  watch(() => props.select, (data) => {
    localSelect.value = _.cloneDeep(data);
  }, {
    immediate: true,
  });

  defineExpose({
    getValue() {
      if (!fieldCellRef.value) {
        return Promise.resolve();
      }
      return Promise.all((fieldCellRef.value as { getValue: () => any }[])?.map(item => item?.getValue()));
    },
  });
</script>

<style lang="postcss" scoped>
.table-row {
  display: flex;

  .cell {
    display: flex;
    height: 42px;
    border-right: 1px solid #dcdee5;
    border-bottom: 1px solid #dcdee5;
    align-items: center;

    &.field-name {
      width: 250px;
    }

    &.display-name {
      width: 250px;
    }

    &.is-priority {
      width: 200px;
    }

    &.drill-config {
      width: 250px;
    }

    &:last-child {
      flex: 1;
    }
  }
}

.empty-row {
  height: 100%;

  .empty-message {
    display: flex;
    width: 100%;
    height: 58px;
    padding: 12px;
    color: #979ba5;
    border-right: 1px solid #dcdee5;
    border-bottom: 1px solid #dcdee5;
    justify-content: center;
    align-items: center;
  }
}
</style>
