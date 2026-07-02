<template>
  <div class="tools-section">
    <div class="divider" />
    <div
      class="tools-header"
      @click="expanded = !expanded">
      <audit-icon
        v-if="expanded"
        class="expand-icon"
        type="angle-line-up" />
      <audit-icon
        v-else
        class="expand-icon"
        type="angle-line-down" />
      <span class="tools-title">已调用 {{ steps.length }} 个工具</span>
    </div>
    <div
      v-show="expanded"
      class="tools-content">
      <div
        v-for="(step, idx) in steps"
        :key="idx"
        class="tool-step"
        :class="step.status">
        <div
          class="step-header"
          @click="step.expanded = !step.expanded">
          <span class="step-icon">
            <template v-if="step.status === 'done'">
              <audit-icon
                class="done-icon"
                type="corret-fill" />
            </template>
            <template v-else-if="step.status === 'active'">
              <span class="step-spinner" />
            </template>
            <template v-else>{{ idx + 1 }}</template>
          </span>
          <span class="step-name">{{ step.name }}</span>
          <span
            v-if="step.elapsedTime"
            class="step-time-wrap">
            <audit-icon
              class="step-time-icon"
              type="shijian" />
            <span class="step-time-text">{{ step.elapsedTime }}ms</span>
          </span>
        </div>
        <div
          v-show="step.expanded"
          class="step-detail">
          <pre class="step-code">{{ step.detail }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { ref } from 'vue';

  export interface ToolStep {
    name: string;
    status: 'pending' | 'active' | 'done';
    elapsedTime?: number;
    detail: string;
    expanded: boolean;
  }

  defineProps<{
    steps: ToolStep[];
  }>();

  const expanded = ref(true);
</script>

<style lang="postcss" scoped>
.tools-section {
  margin-bottom: 16px;
  background: #fff;

  .divider {
    height: 1px;
    margin-bottom: 16px;
    background: #eaebf0;
  }

  .tools-header {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;

    .expand-icon {
      font-size: 12px;
      color: #979ba5;
      transition: transform .2s;

      &.is-expanded {
        transform: rotate(90deg);
      }
    }

    .tools-title {
      font-size: 12px;
      font-weight: 400;
      line-height: 20px;
      color: #979ba5;
    }
  }

  .tools-content {
    margin-top: 12px;
  }

  .tool-step {
    margin-bottom: 8px;
    overflow: hidden;
    border-radius: 0;

    &:last-child {
      margin-bottom: 0;
      border-bottom-right-radius: 4px;
      border-bottom-left-radius: 4px;
    }

    &:first-child {
      border-top-right-radius: 4px;
      border-top-left-radius: 4px;
    }

    &:not(:last-child) {
      border-bottom: none;
    }

    .step-header {
      display: flex;
      padding: 8px 12px;
      cursor: pointer;
      background: #f5f7fa;
      align-items: center;
      gap: 8px;

      .step-icon {
        display: inline-flex;
        width: 18px;
        height: 18px;
        font-size: 16px;
        border: 1.5px solid #c4c6cc;
        border-radius: 50%;
        align-items: center;
        justify-content: center;

        .step-spinner {
          display: inline-block;
          width: 12px;
          height: 12px;
          border: 2px solid #e1ecff;
          border-top-color: #3a84ff;
          border-radius: 50%;
          animation: spin .7s linear infinite;
        }
      }

      .step-name {
        flex: 1;
        font-size: 12px;
        font-weight: 400;
        line-height: 20px;
        color: #313238;
      }

      .step-time-wrap {
        display: inline-flex;
        align-items: center;
        gap: 4px;

        .step-time-icon {
          font-size: 14px;
          color: #979ba5;
        }

        .step-time-text {
          font-size: 12px;
          color: #979ba5;
        }
      }
    }

    .step-detail {
      padding: 12px;
      background: #fafbfd;
      border-top: 1px solid #eaebf0;

      .step-code {
        padding: 0;
        margin: 0;
        font-family: SFMono-Regular, Consolas, monospace;
        font-size: 12px;
        color: #63656e;
        word-break: break-all;
        white-space: pre-wrap;
      }
    }

    &.done .step-header .step-icon {
      background: transparent;
      border: none;

      .done-icon {
        color: #2caf5e;
      }
    }

    &.active .step-header .step-icon {
      color: #3a84ff;
      border-color: #3a84ff;
    }

    &.pending .step-header .step-icon {
      color: #c4c6cc;
      border-color: #c4c6cc;
    }
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
