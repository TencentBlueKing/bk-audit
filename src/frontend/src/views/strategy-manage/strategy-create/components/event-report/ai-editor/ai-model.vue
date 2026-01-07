<template>
  <bk-sideslider
    v-model:isShow="isShowRight"
    class="ai-agent-drawer"
    quick-close
    :title="t('引用 AI 智能体')"
    transfer
    :width="740">
    <template #default>
      <div
        :class="isPreviewExpanded ? `ai-agent-drawer-content-preview` : `ai-agent-drawer-content`">
        <div class="tips-title">
          <audit-icon
            class="info-fill-icon"
            type="info-fill" />
          <span>{{ t('当前策略尚未产生风险单，暂时无法预览 AI 生成的内容') }}</span>
        </div>

        <bk-form
          class="example"
          form-type="vertical"
          :model="formData"
          :rules="rules">
          <bk-form-item
            :label="t('名称')"
            property="name"
            required>
            <bk-input
              v-model="formData.name"
              clearable
              placeholder="请输入" />
          </bk-form-item>
          <bk-form-item
            :label="t('AI 提示词')"
            property="dec"
            required>
            <bk-input
              v-model="formData.dec"
              class="ai-prompt-textarea"
              :placeholder="t('请输入 AI 提示词，指导 AI 如何生成这部分内容')"
              :resize="false"
              :rows="textareaRows"
              style="border-radius: 4px;"
              type="textarea" />
          </bk-form-item>

          <bk-form-item :label="t('关联审计风险单')">
            <bk-select
              v-model="formData.risk"
              class="risks-bk-select">
              <bk-option
                v-for="(item, index) in datasource"
                :id="item.value"
                :key="index"
                :name="item.label" />
            </bk-select>
          </bk-form-item>
        </bk-form>
        <div class="ai-agent-drawer-footer">
          <div
            class="ai-agent-insert-btn mr8"
            @click="handleConfirm">
            {{ t('插入') }}
          </div>
          <bk-button
            class="mr8"
            outline
            theme="primary"
            @click="handlePreview">
            {{ t('预览') }}
          </bk-button>
          <bk-button
            class="ai-agent-cancel-btn"
            @click="handleClose">
            {{ t('取消') }}
          </bk-button>
        </div>
      </div>
    </template>
    <template #footer>
      <div
        class="preview"
        @click="handlePreviewFooter">
        <audit-icon
          class="preview-angle-line-up"
          :class="{ 'rotated': isPreviewExpanded }"
          type="angle-line-up" />
        <div class="preview-title">
          <span>{{ t('AI 生成内容预览') }}</span>
        </div>
      </div>
    </template>
  </bk-sideslider>
</template>

<script setup lang="ts">
  import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Props {
    visible: boolean;
    initialPrompt?: string;
  }
  interface Emits {
    (e: 'update:visible', value: boolean): void;
    (e: 'confirm', value: string): void;
  }
  const props = withDefaults(defineProps<Props>(), {
    initialPrompt: '',
  });
  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const isShowRight = ref(false);
  const prompt = ref('');
  const textareaRows = ref(6);
  const isPreviewExpanded = ref(false);
  const formData = ref({
    name: '',
    dec: '',
    risk: '',
  });
  const rules = ref({});
  const datasource = ref([
    {
      value: 1,
      label: '爬山',
    },
    {
      value: 2,
      label: '跑步',
    },
    {
      value: 3,
      label: '未知',
    },
    {
      value: 4,
      label: '健身',
    },
    {
      value: 5,
      label: '骑车',
    },
    {
      value: 6,
      label: '跳舞',
    },
  ]);

  const handleClose = () => {
    isShowRight.value = false;
  };

  const handleConfirm = () => {
    emit('confirm', prompt.value);
    isShowRight.value = false;
  };

  const handlePreview = () => {
  };

  const handlePreviewFooter = () => {
    isPreviewExpanded.value = !isPreviewExpanded.value;
    // 延迟计算 rows，让高度过渡动画先完成，使过渡更平滑
    nextTick(() => {
      setTimeout(() => {
        calculateTextareaRows();
      }, 300);
    });
  };

  // 计算 textarea 的 rows 值（基于页面高度的 50%）
  const calculateTextareaRows = () => {
    if (isPreviewExpanded.value) {
      textareaRows.value = 3;
      return;
    }
    // 获取视口高度
    const viewportHeight = window.innerHeight;
    // 计算目标高度（视口高度的 50%）
    const targetHeight = viewportHeight *  0.6;
    // textarea 每行高度大约为 22px（包括行间距和 padding）
    const lineHeight = 22;
    // 计算行数
    const calculatedRows = Math.floor(targetHeight / lineHeight);
    // 设置最小和最大行数限制
    textareaRows.value = Math.max(10, Math.min(calculatedRows, 50));
    console.log('textareaRows', textareaRows.value);
  };

  // 窗口大小变化时重新计算
  const handleResize = () => {
    calculateTextareaRows();
  };


  // 组件挂载时计算并监听窗口大小变化
  onMounted(() => {
    calculateTextareaRows();
    window.addEventListener('resize', handleResize);
  });

  // 组件卸载时移除事件监听
  onUnmounted(() => {
    window.removeEventListener('resize', handleResize);
  });

  // 同步 visible 和 isShowRight
  watch(() => props.visible, (newVal) => {
    isShowRight.value = newVal;
    if (newVal) {
      prompt.value = props.initialPrompt || '';
    }
  }, { immediate: true });

  watch(() => isShowRight.value, (newVal) => {
    if (!newVal) {
      emit('update:visible', false);
    } else {
      // 弹窗打开时重新计算 rows
      setTimeout(() => {
        calculateTextareaRows();
      }, 100);
    }
  });
</script>

<style lang="postcss" scoped>
.ai-agent-drawer-content,
.ai-agent-drawer-content-preview {
  width: calc(100% - 100px);
  margin-left: 50px;
  overflow: hidden;
  transition: height .4s cubic-bezier(.4, 0, .2, 1);
}

.ai-agent-drawer-content {
  height: calc(100vh - 130px);
}

.ai-agent-drawer-content-preview {
  height: 40vh;
}

.tips-title {
  display: flex;
  width: 100%;
  height: 32px;
  margin-top: 28px;
  font-size: 12px;
  line-height: 32px;
  color: #4d4f56;
  background: #f0f5ff;
  border: 1px solid #a3c5fd;
  border-radius: 2px;

  .info-fill-icon {
    margin-right: 9px;
    margin-left: 9px;
    font-size: 14px;
    line-height: 32px;
    color: #3a84ff;
  }
}

.example {
  margin-top: 20px;
  transition: opacity .3s ease;
}


.ai-agent-drawer-footer {
  display: flex;

  .ai-agent-insert-btn {
    width: 88px;
    height: 32px;
    font-size: 14px;
    line-height: 32px;
    color: #fff;
    text-align: center;
    cursor: pointer;
    background: linear-gradient(117deg, #235dfa 26%, #eb8cec 100%);
    border: none;
    border-radius: 2px;
    box-shadow: 0 1px 2px rgb(0 0 0 / 8%);
  }
}

.preview {
  position: absolute;
  bottom: 0;
  width: 100%;
  height: 100%;
  margin-top: 20px;
  line-height: 52px;
  cursor: pointer;
  background: #fff;
  border-top: 1px solid #dde4eb;
  transition: background-color .2s ease;

  &:hover {
    background-color: #f5f7fa;
  }

  .preview-angle-line-up {
    position: absolute;
    left: -10px;
    font-size: 14px;
    line-height: 52px;
    transition: transform .4s cubic-bezier(.4, 0, .2, 1);
    transform-origin: center;

    &.rotated {
      transform: rotate(180deg);
    }
  }

  .preview-title {
    margin-left: 15px;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0;
    color: #4d4f56;
  }
}

.ai-agent-drawer {
  :deep(.bk-modal-body) {
    position: relative;
    padding-bottom: 52px; /* 为底部 preview 预留空间 */
    background-color: #f5f7fa;
  }

  :deep(.bk-modal-footer) {
    height: 52px;
    background-color: #fff ;

    .bk-sideslider-footer {
      background-color: #fff ;
    }
  }
}
</style>
