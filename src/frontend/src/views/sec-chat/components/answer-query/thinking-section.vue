<template>
  <div class="thinking-section">
    <div
      class="thinking-header"
      @click="expanded = !expanded">
      <span class="thinking-title">
        <audit-icon
          v-if="expanded"
          class="expand-icon"
          type="angle-line-up" />
        <audit-icon
          v-else
          class="expand-icon"
          type="angle-line-down" />
        思考了 {{ thinkingTime }} 秒
      </span>
    </div>
    <div
      v-show="expanded"
      class="thinking-content">
      <slot />
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { ref } from 'vue';

  defineProps<{
    thinkingTime: string;
  }>();

  const expanded = ref(false);
</script>

<style lang="postcss" scoped>
.thinking-section {
  margin-bottom: 16px;

  .thinking-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 0;
    cursor: pointer;

    .thinking-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      color: #979ba5;

      .expand-icon {
        font-size: 12px;
        color: #979ba5;
      }
    }
  }

  .thinking-content {
    padding: 12px 16px;
    font-size: 13px;
    line-height: 1.6;
    color: #63656e;
    background: #f5f7fa;
    border-radius: 6px;

    :deep(p) {
      margin: 0 0 8px;

      &:last-child {
        margin-bottom: 0;
      }
    }
  }
}
</style>
