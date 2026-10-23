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

  // import SelectVerify from '@views/link-data-manage/link-data-create/components/components/select-verify.vue';
  import CustomConstantInput from './custom-constant-input.vue';

  interface Props {
    eventItem: StrategyFieldEvent['event_basic_field_configs'][0];
    eventItemKey: 'event_basic_field_configs' | 'event_data_field_configs' | 'event_evidence_field_configs' | 'risk_meta_field_config';
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
  display: flex;
  width: 100%;
  min-width: 0;
  height: 100%;
  align-items: stretch;

  :deep(.select-field-value-verify),
  :deep(.bk-select),
  :deep(.bk-select-trigger) {
    display: flex;
    flex: 1 1 auto;
    align-self: stretch;
    width: 100%;
    min-width: 0;
    height: 100%;
  }

  :deep(.bk-select .bk-input),
  :deep(.bk-select .bk-input.is-readonly),
  :deep(.bk-select .bk-input.is-simplicity) {
    width: 100%;
    height: 100%;
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 0;
    box-shadow: none;
    box-sizing: border-box;
  }

  :deep(.bk-select .bk-input--text),
  :deep(.bk-select .bk-input--suffix-icon) {
    background-color: transparent;
  }

  :deep(.bk-select:hover .bk-input),
  :deep(.bk-select.is-focus .bk-input),
  :deep(.bk-select .bk-input.is-focused),
  :deep(.bk-select:hover .bk-input.is-simplicity),
  :deep(.bk-select.is-focus .bk-input.is-simplicity) {
    background-color: #fff;
    border-color: #c4c6cc;
    box-shadow: none;
  }

  :deep(.bk-select.is-focus .bk-input),
  :deep(.bk-select .bk-input.is-focused) {
    border-color: #3a84ff;
  }
}

.no-config {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  width: 100%;
  height: 100%;
  padding: 0 12px;
  box-sizing: border-box;
}
</style>
