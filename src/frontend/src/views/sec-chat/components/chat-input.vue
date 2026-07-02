<template>
  <div class="chat-input-area">
    <div class="input-wrapper">
      <div class="shortcut-commands">
        <div
          v-if="!showShortcuts"
          class="command-btn"
          @click="showShortcuts = true">
          <svg
            class="command-icon"
            height="14"
            viewBox="0 0 1024 1024"
            width="14">
            <path
              :d="commandIconPath1"
              fill="currentColor" />
            <path
              :d="commandIconPath2"
              fill="currentColor" />
          </svg>
          <span>快捷指令</span>
          <audit-icon
            class="expand-icon"
            type="angle-line-down" />
        </div>
        <div
          v-else
          class="shortcut-tags-wrapper">
          <div class="shortcut-tags">
            <div
              v-for="tag in shortcutTags"
              :key="tag.id"
              class="shortcut-tag"
              @click="selectTag(tag)">
              <audit-icon :type="tag.icon" />
              <span>{{ tag.title }}</span>
            </div>
          </div>
          <div
            class="collapse-btn"
            @click="showShortcuts = false">
            <audit-icon
              class="collapse-icon"
              type="angle-line-down" />
          </div>
        </div>
      </div>
      <div class="input-box">
        <div
          class="attach-btn"
          @click="handleAttach">
          <audit-icon
            class="attach-icon"
            type="link" />
        </div>
        <div class="input-content">
          <!-- 斜杠命令菜单 -->
          <div
            v-show="showSlashMenu"
            class="slash-menu">
            <ul class="slash-menu-list">
              <li
                v-for="(cmd, index) in shortcutTags"
                :key="cmd.id"
                class="slash-menu-item"
                :class="{ 'is-active': activeSlashIndex === index }"
                @click="selectSlashCommand(cmd)"
                @mouseenter="activeSlashIndex = index">
                <audit-icon
                  class="cmd-icon"
                  :type="cmd.icon" />
                <span class="cmd-title">{{ cmd.title }}</span>
              </li>
            </ul>
          </div>
          <textarea
            ref="textareaRef"
            v-model="inputValue"
            class="input-textarea"
            :disabled="disabled || generating"
            :placeholder="placeholder || '请输入安全问题，输入 / 唤起快捷指令，Shift+Enter 换行'"
            rows="1"
            @input="autoResize"
            @keydown="handleKeydown" />
        </div>
        <button
          v-if="generating"
          class="send-btn is-generating"
          @click="handleStop">
          <audit-icon
            class="send-icon"
            type="stop" />
        </button>
        <button
          v-else
          class="send-btn"
          :class="{ 'is-active': inputValue.trim() && !disabled }"
          :disabled="!inputValue.trim() || disabled"
          @click="handleSend">
          <audit-icon
            class="send-icon"
            type="right" />
        </button>
      </div>
      <div class="input-hint">
        SecChat 基于 AI 大模型生成回答，请注意验证关键信息的准确性
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { ref, nextTick, watch } from 'vue';

  const props = defineProps<{
    disabled?: boolean;
    generating?: boolean;
    placeholder?: string;
  }>();

  const emit = defineEmits<{
    send: [content: string];
    stop: [];
    attach: [];
  }>();

  const inputValue = ref('');
  const textareaRef = ref<HTMLTextAreaElement | null>(null);
  const showShortcuts = ref(true);
  const showSlashMenu = ref(false);
  const activeSlashIndex = ref(0);

  const commandIconPath1 = 'M846.9 177.1l-59.4-59.4c-15.6-15.6-40.9-15.6-56.6 0L216.4 632.2'
    + 'c-15.6 15.6-15.6 40.9 0 56.6l59.4 59.4c15.6 15.6 40.9 15.6 56.6 0l514.5-514.5'
    + 'c15.6-15.6 15.6-40.9 0-56.6zM304.3 660.5l-31.1-31.1 486.2-486.2 31.1 31.1-486.2 486.2z';
  const commandIconPath2 = 'M192 832h-64v-64c0-17.7-14.3-32-32-32s-32 14.3-32 32v64H0c-17.7 0-32 14.3-32 32'
    + 's14.3 32 32 32h64v64c0 17.7 14.3 32 32 32s32-14.3 32-32v-64h64c17.7 0 32-14.3 32-32s-14.3-32-32-32z'
    + 'M960 192h-64v-64c0-17.7-14.3-32-32-32s-32 14.3-32 32v64h-64c-17.7 0-32 14.3-32 32s14.3 32 32 32h64v64'
    + 'c0 17.7 14.3 32 32 32s32-14.3 32-32v-64h64c17.7 0 32-14.3 32-32s-14.3-32-32-32z';

  const shortcutTags = [
    { id: 'analyze', icon: 'analysis', title: '主机行为分析', prompt: '请帮我分析主机的异常行为' },
    { id: 'alert', icon: 'alert', title: '解读风险告警', prompt: '帮我解读主机的风险告警' },
    { id: 'event', icon: 'view', title: '查看安全事件', prompt: '请帮我查看近期未处理的安全事件' },
    { id: 'check', icon: 'check-line', title: '主机健康检查', prompt: '请对主机进行安全基线合规检查' },
    { id: 'overview', icon: 'chart', title: '安全态势总览', prompt: '请帮我了解当前全网安全态势概况' },
    { id: 'help', icon: 'help-document-fill', title: 'HIDS 使用帮助', prompt: '请介绍 HIDS 的功能配置与使用方法' },
  ];

  // 监听输入，以判断是否触发斜杠菜单
  watch(inputValue, (val) => {
    if (props.generating) return;
    // 当输入以 / 结尾且前面是空或者空白字符时，触发菜单
    if (val === '/' || val.endsWith(' /') || val.endsWith('\n/')) {
      showSlashMenu.value = true;
      activeSlashIndex.value = 0;
    } else {
      showSlashMenu.value = false;
    }
  });

  const selectSlashCommand = (cmd: typeof shortcutTags[0]) => {
    if (props.generating) return;
    // 替换掉触发斜杠的文本，填充指令内容
    const val = inputValue.value;
    const lastSlashIdx = val.lastIndexOf('/');
    if (lastSlashIdx !== -1) {
      inputValue.value = val.substring(0, lastSlashIdx) + cmd.prompt;
    } else {
      inputValue.value = cmd.prompt;
    }
    showSlashMenu.value = false;
    nextTick(() => {
      textareaRef.value?.focus();
      autoResize();
    });
  };

  const handleKeydown = (e: KeyboardEvent) => {
    if (props.generating) return;

    if (showSlashMenu.value) {
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        activeSlashIndex.value = (activeSlashIndex.value - 1 + shortcutTags.length) % shortcutTags.length;
        return;
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        activeSlashIndex.value = (activeSlashIndex.value + 1) % shortcutTags.length;
        return;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        selectSlashCommand(shortcutTags[activeSlashIndex.value]);
        return;
      }
      if (e.key === 'Escape') {
        showSlashMenu.value = false;
        return;
      }
    }

    // 默认回车发送（不是 Shift+Enter 且没有开启菜单时）
    if (e.key === 'Enter' && !e.shiftKey && !showSlashMenu.value) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = () => {
    if (!inputValue.value.trim() || props.disabled || props.generating) return;
    emit('send', inputValue.value.trim());
    inputValue.value = '';
    if (textareaRef.value) {
      textareaRef.value.style.height = 'auto';
    }
  };

  const handleStop = () => {
    emit('stop');
  };

  const selectTag = (tag: typeof shortcutTags[0]) => {
    if (props.generating) return;
    inputValue.value = tag.prompt;
    nextTick(() => {
      textareaRef.value?.focus();
      autoResize();
    });
  };

  const handleAttach = () => {
    if (props.generating) return;
    emit('attach');
  };

  const autoResize = () => {
    if (!textareaRef.value) return;
    textareaRef.value.style.height = 'auto';
    textareaRef.value.style.height = `${Math.min(textareaRef.value.scrollHeight, 160)}px`;
  };
</script>

<style lang="postcss" scoped>
  .chat-input-area {
    flex-shrink: 0;
    padding: 16px 24px 120px;
    background: #f5f7fa;

    .input-wrapper {
      max-width: 900px;
      margin: 0 auto;

      .shortcut-commands {
        display: flex;
        margin-bottom: 8px;

        .command-btn {
          display: flex;
          height: 28px;
          padding: 4px 8px;
          margin-left: -8px;
          font-size: 12px;
          color: #63656e;
          cursor: pointer;
          background: transparent;
          border: 1px solid transparent;
          border-radius: 4px;
          transition: all .2s;
          align-items: center;
          justify-content: center;
          gap: 4px;

          &:hover {
            background: #eaecf0;

            .expand-icon {
              color: #3a84ff;
            }
          }

          .expand-icon {
            margin-left: 4px;
            font-size: 14px;
            color: #979ba5;
            transform: rotate(-90deg);
            transition: color .2s;
          }

          .command-icon {
            display: flex;
            font-size: 14px;
            align-items: center;
          }
        }

        .shortcut-tags-wrapper {
          display: flex;
          align-items: center;
          width: 100%;

          .shortcut-tags {
            display: flex;
            align-items: center;
            gap: 12px;
            flex: 1;
            overflow-x: auto;

            &::-webkit-scrollbar {
              display: none;
            }

            .shortcut-tag {
              display: flex;
              padding: 6px 16px;
              font-size: 12px;
              color: #63656e;
              white-space: nowrap;
              cursor: pointer;
              background: #fff;
              border: 1px solid transparent;
              border-radius: 16px;
              transition: all .2s;
              align-items: center;
              gap: 6px;

              &:hover {
                color: #3a84ff;
                border-color: #3a84ff;
              }

              i {
                font-size: 14px;
                color: #3a84ff;
              }
            }
          }

          .collapse-btn {
            display: flex;
            width: 28px;
            height: 28px;
            margin-left: 8px;
            color: #979ba5;
            cursor: pointer;
            transition: color .2s;
            align-items: center;
            justify-content: center;

            &:hover {
              color: #3a84ff;

              .collapse-icon {
                color: #3a84ff;
              }
            }

            .collapse-icon {
              font-size: 14px;
              color: #979ba5;
              transition: color .2s;
            }

            i {
              font-size: 16px;
            }
          }
        }
      }

      .input-box {
        display: flex;
        padding: 8px 12px;
        background: #fff;
        border: 1px solid transparent;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgb(0 0 0 / 5%);
        transition: all .2s;
        align-items: flex-end;

        &:focus-within {
          border-color: #3a84ff;
          box-shadow: 0 2px 12px rgb(0 0 0 / 10%);
        }

        .attach-btn {
          display: flex;
          width: 32px;
          height: 32px;
          margin-right: 4px;
          color: #979ba5;
          cursor: pointer;
          border-radius: 4px;
          flex-shrink: 0;
          align-items: center;
          justify-content: center;

          .attach-icon {
            font-size: 18px;
          }
        }

        .input-content {
          flex: 1;
          position: relative;
          display: flex;
          align-items: center;
          min-height: 32px;
          margin: 0 8px;

          .slash-menu {
            position: absolute;
            bottom: calc(100% + 12px);
            left: 0;
            z-index: 100;
            width: 180px;
            padding: 4px 0;
            background: #fff;
            border: 1px solid #dcdee5;
            border-radius: 4px;
            box-shadow: 0 2px 6px rgb(0 0 0 / 10%);

            .slash-menu-list {
              padding: 0;
              margin: 0;
              list-style: none;

              .slash-menu-item {
                display: flex;
                padding: 8px 16px;
                color: #63656e;
                cursor: pointer;
                transition: background-color .2s;
                align-items: center;
                gap: 8px;

                &.is-active,
                &:hover {
                  color: #3a84ff;
                  background-color: #f0f1f5;
                }

                .cmd-icon {
                  font-size: 14px;
                  color: #3a84ff;
                }

                .cmd-title {
                  font-size: 14px;
                }
              }
            }
          }

          .input-textarea {
            width: 100%;
            max-height: 160px;
            min-height: 22px;
            padding: 5px 0;
            margin: 0;
            overflow-y: auto;
            font-size: 14px;
            line-height: 22px;
            color: #313238;
            background: transparent;
            border: none;
            outline: none;
            resize: none;

            &::placeholder {
              color: #c4c6cc;
            }

            &:disabled {
              color: #c4c6cc;
              cursor: not-allowed;
            }

            &::-webkit-scrollbar {
              width: 4px;
            }

            &::-webkit-scrollbar-thumb {
              background: #dcdee5;
              border-radius: 2px;
            }
          }
        }

        .send-btn {
          display: flex;
          width: 32px;
          height: 32px;
          padding: 0;
          overflow: hidden;
          cursor: pointer;
          background: transparent;
          border: none;
          border-radius: 6px;
          transition: all .2s;
          flex-shrink: 0;
          align-items: center;
          justify-content: center;

          svg,
          .send-icon {
            font-size: 18px;
            transform: translateY(2px);
          }

          &.is-generating {
            &:hover {
              opacity: 80%;
            }
          }

          &:disabled {
            cursor: not-allowed;
          }
        }
      }

      .input-hint {
        margin-top: 12px;
        font-size: 12px;
        line-height: 18px;
        color: #c4c6cc;
        text-align: center;
      }
    }
  }
</style>
