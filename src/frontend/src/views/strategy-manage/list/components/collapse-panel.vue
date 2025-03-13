<template>
  <div class="collapse-panel">
    <div
      class="collapse-panel-title"
      @click="handleClick">
      <span>
        <audit-icon :type="isActive ? 'angle-fill-down' : 'angle-fill-rignt'" />
        {{ label }}
      </span>
      <slot name="label" />
    </div>
    <transition>
      <div v-show="isActive">
        <bk-loading :loading="loading">
          <slot />
        </bk-loading>
      </div>
    </transition>
  </div>
</template>
<script setup lang="ts">
  import {
    ref,
  } from 'vue';

  interface Props {
    label?: null | undefined | string,
    isActive?:  boolean,
  }
  const props = withDefaults(defineProps<Props>(), {
    isActive: true,
    label: '',
  });

  const loading = ref(false);

  const isActive = ref(props.isActive);

  const handleClick = () => {
    isActive.value = !isActive.value;
  };
</script>
<style scoped lang="postcss">
.collapse-panel {
  .collapse-panel-title {
    display: flex;
    height: 28px;
    padding-left: 8px;
    font-size: 14px;
    font-weight: 700;
    line-height: 28px;
    color: #63656e;
    cursor: pointer;
    background: #f0f1f5;
    align-items: center;
  }
}
</style>
