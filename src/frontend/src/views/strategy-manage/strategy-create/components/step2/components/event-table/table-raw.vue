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
            :event-item="eventItem"
            :event-item-key="eventItemKey"
            :field-key="valueKey"
            :select-options="localSelect"
            @add-custom-constant="addCustomConstant"
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

  import FieldCell from './field-cell.vue';

  interface Props {
    eventItemArr: StrategyFieldEvent['event_basic_field_configs'];
    eventItemKey: keyof StrategyFieldEvent;
    select: Array<DatabaseTableFieldModel>;
    strategyType: string;
  }

  const props = defineProps<Props>();
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
    'is-priority': valueKey === 'is_priority',
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
      return Promise.all((fieldCellRef.value as { getValue: () => any }[])?.map(item => item.getValue()));
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
      background-color: #f5f7fa;
    }

    &.is-priority {
      width: 120px;
    }

    &.map-config {
      width: 220px;
    }

    &.drill-config {
      width: 240px;
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
