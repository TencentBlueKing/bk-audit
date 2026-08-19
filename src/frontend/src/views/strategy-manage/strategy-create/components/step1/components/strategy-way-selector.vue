<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<template>
  <div class="strategy-way-selector">
    <div
      v-for="item in options"
      :key="item.value"
      class="strategy-way-card"
      :class="{
        'is-active': modelValue === item.value,
        'is-disabled': disabled,
      }"
      @click="handleSelect(item.value)">
      <div class="strategy-way-card-icon">
        <img
          :alt="item.label"
          class="strategy-way-card-icon-img"
          :src="item.icon">
      </div>
      <span
        v-bk-tooltips="{
          content: item.tips,
          extCls: 'strategy-way-tips',
          placement: 'top-start',
        }"
        class="strategy-way-card-label">
        {{ item.label }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
  interface WayOption {
    label: string;
    value: string;
    icon: string;
    tips?: string;
  }

  interface Props {
    modelValue: string;
    options: WayOption[];
    disabled?: boolean;
  }

  interface Emits {
    (e: 'update:modelValue', value: string): void;
    (e: 'change', value: string): void;
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const handleSelect = (value: string) => {
    if (props.disabled || props.modelValue === value) {
      return;
    }
    emits('update:modelValue', value);
    emits('change', value);
  };
</script>

<style scoped lang="postcss">
.strategy-way-selector {
  display: inline-flex;
  gap: 16px;
}

.strategy-way-card {
  display: flex;
  width: 240px;
  height: 56px;
  padding: 0 20px;
  cursor: pointer;
  background: #fff;
  border: 1px solid #dcdee5;
  border-radius: 2px;
  transition: all .2s ease;
  align-items: center;
  flex: none;

  &:hover:not(.is-disabled):not(.is-active) {
    border-color: #3a84ff;
  }

  &.is-active {
    background: #f0f5ff;
    border-color: #3a84ff;
  }

  &.is-disabled {
    cursor: not-allowed;
    opacity: .6;
  }
}

.strategy-way-card-icon {
  display: flex;
  width: 24px;
  height: 24px;
  margin-right: 12px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;

  .strategy-way-card-icon-img {
    display: block;
    width: 24px;
    height: 24px;
  }
}

.strategy-way-card-label {
  overflow: hidden;
  font-size: 14px;
  line-height: 22px;
  color: #313238;
  text-overflow: ellipsis;
  white-space: nowrap;
  border-bottom: 1px dashed #979ba5;
}
</style>

<style>
.strategy-way-tips {
  width: 400px;
  word-break: break-all;
}
</style>
