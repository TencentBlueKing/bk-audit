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
        'is-disabled': disabled || item.disabled,
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
    disabled?: boolean;
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
    const option = props.options.find(item => item.value === value);
    if (props.disabled || option?.disabled || props.modelValue === value) {
      return;
    }
    emits('update:modelValue', value);
    emits('change', value);
  };
</script>

<style scoped lang="postcss">
.strategy-way-selector {
  display: inline-flex;
  gap: var(--audit-space-16);
}

.strategy-way-card {
  display: flex;
  width: 200px;
  height: 48px;
  padding: 0 var(--audit-space-16);
  cursor: pointer;
  background: var(--audit-neutral-bg-04);
  border: 1px solid var(--audit-neutral-border-01);
  border-radius: var(--audit-radius-container);
  transition: border-color .2s ease, background-color .2s ease;
  align-items: center;
  gap: var(--audit-space-8);
  flex: none;

  &:hover:not(.is-disabled):not(.is-active) {
    border-color: var(--audit-brand-02);
  }

  &.is-active {
    background: var(--audit-brand-06);
    border-color: var(--audit-brand-02);

    .strategy-way-card-label {
      color: var(--audit-brand-02);
    }
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
  font-size: var(--audit-font-size-sm);
  font-weight: var(--audit-font-weight-bold);
  line-height: var(--audit-line-height-sm);
  color: var(--audit-neutral-text-02);
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

<style>
.strategy-way-tips {
  width: 400px;
  word-break: break-all;
}
</style>
