<template>
  <div
    class="answer-case"
    :class="{ 'is-collapsed': !expanded }">
    <!-- 头部：思考时间 + 展开/收起 -->
    <div
      class="case-header"
      @click="toggleExpand">
      <span class="expand-icon">
        <angle-right v-if="!expanded" />
        <angle-down v-else />
      </span>
      <span class="thinking-time">思考了 {{ thinkingTime }}</span>
    </div>

    <!-- 内容区域 -->
    <transition name="case-content">
      <div
        v-show="expanded"
        class="case-body">
        <div
          class="case-content"
          v-html="renderedContent" /> <!-- eslint-disable-line vue/no-v-html -->

        <!-- 底部操作栏 -->
        <div class="case-actions">
          <button
            class="action-btn"
            title="复制"
            @click="$emit('copy')">
            <audit-icon type="copy" />
          </button>
          <button
            class="action-btn"
            title="点赞"
            @click="$emit('like')">
            <audit-icon type="corret-fill" />
          </button>
          <button
            class="action-btn"
            title="点踩"
            @click="$emit('dislike')">
            <audit-icon type="warning" />
          </button>
          <button
            class="action-btn"
            title="重新生成"
            @click="$emit('refresh')">
            <audit-icon type="refresh" />
          </button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script lang="ts" setup>
  import { ref, computed } from 'vue';
  import { AngleRight, AngleDown } from 'bkui-vue/lib/icon';

  const props = defineProps<{
    content: string;
    thinkingTime?: string;
    defaultExpanded?: boolean;
  }>();

  defineEmits<{
    copy: [];
    like: [];
    dislike: [];
    refresh: [];
  }>();

  const expanded = ref(props.defaultExpanded !== false);

  // 将换行和简单格式转为 HTML
  const renderedContent = computed(() => {
    // 先按空行分割段落，每个段落用 <p> 包裹
    const paragraphs = props.content.split('\n\n');

    return paragraphs.map((para) => {
      let html = para.trim();
      if (!html) return '';

      // 加粗文本 **text** → <strong>text</strong>
      html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

      // 处理列表项：以 - 开头的行
      if (html.includes('\n- ') || html.startsWith('- ')) {
        // 将列表项转换为 <li>
        const lines = html.split('\n');
        let inList = false;
        let result = '';

        lines.forEach((line, idx) => {
          const isListItem = line.trim().startsWith('- ');
          if (isListItem) {
            if (!inList) {
              result += '<ul>';
              inList = true;
            }
            result += `<li>${line.trim().substring(2)}</li>`;
          } else {
            if (inList) {
              result += '</ul>';
              inList = false;
            }
            if (line.trim()) {
              result += line + (idx < lines.length - 1 ? '<br>' : '');
            }
          }
        });

        if (inList) {
          result += '</ul>';
        }
        return result;
      }

      // 普通段落：内部换行转为 <br>
      return html.replace(/\n/g, '<br>');
    }).filter(Boolean)
      .join('');
  });

  const toggleExpand = () => {
    expanded.value = !expanded.value;
  };
</script>

<style lang="postcss" scoped>
.answer-case {
  overflow: hidden;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgb(0 0 0 / 6%);
  transition: box-shadow .2s;

  &:hover {
    box-shadow: 0 4px 16px rgb(0 0 0 / 10%);
  }

  .case-header {
    display: flex;
    padding: 8px 16px;
    cursor: pointer;
    background: #fafbfc;
    border-bottom: 1px solid #f0f1f5;
    transition: background .15s;
    user-select: none;
    align-items: center;
    gap: 6px;

    &:hover {
      background: #f5f6f9;
    }

    .expand-icon {
      display: flex;
      font-size: 12px;
      color: #c4c6cc;
      transition: transform .2s;
      align-items: center;
    }

    .thinking-time {
      font-size: 12px;
      line-height: 18px;
      color: #c4c6cc;
    }
  }

  .case-body {
    padding: 16px;

    .case-content {
      font-size: 14px;
      line-height: 24px;
      color: #313238;
      word-break: break-word;

      :deep(p) {
        margin: 0 0 16px;

        &:last-child {
          margin-bottom: 0;
        }
      }

      :deep(strong) {
        font-weight: 600;
        color: #1a1a2e;
      }

      :deep(ul) {
        padding: 0;
        margin: 0 0 16px;
        list-style: none;

        &:last-child {
          margin-bottom: 0;
        }

        li {
          position: relative;
          padding-left: 16px;
          margin-bottom: 4px;
          line-height: 24px;

          &:last-child {
            margin-bottom: 0;
          }

          &::before {
            position: absolute;
            top: 0;
            left: 0;
            font-weight: normal;
            color: #313238;
            content: '–';
          }
        }
      }
    }

    .case-actions {
      display: flex;
      padding-top: 12px;
      margin-top: 16px;
      border-top: 1px solid #f0f1f5;
      align-items: center;
      gap: 8px;

      .action-btn {
        display: flex;
        width: 32px;
        height: 32px;
        font-size: 16px;
        color: #c4c6cc;
        cursor: pointer;
        background: transparent;
        border: none;
        border-radius: 6px;
        transition: all .2s;
        align-items: center;
        justify-content: center;

        &:hover {
          color: #3a84ff;
          background: #f0f5ff;
        }

      }
    }
  }
}

/* 展开收起动画 */
.case-content-enter-active,
.case-content-leave-active {
  overflow: hidden;
  transition: all .25s ease;
}

.case-content-enter-from,
.case-content-leave-to {
  max-height: 0;
  opacity: 0%;
}

.case-content-enter-to,
.case-content-leave-from {
  max-height: 2000px;
  opacity: 100%;
}
</style>
