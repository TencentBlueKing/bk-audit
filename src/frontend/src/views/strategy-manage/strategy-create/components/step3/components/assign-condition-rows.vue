<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<template>
  <div
    class="assign-condition-rows"
    :class="{ 'has-condition': formState.groups.length > 1 }">
    <div class="rule-item-wrap">
      <div
        v-for="(group, groupIndex) in formState.groups"
        :key="groupIndex"
        class="rule-item"
        :style="{ paddingLeft: getGroupPaddingLeft(group) }">
        <template v-if="formState.groups.length > 1">
          <div class="row-line" />
          <div
            v-if="groupIndex > 0"
            class="column-line column-line-top" />
          <div
            v-if="groupIndex < formState.groups.length - 1"
            class="column-line column-line-bottom" />
        </template>
        <div
          v-for="(item, index) in group.conditions"
          :key="item.uid"
          class="rule-item-field"
          :style="{ marginBottom: index === group.conditions.length - 1 ? '0px' : '8px' }">
          <div
            v-if="group.conditions.length > 1"
            class="inner-row-line" />
          <div
            v-if="index < group.conditions.length - 1"
            class="inner-column-line" />
          <bk-select
            filterable
            :model-value="item.field"
            :placeholder="t('请选择字段')"
            :popover-options="{ placement: 'top-start' }"
            @change="(val: string) => handleFieldChange(groupIndex, index, val)">
            <bk-option
              v-for="field in fieldOptions"
              :key="field.id"
              :label="field.name"
              :value="field.id" />
          </bk-select>
          <bk-select
            :model-value="item.operator"
            :placeholder="t('请选择')"
            :popover-options="{ placement: 'top-start' }"
            @change="(val: string) => handleOperatorChange(groupIndex, index, val)">
            <bk-option
              v-for="op in operatorOptions"
              :key="op.value"
              :label="op.label"
              :value="op.value" />
          </bk-select>
          <bk-input
            :model-value="item.value"
            :placeholder="t('请输入值')"
            @update:model-value="(val: string) => handleValueChange(groupIndex, index, val)" />
          <div class="icon-group">
            <audit-icon
              style="margin-right: 10px; cursor: pointer;"
              type="add-fill"
              @click="handleAddRow(groupIndex, index)" />
            <audit-icon
              v-if="group.conditions.length > 1"
              style="cursor: pointer;"
              type="reduce-fill"
              @click="handleRemoveRow(groupIndex, index)" />
          </div>
        </div>
        <div
          v-if="group.conditions.length > 1"
          class="inner-condition"
          @click="handleChangeGroupConnector(groupIndex)">
          {{ group.connector }}
        </div>
        <audit-icon
          v-if="formState.groups.length > 1"
          class="delete-conditions"
          style="font-size: 14px;"
          type="delete"
          @click="handleRemoveGroup(groupIndex)" />
      </div>
      <div
        v-if="formState.groups.length > 1"
        class="condition"
        @click="handleChangeOuterConnector">
        {{ formState.connector }}
      </div>
    </div>
    <div
      class="add-rule-item"
      @click="handleAddGroup">
      <audit-icon
        style="margin: 0 6px;"
        type="add" />
      <span>{{ t('添加条件组') }}</span>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import {
    type AssignConditionForm,
    type AssignConditionGroup,
    createDefaultAssignConditionForm,
    dispatchToAssignConditionForm,
    isAssignConditionForm,
  } from '../../../utils/strategy-protocol';

  interface ConditionRow {
    uid: number;
    field: string;
    operator: string;
    value: string;
  }

  interface InternalGroup extends Omit<AssignConditionGroup, 'conditions'> {
    conditions: ConditionRow[];
  }

  interface InternalForm {
    connector: 'and' | 'or';
    groups: InternalGroup[];
  }

  interface Props {
    modelValue: AssignConditionForm | Array<{ field: string; operator: string; value: string }>;
    fieldOptions: Array<{ id: string; name: string }>;
  }

  interface Emits {
    (e: 'update:modelValue', value: AssignConditionForm): void;
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

  let rowUid = 1;
  const createCondition = (overrides: Partial<ConditionRow> = {}): ConditionRow => {
    const next = {
      uid: rowUid,
      field: '',
      operator: 'eq',
      value: '',
      ...overrides,
    };
    rowUid += 1;
    return next;
  };

  const toInternalForm = (value: Props['modelValue']): InternalForm => {
    const normalized = isAssignConditionForm(value)
      ? value
      : dispatchToAssignConditionForm(Array.isArray(value) ? value : undefined);
    return {
      connector: normalized.connector,
      groups: normalized.groups.map(group => ({
        connector: group.connector,
        conditions: group.conditions.length
          ? group.conditions.map(row => createCondition({ ...row }))
          : [createCondition()],
      })),
    };
  };

  const toEmitValue = (): AssignConditionForm => ({
    connector: formState.value.connector,
    groups: formState.value.groups.map(group => ({
      connector: group.connector,
      conditions: group.conditions.map(({ field, operator, value }) => ({
        field,
        operator,
        value,
      })),
    })),
  });

  const formState = ref<InternalForm>(toInternalForm(createDefaultAssignConditionForm()));
  let lastEmitted = '';

  const getGroupPaddingLeft = (group: InternalGroup) => {
    const hasNested = formState.value.groups.some(item => item.conditions.length > 1);
    if (group.conditions.length > 1 || hasNested) {
      return '55px';
    }
    return '16px';
  };

  const emitChange = () => {
    const next = toEmitValue();
    lastEmitted = JSON.stringify(next);
    emits('update:modelValue', next);
  };

  const handleFieldChange = (groupIndex: number, index: number, val: string) => {
    formState.value.groups[groupIndex].conditions[index].field = val;
    emitChange();
  };

  const handleOperatorChange = (groupIndex: number, index: number, val: string) => {
    formState.value.groups[groupIndex].conditions[index].operator = val;
    emitChange();
  };

  const handleValueChange = (groupIndex: number, index: number, val: string) => {
    formState.value.groups[groupIndex].conditions[index].value = val;
    emitChange();
  };

  const handleAddRow = (groupIndex: number, index: number) => {
    formState.value.groups[groupIndex].conditions.splice(index + 1, 0, createCondition());
    emitChange();
  };

  const handleRemoveRow = (groupIndex: number, index: number) => {
    if (formState.value.groups[groupIndex].conditions.length <= 1) return;
    formState.value.groups[groupIndex].conditions.splice(index, 1);
    emitChange();
  };

  const handleAddGroup = () => {
    formState.value.groups.push({
      connector: 'and',
      conditions: [createCondition()],
    });
    emitChange();
  };

  const handleRemoveGroup = (groupIndex: number) => {
    if (formState.value.groups.length <= 1) return;
    formState.value.groups.splice(groupIndex, 1);
    emitChange();
  };

  const handleChangeGroupConnector = (groupIndex: number) => {
    const group = formState.value.groups[groupIndex];
    group.connector = group.connector === 'and' ? 'or' : 'and';
    emitChange();
  };

  const handleChangeOuterConnector = () => {
    formState.value.connector = formState.value.connector === 'and' ? 'or' : 'and';
    emitChange();
  };

  watch(
    () => props.modelValue,
    (value) => {
      const incoming = JSON.stringify(isAssignConditionForm(value)
        ? value
        : dispatchToAssignConditionForm(Array.isArray(value) ? value : undefined));
      if (incoming === lastEmitted) return;
      lastEmitted = incoming;
      formState.value = toInternalForm(value ?? createDefaultAssignConditionForm());
    },
    { immediate: true, deep: true },
  );
</script>
<style lang="postcss" scoped>
.assign-condition-rows {
  .rule-item-wrap {
    position: relative;

    .condition {
      position: absolute;
      top: calc(50% - 14px);
      left: -38px;
      width: 28px;
      height: 28px;
      line-height: 28px;
      color: #f5b401;
      text-align: center;
      cursor: pointer;
      background: #fff;
      border: 1px solid #f5b401;
      border-radius: 2px;
    }

    .rule-item {
      position: relative;
      padding: 16px;
      padding-right: 25px;
      margin-bottom: 16px;
      background: #f5f7fa;
      flex: 1;

      .row-line {
        position: absolute;
        top: 50%;
        left: -25px;
        width: 25px;
        height: 0;
        border-top: 1px dashed #dcdee5;
      }

      .column-line {
        position: absolute;
        left: -25px;
        width: 0;
        height: calc(50% + 8px);
        border-left: 1px dashed #dcdee5;
      }

      .column-line-top {
        top: 0;
        transform: translateY(-8px);
      }

      .column-line-bottom {
        top: 50%;
      }

      .delete-conditions {
        position: absolute;
        top: 5px;
        right: 5px;
        color: #979ba5;
        cursor: pointer;
      }

      .inner-condition {
        position: absolute;
        top: calc(50% - 14px);
        left: 14px;
        width: 28px;
        height: 28px;
        line-height: 28px;
        color: #f5b401;
        text-align: center;
        cursor: pointer;
        background: #fff;
        border: 1px solid #f5b401;
        border-radius: 2px;
      }
    }
  }

  .rule-item-field {
    position: relative;
    display: grid;
    grid-template-columns: 300px 180px 1fr minmax(65px, auto);
    gap: 8px;

    .inner-row-line {
      position: absolute;
      top: 16px;
      left: -25px;
      width: 25px;
      height: 0;
      border-top: 1px dashed #dcdee5;
    }

    .inner-column-line {
      position: absolute;
      top: 16px;
      left: -25px;
      width: 0;
      height: 40px;
      border-left: 1px dashed #dcdee5;
    }

    .icon-group {
      display: flex;
      align-items: center;
      font-size: 14px;
      color: #c4c6cc;
    }
  }

  .add-rule-item {
    display: flex;
    height: 32px;
    padding: 0 5px;
    color: #3a84ff;
    cursor: pointer;
    background: #fafbfd;
    border: 1px dashed #dcdee5;
    border-radius: 2px;
    align-items: center;
  }

  &.has-condition {
    width: calc(100% - 35px);
    transform: translateX(35px);
  }
}
</style>
