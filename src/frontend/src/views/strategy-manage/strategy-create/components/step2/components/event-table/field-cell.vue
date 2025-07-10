<template>
  <div class="field-cell">
    <!-- 是否重点展示 -->
    <bk-switcher
      v-if="fieldKey === 'is_priority'"
      v-model="localEventItem.is_priority"
      theme="primary" />

    <!-- 字段映射 -->
    <field-mapping
      v-else-if="fieldKey === 'map_config' && localEventItem.map_config"
      ref="fieldMappingRef"
      :event-item="eventItem"
      :event-item-key="eventItemKey"
      :optional-fields="optionalFields"
      :required-fields="requiredFields"
      :select-options="selectOptions"
      @add-custom-constant="addCustomConstant"
      @select="handleFieldSelect" />

    <!-- 字段下钻 -->
    <bk-input
      v-else-if="fieldKey === 'drill_config' && localEventItem.drill_config"
      v-model="localEventItem.drill_config.tool.uid"
      behavior="simplicity"
      class="description-input" />

    <!-- 描述 -->
    <bk-input
      v-else-if="fieldKey === 'description'"
      v-model="localEventItem.description"
      behavior="simplicity"
      class="description-input"
      :maxlength="100"
      type="textarea" />

    <!-- 仅查看 -->
    <template v-else>
      {{ localEventItem[fieldKey] }}
    </template>
  </div>
</template>

<script setup lang="ts">
  import { ref, watch } from 'vue';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';
  import StrategyFieldEvent from '@model/strategy/strategy-field-event';

  import FieldMapping from './field-mapping.vue';

  interface Props {
    eventItem: StrategyFieldEvent['event_basic_field_configs'][0];
    eventItemKey: keyof StrategyFieldEvent;
    fieldKey: keyof StrategyFieldEvent['event_basic_field_configs'][0];
    selectOptions: Array<DatabaseTableFieldModel>;
  }

  interface Emits {
    (e: 'update:fieldValue', value: any): void;
    (e: 'select', value: string, config: StrategyFieldEvent['event_basic_field_configs'][0]): void;
    (e: 'add-custom-constant', value: string): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();

  const fieldMappingRef = ref();

  const requiredFields = ['raw_event_id', 'event_source', 'operator'];
  const optionalFields = ['event_content', 'event_type'];

  const localEventItem = ref(props.eventItem);

  const handleFieldSelect = (value: string) => {
    emit('select', value, props.eventItem);
  };

  const addCustomConstant = (value: string) => {
    emit('add-custom-constant', value);
  };

  watch(props.eventItem, (value) => {
    localEventItem.value = value;
  });

  defineExpose({
    getValue() {
      if (!fieldMappingRef.value) {
        return Promise.resolve();
      }
      return fieldMappingRef.value.getValue();
    },
  });
</script>

<style lang="postcss" scoped>
.field-cell {
  display: flex;
  width: 100%;
  height: 100%;
  align-items: center;

  :deep(.bk-input) {
    border: none;
  }

  .description-input {
    height: 45px;
    border: none;
  }
}

</style>
