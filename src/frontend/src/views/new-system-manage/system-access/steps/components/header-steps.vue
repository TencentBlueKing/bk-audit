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
      font-size: 14px;
      color: #64656c;
      background-color: #eaebf0;
      border-radius: 50%;
      align-items: center;
      justify-content: center;
    }

    .active-item-icon {
      color: #fff;
      background-color: #3a84ff;
    }

    .item-title {
      margin-left: 5px;
      font-size: 14px;
      letter-spacing: 0;
      color: #4d4f56;
    }

    .item-line {
      position: relative;
      top: 1px; /* 微调线条垂直位置 */
      width: 136px;
      height: 1px;
      margin-right: 5px;
      margin-left: 5px;
      background-color: #eaebf0;
    }

    .active-item-line {
      background-color: #3a84ff;
    }

    .active-check-line {
      color: #3a84ff;
      background-color: #e1ecff;
    }
  }

</style>
