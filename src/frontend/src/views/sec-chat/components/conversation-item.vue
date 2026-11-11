<template>
  <div
    class="conversation-item"
    :class="{ 'is-active': active, 'is-indent': indent }"
    @click="$emit('click')"
    @mouseenter="hovered = true"
    @mouseleave="hovered = false">
    <span class="conv-dot" />
    <span class="conv-title">{{ conversation.title }}</span>
    <div
      v-if="hovered || active"
      class="conv-actions"
      @click.stop>
      <bk-popover
        :arrow="false"
        placement="bottom-end"
        theme="light"
        trigger="click">
        <bk-button
          class="action-btn"
          text
          theme="default">
          <audit-icon type="more" />
        </bk-button>
        <template #content>
          <div class="conv-menu">
            <div
              class="menu-item danger"
              @click="$emit('delete')">
              <audit-icon type="delete" />
              <span>删除</span>
            </div>
          </div>
        </template>
      </bk-popover>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { ref } from 'vue';

  interface Conversation {
    id: string;
    title: string;
    pinned: boolean;
    groupName?: string;
    messages: any[];
    createdAt: number;
  }

  defineProps<{
    conversation: Conversation;
    active: boolean;
    indent?: boolean;
  }>();

  defineEmits<{
    click: [];
    delete: [];
  }>();

  const hovered = ref(false);
</script>

<style lang="postcss" scoped>
  .conversation-item {
    position: relative;
    display: flex;
    min-height: 32px;
    padding: var(--bk-theme-space-6) var(--bk-theme-space-8);
    cursor: pointer;
    border-radius: var(--bk-theme-tag-radius);
    align-items: center;
    gap: var(--bk-theme-space-6);

    &:hover,
    &.is-active {
      background: var(--bk-theme-fill-selected);

      .conv-title {
        color: var(--bk-theme-color-brand-2);
      }
    }

    &.is-active {
      background: var(--bk-theme-fill-selected);
    }

    &.is-indent {
      padding-left: var(--bk-theme-space-16);
    }

    .conv-dot {
      width: 4px;
      height: 4px;
      background: var(--bk-theme-border-strong);
      border-radius: 50%;
      flex-shrink: 0;
    }

    .conv-title {
      overflow: hidden;
      font-size: 13px;
      line-height: 20px;
      color: var(--bk-theme-text-strong);
      text-overflow: ellipsis;
      white-space: nowrap;
      flex: 1;
    }

    .conv-actions {
      display: flex;
      align-items: center;
      gap: var(--bk-theme-space-2);
      flex-shrink: 0;

      .action-btn {
        display: flex;
        width: 20px;
        height: 20px;
        padding: 0;
        color: var(--bk-theme-text-weak);
        align-items: center;
        justify-content: center;

        &:hover {
          color: var(--bk-theme-color-brand-2);
        }
      }
    }
  }

  .conv-menu {
    min-width: 100px;
    padding: var(--bk-theme-space-4) 0;

    .menu-item {
      display: flex;
      padding: var(--bk-theme-space-6) var(--bk-theme-space-12);
      font-size: 13px;
      color: var(--bk-theme-text-default);
      cursor: pointer;
      align-items: center;
      gap: var(--bk-theme-space-6);

      &:hover {
        background: var(--bk-theme-surface-muted);
      }

      &.danger {
        color: var(--bk-theme-color-danger-2);

        &:hover {background: var(--bk-theme-fill-danger);
        }
      }
    }
  }
</style>
