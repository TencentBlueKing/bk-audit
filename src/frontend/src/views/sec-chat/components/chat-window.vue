<template>
  <div class="chat-window">
    <!-- 消息列表区（自动滚动） -->
    <div
      ref="messageListRef"
      class="message-list">
      <div class="message-list-inner">
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="message-row"
          :class="msg.role">
          <!-- AI 消息 - 交互式查询类型（时间+主机选择器） -->
          <template v-if="msg.role === 'assistant' && msg.type === 'query'">
            <div class="case-bubble-wrapper">
              <answer-query
                :content="msg.content"
                @confirm="(hosts: any[]) => handleQueryConfirm(msg, hosts)" />
            </div>
          </template>

          <!-- AI 消息 - 回答案例类型（无头像） -->
          <template v-else-if="msg.role === 'assistant' && msg.type === 'case'">
            <div class="case-bubble-wrapper">
              <answer-case
                :content="msg.content"
                default-expanded
                :thinking-time="msg.thinkingTime || '0.8秒'"
                @copy="handleCopy(msg)"
                @dislike="handleDislike(msg)"
                @like="handleLike(msg)"
                @refresh="handleRefresh(msg)" />
            </div>
          </template>

          <!-- AI 普通消息 -->
          <template v-else-if="msg.role === 'assistant'">
            <div class="msg-avatar assistant-avatar">
              <audit-icon type="audit" />
            </div>
            <div class="msg-bubble assistant-bubble">
              <div class="msg-content">
                {{ msg.content }}
              </div>
              <div class="msg-time">
                {{ formatTime(msg.timestamp) }}
              </div>
            </div>
          </template>

          <!-- 用户消息 -->
          <template v-else>
            <div class="msg-bubble user-bubble">
              <div class="msg-content">
                {{ msg.content }}
              </div>
              <div class="msg-time">
                {{ formatTime(msg.timestamp) }}
              </div>
            </div>
          </template>
        </div>

        <!-- 加载中 -->
        <div
          v-if="loading"
          class="message-row assistant">
          <div class="msg-avatar assistant-avatar">
            <audit-icon type="audit" />
          </div>
          <div class="msg-bubble assistant-bubble loading-bubble">
            <div class="typing-indicator">
              <span />
              <span />
              <span />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部输入区（固定不被压缩） -->
    <chat-input
      :generating="loading"
      placeholder="请输入安全问题，输入 / 唤起快捷指令，Shift+Enter 换行"
      @send="$emit('send', $event)"
      @stop="$emit('stop')" />
  </div>
</template>

<script lang="ts" setup>
  import { nextTick, ref, watch } from 'vue';
  import AnswerCase from './answer-case.vue';
  import AnswerQuery from './answer-query/index.vue';
  import ChatInput from './chat-input.vue';

  interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: number;
    // 案例回答类型字段（可选）
    type?: 'case' | 'query';
    thinkingTime?: string;
  }

  const props = defineProps<{
    messages: Message[];
    loading: boolean;
  }>();

  const emit = defineEmits<{
    send: [content: string];
    stop: [];
    'refresh-answer': [msgId: string];
  }>();

  const messageListRef = ref<HTMLElement | null>(null);

  // 消息更新时自动滚动到底部
  watch(
    () => [props.messages.length, props.loading],
    async () => {
      await nextTick();
      if (messageListRef.value) {
        messageListRef.value.scrollTop = messageListRef.value.scrollHeight;
      }
    },
  );

  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp);
    const h = date.getHours()
      .toString()
      .padStart(2, '0');
    const m = date.getMinutes()
      .toString()
      .padStart(2, '0');
    return `${h}:${m}`;
  };

  // 回答案例操作
  const handleCopy = (msg: Message) => {
    navigator.clipboard?.writeText(msg.content).then(() => {
      // TODO: 可加 toast 提示
      console.log('已复制回答内容');
    });
  };

  const handleLike = (msg: Message) => {
    console.log('点赞', msg.id);
  };

  const handleDislike = (msg: Message) => {
    console.log('点踩', msg.id);
  };

  const handleRefresh = (msg: Message) => {
    emit('refresh-answer', msg.id);
  };

  const handleQueryConfirm = (msg: Message, hosts: any[]) => {
    console.log('查询确认', msg.id, hosts, '台主机');
    // TODO: 触发实际分析请求
  };
</script>

<style lang="postcss" scoped>
  .chat-window {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;

    .message-list {
      padding: 24px 24px 0;
      overflow-y: auto;
      flex: 1;

      &::-webkit-scrollbar {
        width: 4px;
      }

      &::-webkit-scrollbar-thumb {
        background: #dcdee5;
        border-radius: 2px;
      }

      .message-list-inner {
        display: flex;
        max-width: 900px;
        padding-bottom: 40px;
        margin: 0 auto;
        flex-direction: column;
        gap: 20px;
      }

      .message-row {
        display: flex;
        align-items: flex-start;
        gap: 12px;

        &.user {
          flex-direction: row-reverse;
        }

        .msg-avatar {
          display: flex;
          width: 36px;
          height: 36px;
          border-radius: 50%;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;

          i {
            font-size: 18px;
          }

          &.assistant-avatar {
            background: linear-gradient(135deg, #4a9eff 0%, #3a84ff 100%);

            i {
              color: #fff;
            }
          }

          &.user-avatar {
            background: #e1ecff;

            i {
              color: #3a84ff;
            }
          }
        }

        /* 案例回答容器（自适应内容宽度） */
        .case-bubble-wrapper {
          width: 100%;
          max-width: 100%;
        }

        .msg-bubble {
          max-width: 80%;
          padding: 12px 16px;

          .msg-content {
            font-size: 14px;
            line-height: 22px;
            word-break: break-word;
          }

          .msg-time {
            margin-top: 8px;
            font-size: 11px;
            color: #c4c6cc;
            text-align: right;
          }

          &.assistant-bubble {
            background: #fff;
            border: 1px solid #dcdee5;
            border-radius: 0 12px 12px;

            .msg-content {
              color: #313238;
            }
          }

          &.user-bubble {
            background: #3a84ff;
            border-radius: 12px 0 12px 12px;

            .msg-content {
              color: #fff;
            }

            .msg-time {
              color: rgb(255 255 255 / 60%);
            }
          }

          &.loading-bubble {
            padding: 14px 16px;
          }
        }
      }
    }
  }

  .typing-indicator {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 20px;

    span {
      width: 6px;
      height: 6px;
      background: #c4c6cc;
      border-radius: 50%;
      animation: typing 1.2s infinite;

      &:nth-child(2) {
        animation-delay: .2s;
      }

      &:nth-child(3) {
        animation-delay: .4s;
      }
    }
  }

  @keyframes typing {
    0%,
    60%,
    100% {
      opacity: 40%;
      transform: translateY(0);
    }

    30% {
      opacity: 100%;
      transform: translateY(-6px);
    }
  }
</style>
