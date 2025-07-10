<template>
  <div class="field-mapping">
    <!-- 必填 -->
    <select-verify
      v-if="isRequired && eventItemKey === 'event_basic_field_configs' && localEventItem.map_config"
      ref="selectVerifyRef"
      :default-value="localEventItem.map_config.source_field"
      style="width: 100%;"
      theme="background">
      <bk-select
        v-model="localEventItem.map_config.source_field"
        @select="handleSelect">
        <bk-option
          v-for="(selectItem, index) in selectOptions"
          :key="index"
          :label="selectItem.display_name"
          :value="selectItem.display_name" />
        <template #extension>
          <custom-constant-input :on-confirm="addCustomConstant" />
        </template>
      </bk-select>
    </select-verify>

    <!-- 选填 -->
    <bk-select
      v-else-if="isOptional && eventItemKey === 'event_basic_field_configs' && localEventItem.map_config"
      v-model="localEventItem.map_config.source_field"
      style="width: 100%;"
      @select="handleSelect">
      <bk-option
        v-for="(selectItem, index) in selectOptions"
        :key="index"
        :label="selectItem.display_name"
        :value="selectItem.display_name" />
      <template #extension>
        <custom-constant-input :on-confirm="addCustomConstant" />
      </template>
    </bk-select>

    <!-- 无需配置 -->
    <template v-else>
      <span class="no-config">{{ t('无需配置') }}</span>
    </template>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';
  import StrategyFieldEvent from '@model/strategy/strategy-field-event';

  import SelectVerify from '@views/link-data-manage/link-data-create/components/components/select-verify.vue';

  import CustomConstantInput from './custom-constant-input.vue';

  interface Props {
    eventItem: StrategyFieldEvent['event_basic_field_configs'][0];
    eventItemKey: keyof StrategyFieldEvent;
    selectOptions: Array<DatabaseTableFieldModel>;
    requiredFields: string[];
    optionalFields: string[];
  }

  interface Emits {
    (e: 'update:modelValue', value: string): void;
    (e: 'select', value: string): void;
    (e: 'add-custom-constant', value: string): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const { t } = useI18n();

  const selectVerifyRef = ref();

  const localEventItem = ref(props.eventItem);

  const isRequired = computed(() => props.requiredFields.includes(localEventItem.value.field_name));
  const isOptional = computed(() => props.optionalFields.includes(localEventItem.value.field_name));

  const handleSelect = (value: string) => {
    emit('update:modelValue', value);
    emit('select', value);
  };

  const addCustomConstant = (value: string) => {
    emit('add-custom-constant', value);
  };

  watch(props.eventItem, (value) => {
    localEventItem.value = value;
  });

  defineExpose({
    getValue() {
      if (!selectVerifyRef.value) {
        return Promise.resolve();
      }
      return selectVerifyRef.value.getValue();
    },
  });
</script>

<style lang="postcss" scoped>
.field-mapping {
  width: 100%;
}

.no-config {
  padding-left: 8px;
}
</style>
