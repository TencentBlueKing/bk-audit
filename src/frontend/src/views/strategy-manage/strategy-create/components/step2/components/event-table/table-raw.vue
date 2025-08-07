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
    <div
      v-for="(eventItem, eventItemIndex) in eventItemArr"
      :key="eventItemIndex"
      class="table-row">
      <template
        v-for="(value, valueKey) in eventItem"
        :key="valueKey">
        <div
          v-if="!excludeKey.includes(valueKey)"
          class="cell"
          :class="getCellClass(valueKey)">
          <field-cell
            ref="fieldCellRef"
            :all-tools-data="allToolsData"
            :event-item="eventItem"
            :event-item-key="eventItemKey"
            :field-key="valueKey"
            :output-fields="outputFields"
            :select-options="localSelect"
            :strategy-name="strategyName"
            :tag-data="tagData"
            @add-custom-constant="addCustomConstant"
            @open-tool="handleOpenTool"
            @select="handleSelect"
            @update:field-value="updateFieldValue(eventItem, valueKey, $event)" />
        </div>
      </template>
    </div>
  </template>
  <div
    v-else
    class="table-row empty-row">
    <div class="empty-message">
      {{ t('暂未获取到相关字段，请先进入下一步') }}
    </div>
  </div>
</template>

<script setup lang='ts'>
  import _ from 'lodash';
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';
  import StrategyFieldEvent from '@model/strategy/strategy-field-event';
  import ToolDetailModel from '@model/tool/tool-detail';

  import FieldCell from './field-cell.vue';

  interface Props {
    eventItemArr: StrategyFieldEvent['event_basic_field_configs'];
    eventItemKey: keyof StrategyFieldEvent;
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
    (e: 'openTool', value: ToolDetailModel): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const { t } = useI18n();

  const fieldCellRef = ref();

  const localSelect = ref<Array<DatabaseTableFieldModel>>([]);

  // strategyType为model时，排除map_config
  const excludeKey = computed<Array<string>>(() => {
    const initKey = ['example', 'prefix'];
    if (props.strategyType === 'model') {
      initKey.push('map_config');
    }
    return initKey;
  });

  const getCellClass = (valueKey: string) => ({
    'field-name': valueKey === 'field_name',
    'display-name': valueKey === 'display_name',
    'is-priority': valueKey === 'is_priority' || valueKey === 'is_show',
    'map-config': valueKey === 'map_config',
    'drill-config': valueKey === 'drill_config',
    description: valueKey === 'description',
  });

  const updateFieldValue = (config: any, key: string, value: any) => {
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
  const handleOpenTool = async (toolInfo: ToolDetailModel) => {
    emit('openTool', toolInfo);
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
  display: flex;

  .cell {
    display: flex;
    height: 58px;
    padding: 12px;
    border-right: 1px solid #dcdee5;
    border-bottom: 1px solid #dcdee5;
    align-items: center;

    &.field-name {
      width: 200px;
    }

    &.display-name {
      width: 200px;
    }

    &.is-priority {
      width: 120px;
    }

    &.map-config {
      width: 230px;
    }

    &.drill-config {
      width: 230px;
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
