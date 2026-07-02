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
      <bk-button
        v-bk-tooltips="conversation.pinned ? '取消置顶' : '置顶'"
        class="action-btn"
        text
        theme="default"
        @click="$emit('pin')">
        <audit-icon :type="conversation.pinned ? 'attention' : 'view-2'" />
      </bk-button>
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
    pin: [];
  }>();

  const hovered = ref(false);
</script>

<style lang="postcss" scoped>
  .conversation-item {
    position: relative;
    display: flex;
    min-height: 32px;
    padding: 6px 8px;
    cursor: pointer;
    border-radius: 4px;
    align-items: center;
    gap: 6px;

    &:hover,
    &.is-active {
      background: #e1ecff;

      .conv-title {
        color: #3a84ff;
      }
    }

    &.is-active {
      background: #e1ecff;
    }

    &.is-indent {
      padding-left: 16px;
    }

    .conv-dot {
      width: 4px;
      height: 4px;
      background: #c4c6cc;
      border-radius: 50%;
      flex-shrink: 0;
    }

    .conv-title {
      overflow: hidden;
      font-size: 13px;
      line-height: 20px;
      color: #313238;
      text-overflow: ellipsis;
      white-space: nowrap;
      flex: 1;
    }

    .conv-actions {
      display: flex;
      align-items: center;
      gap: 2px;
      flex-shrink: 0;

      .action-btn {
        display: flex;
        width: 20px;
        height: 20px;
        padding: 0;
        color: #979ba5;
        align-items: center;
        justify-content: center;

        &:hover {
          color: #3a84ff;
        }
      }
    }
  }

  .conv-menu {
    min-width: 100px;
    padding: 4px 0;

    .menu-item {
      display: flex;
      padding: 6px 12px;
      font-size: 13px;
      color: #63656e;
      cursor: pointer;
      align-items: center;
      gap: 6px;

      &:hover {
        background: #f0f1f5;
      }

      &.danger {
        color: #ea3636;

        &:hover {
          background: #fff1f1;
        }
      }
    }
  }
</style>
