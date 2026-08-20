<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<template>
  <div class="assign-condition-rows">
    <div
      v-for="(item, index) in modelValue"
      :key="index"
      class="condition-row">
      <bk-select
        v-model="item.field"
        class="field-select"
        filterable
        :placeholder="t('请选择字段')">
        <bk-option
          v-for="field in fieldOptions"
          :key="field.id"
          :label="field.name"
          :value="field.id" />
      </bk-select>
      <bk-select
        v-model="item.operator"
        class="operator-select"
        :placeholder="t('请选择')">
        <bk-option
          v-for="op in operatorOptions"
          :key="op.value"
          :label="op.label"
          :value="op.value" />
      </bk-select>
      <bk-input
        v-model="item.value"
        class="value-input"
        :placeholder="t('请输入值')" />
      <div class="condition-actions">
        <audit-icon
          class="action-icon"
          type="add-fill"
          @click="handleAdd(index)" />
        <audit-icon
          v-if="modelValue.length > 1"
          class="action-icon"
          type="reduce-fill"
          @click="handleRemove(index)" />
      </div>
    </div>
    <div
      class="add-condition-group"
      @click="handleAddGroup">
      <audit-icon
        style="margin-right: 4px;"
        type="add" />
      {{ t('添加条件组') }}
    </div>
  </div>
</template>
<script setup lang="ts">
  import { useI18n } from 'vue-i18n';

  export interface ConditionItem {
    field: string;
    operator: string;
    value: string;
  }

  interface Props {
    modelValue: ConditionItem[];
    fieldOptions: Array<{ id: string; name: string }>;
  }

  interface Emits {
    (e: 'update:modelValue', value: ConditionItem[]): void;
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const operatorOptions = [
    { label: '= 等于', value: 'eq' },
    { label: '!= 不等于', value: 'neq' },
    { label: '> 大于', value: 'gt' },
    { label: '>= 大于等于', value: 'gte' },
    { label: '< 小于', value: 'lt' },
    { label: '<= 小于等于', value: 'lte' },
    { label: 'in 属于', value: 'include' },
    { label: 'not in 不属于', value: 'exclude' },
  ];

  const createCondition = (): ConditionItem => ({
    field: '',
    operator: 'eq',
    value: '',
  });

  const handleAdd = (index: number) => {
    const next = [...props.modelValue];
    next.splice(index + 1, 0, createCondition());
    emits('update:modelValue', next);
  };

  const handleRemove = (index: number) => {
    if (props.modelValue.length <= 1) return;
    const next = [...props.modelValue];
    next.splice(index, 1);
    emits('update:modelValue', next);
  };

  const handleAddGroup = () => {
    emits('update:modelValue', [...props.modelValue, createCondition()]);
  };
</script>
<style lang="postcss" scoped>
.assign-condition-rows {
  .condition-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    padding: 12px;
    background: #f5f7fa;
    border: 1px solid #dcdee5;
    border-radius: 2px;

    .field-select {
      width: 220px;
      flex-shrink: 0;
    }

    .operator-select {
      width: 160px;
      flex-shrink: 0;
    }

    .value-input {
      flex: 1;
      min-width: 0;
    }

    .condition-actions {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-shrink: 0;
      color: #c4c6cc;

      .action-icon {
        font-size: 14px;
        cursor: pointer;

        &:hover {
          color: #3a84ff;
        }
      }
    }
  }

  .add-condition-group {
    display: inline-flex;
    align-items: center;
    height: 32px;
    padding: 0 8px;
    color: #3a84ff;
    cursor: pointer;
    background: #fafbfd;
    border: 1px dashed #dcdee5;
    border-radius: 2px;
  }
}
</style>
