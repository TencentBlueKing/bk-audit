<template>
  <div class="result-footer">
    <div class="footer-actions">
      <!-- 复制 -->
      <span v-bk-tooltips="{ content: '复制', placement: 'top' }">
        <button
          class="action-btn"
          @click="handleCopy">
          <copy />
        </button>
      </span>

      <!-- 点赞 -->
      <span v-bk-tooltips="{ content: '点赞', placement: 'top' }">
        <button
          class="action-btn"
          :class="{ active: isLiked }"
          @click="handleLike">
          <audit-icon :type="isLiked ? 'corret-fill' : 'view-2'" />
        </button>
      </span>

      <!-- 点踩 -->
      <span
        v-bk-tooltips="{ content: '点踩', placement: 'top' }"
        class="dislike-wrapper">
        <button
          class="action-btn"
          :class="{ active: isDisliked }"
          @click="toggleDislike">
          <audit-icon :type="isDisliked ? 'abnormal' : 'warning'" />
        </button>
        <!-- 自定义 Popover -->
        <teleport to="body">
          <div
            v-if="showDislikePanel"
            class="dislike-popover"
            :class="{ 'show-above': showAbove }"
            :style="dislikePanelStyle"
            @click.stop>
            <div class="popover-arrow" />
            <div class="dislike-panel">
              <div class="dislike-title">反馈原因</div>
              <div class="dislike-options">
                <div
                  v-for="reason in dislikeReasons"
                  :key="reason.value"
                  class="dislike-option"
                  :class="{ selected: selectedReason === reason.value }"
                  @click="handleDislikeSelect(reason.value)">
                  {{ reason.label }}
                </div>
                <div
                  v-if="!showOtherInput"
                  class="dislike-option full-width"
                  :class="{ selected: selectedReason === 'other' }"
                  @click="handleOtherClick">
                  其他问题
                </div>
              </div>
              <div
                v-if="showOtherInput"
                class="other-reason-section">
                <bk-input
                  v-model="otherReasonText"
                  :maxlength="100"
                  placeholder="请输入具体问题"
                  :rows="3"
                  type="textarea" />
                <div class="other-reason-actions">
                  <bk-button
                    size="small"
                    theme="primary"
                    @click="confirmOtherReason">提交反馈</bk-button>
                  <bk-button
                    size="small"
                    @click="cancelOtherReason">取消</bk-button>
                </div>
              </div>
            </div>
          </div>
          <!-- 点击外部关闭的遮罩 -->
          <div
            v-if="showDislikePanel"
            class="dislike-overlay"
            @click="closeDislikePanel" />
        </teleport>
      </span>

      <!-- 重新生成 -->
      <span v-bk-tooltips="{ content: '重新生成', placement: 'top' }">
        <button
          class="action-btn"
          @click="$emit('refresh')">
          <audit-icon type="refresh" />
        </button>
      </span>
    </div>

    <!-- 导出报告 -->
    <bk-dropdown
      :popover-options="{ clickContentAutoHide: true, trigger: 'click' }"
      @hide="exportDropdownShow = false"
      @show="exportDropdownShow = true">
      <button
        class="export-btn"
        :class="{ open: exportDropdownShow }">
        <audit-icon
          class="export-icon"
          type="download" />
        导出报告
      </button>
      <template #content>
        <bk-dropdown-menu>
          <bk-dropdown-item @click="handleExport('markdown')">
            导出 Markdown
          </bk-dropdown-item>
          <bk-dropdown-item @click="handleExport('pdf')">
            导出 PDF
          </bk-dropdown-item>
        </bk-dropdown-menu>
      </template>
    </bk-dropdown>
  </div>
</template>

<script lang="ts" setup>
  import { ref, onMounted, onUnmounted, nextTick } from 'vue';
  import { Copy } from 'bkui-vue/lib/icon';
  import { Message } from 'bkui-vue';

  defineEmits<{
    copy: [];
    like: [];
    dislike: [];
    refresh: [];
    export: [];
  }>();
  const exportDropdownShow = ref(false);
  const isLiked = ref(false);
  const isDisliked = ref(false);
  const showOtherInput = ref(false);
  const otherReasonText = ref('');
  const selectedReason = ref('');
  const showDislikePanel = ref(false);
  const dislikePanelStyle = ref<{ top: string; left: string }>({ top: '0px', left: '0px' });

  const dislikeReasons = [
    { value: 'inaccurate', label: '内容不准确' },
    { value: 'incomplete', label: '回答不完整' },
    { value: 'irrelevant', label: '与问题不相关' },
    { value: 'outdated', label: '信息过时' },
  ];

  const showAbove = ref(false);

  // 计算面板位置
  const updateDislikePanelPosition = () => {
    const btn = document.querySelector('.dislike-wrapper .action-btn') as HTMLElement;
    const popover = document.querySelector('.dislike-popover') as HTMLElement;
    if (btn) {
      const rect = btn.getBoundingClientRect();
      let panelHeight = 140;
      if (popover) {
        panelHeight = popover.offsetHeight;
      } else if (showOtherInput.value) {
        panelHeight = 260;
      }
      const spaceBelow = window.innerHeight - rect.bottom;
      const spaceAbove = rect.top;

      // 判断向上还是向下展示
      showAbove.value = spaceBelow < panelHeight && spaceAbove > panelHeight;

      if (showAbove.value) {
        dislikePanelStyle.value = {
          top: `${rect.top - panelHeight - 8}px`,
          left: `${rect.left - 24}px`,
        };
      } else {
        dislikePanelStyle.value = {
          top: `${rect.bottom + 8}px`,
          left: `${rect.left - 24}px`,
        };
      }
    }
  };

  const toggleDislike = () => {
    if (showDislikePanel.value) {
      closeDislikePanel();
    } else {
      showDislikePanel.value = true;
      showOtherInput.value = false;
      nextTick(() => {
        updateDislikePanelPosition();
      });
    }
  };

  const closeDislikePanel = () => {
    showDislikePanel.value = false;
    showOtherInput.value = false;
    otherReasonText.value = '';
    selectedReason.value = '';
  };

  // 复制
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      Message({ theme: 'success', message: '复制成功' });
    } catch {
      Message({ theme: 'error', message: '复制失败' });
    }
  };

  // 点赞
  const handleLike = () => {
    isLiked.value = !isLiked.value;
    if (isLiked.value) {
      isDisliked.value = false;
    }
  };

  // 点踩选择原因
  const handleDislikeSelect = (reason: string) => {
    selectedReason.value = reason;
    isDisliked.value = true;
    isLiked.value = false;
    closeDislikePanel();
  };

  const handleOtherClick = () => {
    selectedReason.value = 'other';
    showOtherInput.value = true;
    nextTick(() => {
      updateDislikePanelPosition();
    });
  };

  // 点踩-其他原因
  const cancelOtherReason = () => {
    showOtherInput.value = false;
    otherReasonText.value = '';
    selectedReason.value = '';
    nextTick(() => {
      updateDislikePanelPosition();
    });
  };

  const confirmOtherReason = () => {
    if (otherReasonText.value.trim()) {
      selectedReason.value = 'other';
      isDisliked.value = true;
      isLiked.value = false;
      closeDislikePanel();
    }
  };

  // 导出
  const handleExport = (type: 'markdown' | 'pdf') => {
    exportDropdownShow.value = false;
    console.log('导出类型:', type);
  };

  // 监听窗口滚动/resize 关闭面板
  const handleScroll = () => {
    if (showDislikePanel.value) {
      closeDislikePanel();
    }
  };

  onMounted(() => {
    window.addEventListener('scroll', handleScroll, true);
    window.addEventListener('resize', handleScroll);
  });

  onUnmounted(() => {
    window.removeEventListener('scroll', handleScroll, true);
    window.removeEventListener('resize', handleScroll);
  });

</script>

<style lang="postcss" scoped>
.result-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 16px;
  border-top: 1px solid #dcdee5;

  .footer-actions {
    display: flex;
    gap: 8px;

    > span {
      display: inline-flex;
    }

    .action-btn {
      display: flex;
      width: 32px;
      height: 32px;
      color: #979ba5;
      cursor: pointer;
      background: #fff;
      border: 1px solid #dcdee5;
      border-radius: 4px;
      transition: all .2s;
      align-items: center;
      justify-content: center;

      &:hover {
        color: #3a84ff;
        background: #f5f7fa;
        border-color: #3a84ff;
      }

      &.active {
        color: #3a84ff;
        background: #e6f0ff;
        border-color: #3a84ff;
      }
    }
  }

  .export-btn {
    display: flex;
    padding: 6px 12px;
    font-size: 13px;
    color: #63656e;
    cursor: pointer;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
    transition: all .2s;
    align-items: center;
    gap: 6px;

    &:hover {
      color: #3a84ff;
      background: #f5f7fa;
      border-color: #3a84ff;

      .export-icon,
      .arrow-icon {
        color: #3a84ff;
      }
    }

    &.open {
      color: #3a84ff;
      background: #e6f0ff;
      border-color: #3a84ff;

      .export-icon,
      .arrow-icon {
        color: #3a84ff;
      }
    }

    .export-icon,
    .arrow-icon {
      font-size: 14px;
      color: #63656e;
      transition: color .2s;
    }

    .arrow-icon {
      &.open {
        transform: rotate(180deg);
      }
    }
  }
}

.dislike-wrapper {
  position: relative;
}
</style>

<style lang="postcss">
.dislike-popover {
  position: fixed;
  z-index: 9999;
  width: 280px;
  padding: 16px;
  background: #fff;
  border: 1px solid #eaebef;
  border-radius: 4px;
  box-shadow: 0 2px 6px rgb(0 0 0 / 10%);

  .popover-arrow {
    position: absolute;
    width: 8px;
    height: 8px;
    background: #fff;
    border-top: 1px solid #eaebef;
    border-left: 1px solid #eaebef;
    transform: rotate(45deg);
  }

  &:not(.show-above) {
    .popover-arrow {
      top: -5px;
      left: 34px;
    }
  }

  &.show-above {
    .popover-arrow {
      bottom: -5px;
      left: 34px;
      transform: rotate(-135deg);
    }
  }

  .dislike-panel {
    .dislike-title {
      margin-bottom: 12px;
      font-size: 14px;
      line-height: 22px;
      color: #313238;
    }

    .dislike-options {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;

      .dislike-option {
        display: flex;
        height: 32px;
        font-size: 12px;
        color: #63656e;
        cursor: pointer;
        background-color: #f5f7fa;
        border-radius: 2px;
        transition: all .2s;
        flex: 1 1 calc(50% - 4px);
        align-items: center;
        justify-content: center;

        &:hover {
          background-color: #eaebef;
        }

        &.selected {
          color: #3a84ff;
          background-color: #e1ecff;
        }

        &.full-width {
          flex: 1 1 100%;
        }
      }
    }

    .other-reason-section {
      margin-top: 12px;

      .bk-textarea {
        font-size: 12px;
      }

      .other-reason-actions {
        display: flex;
        justify-content: flex-end;
        gap: 8px;
        margin-top: 12px;
      }
    }
  }
}

.dislike-overlay {
  position: fixed;
  inset: 0;
  z-index: 9998;
}
</style>
