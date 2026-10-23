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
  <template v-if="eventItemArr && eventItemArr.length">
    <vuedraggable
      handle=".row-drag-handle"
      item-key="field_name"
      :list="eventItemArr">
      <template #item="{element}: { element: StrategyFieldEvent['event_basic_field_configs'][0] }">
        <div class="table-row">
          <div
            v-for="valueKey in columnKeys"
            :key="valueKey"
            class="cell"
            :class="getCellClass(valueKey)">
            <template v-if="valueKey === 'field_name'">
              <audit-icon
                class="row-drag-handle"
                type="move" />
            </template>
            <field-cell
              ref="fieldCellRef"
              :all-tools-data="allToolsData"
              :event-item="element"
              :event-item-key="eventItemKey"
              :field-key="valueKey"
              :output-fields="outputFields"
              :select-options="localSelect"
              :strategy-name="strategyName"
              :tag-data="tagData"
              @add-custom-constant="addCustomConstant"
              @open-tool="handleOpenTool"
              @refresh-tool-list="handleRefreshToolList"
              @select="handleSelect"
              @update:field-value="updateFieldValue(element, valueKey, $event)" />
          </div>
        </div>
      </template>
    </vuedraggable>
  </template>
  <template v-else>
    <div
      v-if="!isEditMode && !isCloneMode"
      class="table-row empty-row">
      <div class="empty-message">
        {{ t('暂未获取到相关字段，请先进入下一步') }}
      </div>
    </div>
  </template>
</template>

<script setup lang='ts'>
  import _ from 'lodash';
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';
  import Vuedraggable from 'vuedraggable';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';
  import StrategyFieldEvent from '@model/strategy/strategy-field-event';
  import ToolDetailModel from '@model/tool/tool-detail';

  import FieldCell from './field-cell.vue';

  import {
    isStrategyCloneRoute,
    isStrategyEditRoute,
  } from '../../../../../utils/strategy-routes';

  type EventFieldKey = keyof StrategyFieldEvent['event_basic_field_configs'][0];

  interface Props {
    eventItemArr: StrategyFieldEvent['event_basic_field_configs'];
    eventItemKey: 'event_basic_field_configs' | 'event_data_field_configs' | 'event_evidence_field_configs' | 'risk_meta_field_config';
    select: Array<DatabaseTableFieldModel>;
    strategyType: string;
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
  const { t } = useI18n();
  const route = useRoute();

  const fieldCellRef = ref();
  const isEditMode = isStrategyEditRoute(route.name);
  const isCloneMode = isStrategyCloneRoute(route.name);

  const localSelect = ref<Array<DatabaseTableFieldModel>>([]);

  // 固定列顺序，避免按对象 key 遍历导致「基本信息 / 事件结果」列错位
  const columnKeys = computed((): EventFieldKey[] => {
    const keys: EventFieldKey[] = [
      'field_name',
      'display_name',
      'is_show',
      'is_priority',
      'duplicate_field',
      'map_config',
      'enum_mappings',
      'drill_config',
      'description',
    ];
    if (props.strategyType === 'model') {
      return keys.filter(key => key !== 'map_config');
    }
    return keys;
  });

  const getCellClass = (valueKey: EventFieldKey) => ({
    'field-name': valueKey === 'field_name',
    'display-name': valueKey === 'display_name',
    'is-priority': valueKey === 'is_priority' || valueKey === 'is_show' || valueKey === 'enum_mappings' || valueKey === 'duplicate_field',
    'map-config': valueKey === 'map_config',
    'enum-mappings': valueKey === 'enum_mappings',
    'drill-config': valueKey === 'drill_config',
    description: valueKey === 'description',
  });

  const updateFieldValue = (config: any, key: EventFieldKey, value: any) => {
    // eslint-disable-next-line no-param-reassign
    config[key] = value;
  };

  const handleSelect = (value: string, config: StrategyFieldEvent['event_basic_field_configs'][0]) => {
    // 如果是固定值 给target_value赋值
    const selectItem = localSelect.value.find(item => item.raw_name === value);
    if (selectItem && !selectItem.table && config.map_config) {
      // eslint-disable-next-line no-param-reassign
      config.map_config.target_value = value;
    }
  };

  const addCustomConstant = (value: string) => {
    localSelect.value.push({
      table: '',
      raw_name: value,
      display_name: value,
      field_type: '',
      aggregate: null,
      spec_field_type: '',
      remark: '',
      property: {},
    });
  };

  // 打开工具
  const handleOpenTool = async (toolInfo: string) => {
    emit('openTool', toolInfo);
  };

  const handleRefreshToolList = () => {
    emit('refresh-tool-list');
  };

  watch(() => props.select, (data) => {
    localSelect.value = _.cloneDeep(data);
  }, {
    immediate: true,
  });

  watch(() => props.eventItemArr, (item) => {
    // 如果有固定值没有对应select，补上
    item.forEach((config) => {
      if (config.map_config
        && config.map_config.target_value
        && !localSelect.value.some(select => select.display_name === config.map_config?.target_value)) {
        addCustomConstant(config.map_config.target_value);
      }
    });
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
  display: grid;
  grid-template-columns: var(--event-row-cols);
  width: 100%;
  min-width: 0;
  background: #fff;

  .row-drag-handle {
    margin: 0 10px;
    font-size: 13px;
    color: #c4c6cc;
    cursor: move;
  }

  &.is-even {
    background: #fafbfd;
  }

  .cell {
    display: flex;
    box-sizing: border-box;
    height: 42px;
    min-width: 0;
    overflow: hidden;
    padding: 0 12px;
    border-right: 1px solid #dcdee5;
    border-bottom: 1px solid #dcdee5;
    align-items: center;

    &.map-config {
      align-items: stretch;
      padding: 0;
    }

    &.drill-config,
    &.enum-mappings,
    &.description,
    &.display-name {
      padding: 0;
    }

    &.display-name {
      :deep(.show-tooltips-text) {
        padding: 0 12px;
      }
    }

    :deep(.show-tooltips-text) {
      width: 100%;
      min-width: 0;
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
