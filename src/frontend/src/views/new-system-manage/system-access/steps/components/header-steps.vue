<template>
  <div class="header-steps">
    <span
      v-for="(item,index) in stepsTitle"
      :key="item.title">
      <span
        v-if="(index + 1.5) < curStep "
        class="item-icon"
        :class="(index + 1.5) <= curStep ? 'active-check-line' : ''">
        <audit-icon
          class="btn-icon-check-line"
          type="check-line" />
      </span>
      <span
        v-else
        class="item-icon"
        :class="(index + 1) <= curStep ? 'active-item-icon' : ''">
        {{ index + 1 }}
      </span>
      <span class="item-title">{{ item.title }}</span>
      <span
        v-if="(index + 1) < stepsTitle.length"
        class="item-line"
        :class="(index + 1) <= curStep ? 'active-item-line' : ''" />
    </span>
  </div>
</template>

<script setup lang="ts">

  interface Props {
    stepsTitle: Array<Record<string, any>>;
    curStep: number;
  }

  defineProps<Props>();
</script>

<style lang="postcss" scoped>
  .header-steps {
    display: flex;
    align-items: center;
    height: 100%;

    > span {
      display: flex;
      align-items: center;
    }

    .item-icon {
      display: inline-flex;
      width: 24px;
      height: 24px;
      font-size: var(--bk-theme-font-size-sm);
      color: var(--bk-theme-text-default);
      background-color: var(--bk-theme-border-weak);
      border-radius: 50%;
      align-items: center;
      justify-content: center;
    }

    .active-item-icon {
      color: var(--bk-theme-surface-default);
      background-color: var(--bk-theme-color-brand-2);
    }

    .item-title {
      margin-left: var(--bk-theme-space-4);
      font-size: var(--bk-theme-font-size-sm);
      letter-spacing: 0;
      color: var(--bk-theme-text-default);
    }

    .item-line {
      position: relative;
      top: 1px; /* 微调线条垂直位置 */
      width: 136px;
      height: 1px;
      margin-right: var(--bk-theme-space-4);
      margin-left: var(--bk-theme-space-4);
      background-color: var(--bk-theme-border-weak);
    }

    .active-item-line {
      background-color: var(--bk-theme-color-brand-2);
    }

    .active-check-line {
      color: var(--bk-theme-color-brand-2);
      background-color: var(--bk-theme-fill-selected);
    }
  }

</style>
