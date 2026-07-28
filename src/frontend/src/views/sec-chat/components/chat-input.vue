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
              :class="{ 'is-disabled': tag.disabled }"
              :title="tag.disabled ? '暂未开放' : undefined"
              @click="selectTag(tag)">
              <img
                v-if="tag.iconSrc"
                alt=""
                class="tag-icon-img"
                :src="tag.iconSrc">
              <ai-setting-icon
                v-else-if="tag.useSettingIcon"
                class="tag-icon-img" />
              <audit-icon
                v-else
                :type="tag.icon" />
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
                v-for="(cmd, index) in filteredSlashCommands"
                :key="cmd.id"
                class="slash-menu-item"
                :class="{
                  'is-active': activeSlashIndex === index,
                  'is-disabled': cmd.disabled,
                }"
                @mousedown.prevent="selectSlashCommand(cmd)"
                @mouseenter="!cmd.disabled && (activeSlashIndex = index)">
                <img
                  v-if="cmd.iconSrc"
                  alt=""
                  class="cmd-icon-img"
                  :src="cmd.iconSrc">
                <ai-setting-icon
                  v-else-if="cmd.useSettingIcon"
                  class="cmd-icon-img" />
                <audit-icon
                  v-else
                  class="cmd-icon"
                  :type="cmd.icon" />
                <span class="cmd-title">{{ cmd.title }}</span>
              </li>
              <li
                v-if="!filteredSlashCommands.length"
                class="slash-menu-empty">
                无匹配指令
              </li>
            </ul>
          </div>
          <textarea
            ref="textareaRef"
            v-model="inputValue"
            class="input-textarea"
            :disabled="disabled || generating"
            :placeholder="placeholder || '请输入 / 唤起快捷指令，Shift+Enter 换行'"
            rows="1"
            @click="updateSlashMenuState"
            @input="handleInput"
            @keydown="handleKeydown"
            @keyup="updateSlashMenuState" />
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
          <img
            alt=""
            class="send-icon-img"
            :src="fasongIcon">
        </button>
      </div>
      <div class="input-hint">
        AI助手 基于 AI 大模型生成回答，请注意验证关键信息的准确性
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { computed, nextTick, ref } from 'vue';

  import AiSettingIcon from './ai-setting-icon.vue';

  import biaobiaoIcon from '@images/biaobiao-icon.svg';
  import fasongIcon from '@images/fasong-icon.svg';
  import fengxianIcon from '@images/fengxian-icon.svg';
  import shiyongIcon from '@images/shiyong-icon.svg';

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
  const slashQuery = ref('');
  const slashStartIndex = ref(-1);

  const commandIconPath1 = 'M846.9 177.1l-59.4-59.4c-15.6-15.6-40.9-15.6-56.6 0L216.4 632.2'
    + 'c-15.6 15.6-15.6 40.9 0 56.6l59.4 59.4c15.6 15.6 40.9 15.6 56.6 0l514.5-514.5'
    + 'c15.6-15.6 15.6-40.9 0-56.6zM304.3 660.5l-31.1-31.1 486.2-486.2 31.1 31.1-486.2 486.2z';
  const commandIconPath2 = 'M192 832h-64v-64c0-17.7-14.3-32-32-32s-32 14.3-32 32v64H0c-17.7 0-32 14.3-32 32'
    + 's14.3 32 32 32h64v64c0 17.7 14.3 32 32 32s32-14.3 32-32v-64h64c17.7 0 32-14.3 32-32s-14.3-32-32-32z'
    + 'M960 192h-64v-64c0-17.7-14.3-32-32-32s-32 14.3-32 32v64h-64c-17.7 0-32 14.3-32 32s14.3 32 32 32h64v64'
    + 'c0 17.7 14.3 32 32 32s32-14.3 32-32v-64h64c17.7 0 32-14.3 32-32s-14.3-32-32-32z';

  const shortcutTags = [
    { id: 'log', icon: 'audit', title: '审计日志检索', prompt: '请帮我检索审计日志', disabled: false },
    { id: 'analysis', icon: 'shujutongji', title: '风险分析', prompt: '请帮我分析当前审计风险分布与趋势', disabled: true },
    { id: 'alert', icon: '', iconSrc: fengxianIcon, title: '风险解读', prompt: '帮我解读未处理的高危风险告警', disabled: true },
    { id: 'report', icon: '', iconSrc: biaobiaoIcon, title: '报表解读', prompt: '请帮我解读审计报表数据与趋势', disabled: true },
    { id: 'scene', icon: '', useSettingIcon: true, title: '场景配置', prompt: '请介绍如何配置审计场景与检测策略', disabled: true },
    { id: 'help', icon: '', iconSrc: shiyongIcon, title: '使用帮助', prompt: '请介绍审计中心的功能配置与使用方法', disabled: true },
  ];

  const enabledSlashCommands = computed(() => shortcutTags.filter(item => !item.disabled));

  const filteredSlashCommands = computed(() => {
    const keyword = slashQuery.value.trim().toLowerCase();
    const list = enabledSlashCommands.value;
    if (!keyword) return list;
    return list.filter(item => (
      item.title.toLowerCase().includes(keyword)
      || item.prompt.toLowerCase().includes(keyword)
    ));
  });

  /** 根据光标位置检测是否处于 / 指令模式 */
  const updateSlashMenuState = () => {
    if (props.generating || props.disabled) {
      showSlashMenu.value = false;
      return;
    }
    const textarea = textareaRef.value;
    const { value } = inputValue;
    const cursor = textarea?.selectionStart ?? value.length;
    const textBeforeCursor = value.slice(0, cursor);
    const match = textBeforeCursor.match(/(?:^|[\s\n])\/([^\s\n]*)$/);

    if (match) {
      slashStartIndex.value = textBeforeCursor.lastIndexOf('/');
      slashQuery.value = match[1] || '';
      showSlashMenu.value = true;
      showShortcuts.value = true;
      if (activeSlashIndex.value >= filteredSlashCommands.value.length) {
        activeSlashIndex.value = 0;
      }
    } else {
      showSlashMenu.value = false;
      slashQuery.value = '';
      slashStartIndex.value = -1;
    }
  };

  const handleInput = () => {
    autoResize();
    updateSlashMenuState();
  };

  const selectSlashCommand = (cmd: typeof shortcutTags[0]) => {
    if (props.generating || cmd.disabled) return;
    const { value } = inputValue;
    const start = slashStartIndex.value >= 0 ? slashStartIndex.value : value.lastIndexOf('/');
    const textarea = textareaRef.value;
    const cursor = textarea?.selectionStart ?? value.length;

    if (start >= 0) {
      inputValue.value = `${value.slice(0, start)}${cmd.prompt}${value.slice(cursor)}`;
    } else {
      inputValue.value = cmd.prompt;
    }

    showSlashMenu.value = false;
    slashQuery.value = '';
    slashStartIndex.value = -1;

    nextTick(() => {
      const el = textareaRef.value;
      if (!el) return;
      const pos = start >= 0 ? start + cmd.prompt.length : cmd.prompt.length;
      el.focus();
      el.setSelectionRange(pos, pos);
      autoResize();
    });
  };

  const handleKeydown = (e: KeyboardEvent) => {
    if (props.generating) return;
    // 中文输入法选词中，不拦截回车
    if (e.isComposing || e.keyCode === 229) return;

    if (showSlashMenu.value && filteredSlashCommands.value.length) {
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        const len = filteredSlashCommands.value.length;
        activeSlashIndex.value = (activeSlashIndex.value - 1 + len) % len;
        return;
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        activeSlashIndex.value = (activeSlashIndex.value + 1) % filteredSlashCommands.value.length;
        return;
      }
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        selectSlashCommand(filteredSlashCommands.value[activeSlashIndex.value]);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        showSlashMenu.value = false;
        return;
      }
    }

    // Enter 发送；Shift+Enter 换行（不 preventDefault，由 textarea 插入换行）
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
      return;
    }

    if (e.key === 'Enter' && e.shiftKey) {
      // 换行后下一帧更新高度与 / 菜单状态
      nextTick(() => {
        autoResize();
        updateSlashMenuState();
      });
    }
  };

  const handleSend = () => {
    if (!inputValue.value.trim() || props.disabled || props.generating) return;
    emit('send', inputValue.value.trim());
    inputValue.value = '';
    showSlashMenu.value = false;
    slashQuery.value = '';
    slashStartIndex.value = -1;
    if (textareaRef.value) {
      textareaRef.value.style.height = 'auto';
    }
  };

  const handleStop = () => {
    emit('stop');
  };

  const selectTag = (tag: typeof shortcutTags[0]) => {
    if (props.generating || tag.disabled) return;
    inputValue.value = tag.prompt;
    showSlashMenu.value = false;
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
    width: 100%;
    min-width: 0;
    flex-shrink: 0;
    padding: 0;
    background: transparent;
    box-sizing: border-box;

    .input-wrapper {
      width: 100%;
      max-width: 100%;
      min-width: 0;
      margin: 0;
      box-sizing: border-box;

      .shortcut-commands {
        display: flex;
        width: 100%;
        min-width: 0;
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
          min-width: 0;

          .shortcut-tags {
            display: flex;
            align-items: center;
            gap: 8px;
            flex: 1;
            min-width: 0;
            overflow-x: auto;

            &::-webkit-scrollbar {
              display: none;
            }

            .shortcut-tag {
              display: flex;
              padding: 4px 12px;
              font-size: 12px;
              color: #63656e;
              white-space: nowrap;
              cursor: pointer;
              background: #fff;
              border: 1px solid transparent;
              border-radius: 16px;
              transition: all .2s;
              align-items: center;
              gap: 4px;
              flex-shrink: 0;

              &:hover:not(.is-disabled) {
                color: #3a84ff;
                border-color: #3a84ff;
              }

              &.is-disabled {
                cursor: not-allowed;
              }

              i {
                font-size: 14px;
                color: #3a84ff;
              }

              .tag-icon-img {
                display: block;
                width: 14px;
                height: 14px;
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
        width: 100%;
        min-width: 0;
        min-height: 64px;
        padding: 12px 16px;
        overflow: visible;
        background: #fff;
        border: 1px solid #eaebf0;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgb(0 0 0 / 6%);
        transition: all .2s;
        align-items: flex-end;
        box-sizing: border-box;

        &:focus-within {
          border-color: #3a84ff;
          box-shadow: 0 2px 12px rgb(58 132 255 / 12%);
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

          &:hover {
            color: #3a84ff;
          }

          .attach-icon {
            font-size: 18px;
          }
        }

        .input-content {
          flex: 1;
          position: relative;
          display: flex;
          align-items: center;
          min-width: 0;
          min-height: 32px;
          margin: 0 8px;
          overflow: visible;

          .slash-menu {
            position: absolute;
            bottom: calc(100% + 8px);
            left: 0;
            z-index: 200;
            width: 220px;
            max-height: 280px;
            overflow: auto;
            padding: 4px 0;
            background: #fff;
            border: 1px solid #dcdee5;
            border-radius: 4px;
            box-shadow: 0 2px 10px rgb(0 0 0 / 12%);

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

                .cmd-icon-img {
                  display: block;
                  width: 14px;
                  height: 14px;
                  font-size: 14px;
                  color: #3a84ff;
                }

                .cmd-title {
                  font-size: 14px;
                }
              }

              .slash-menu-empty {
                padding: 12px 16px;
                font-size: 12px;
                color: #c4c6cc;
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
          background: #c4c6cc;
          border: none;
          border-radius: 6px;
          transition: background .2s, opacity .2s;
          flex-shrink: 0;
          align-items: center;
          justify-content: center;

          .send-icon-img {
            display: block;
            width: 18px;
            height: 18px;
          }

          svg,
          .send-icon {
            font-size: 18px;
            color: #fff;
          }

          &.is-active {
            background: linear-gradient(90deg, #0061A5 0%, #0D99FF 100%);

            &:hover {
              opacity: 92%;
            }
          }

          &.is-generating {
            background: linear-gradient(90deg, #0061A5 0%, #0D99FF 100%);

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
        margin-top: 8px;
        font-size: 12px;
        line-height: 18px;
        color: #c4c6cc;
        text-align: center;
      }
    }
  }
</style>
