<template>
  <bk-sideslider
    v-model:isShow="isShowRight"
    quick-close
    :title="t('AI智能体')"
    transfer
    :width="640">
    <template #default>
      <div class="ai-agent-drawer-content">
        <div class="form-item">
          <label class="form-label">{{ t('提示词') }}</label>
          <bk-input
            v-model="prompt"
            :placeholder="t('请输入AI提示词')"
            :rows="6"
            type="textarea" />
        </div>
      </div>
    </template>
    <template #footer>
      <div class="ai-agent-drawer-footer">
        <bk-button
          class="mr8"
          @click="handleClose">
          {{ t('取消') }}
        </bk-button>
        <bk-button
          theme="primary"
          @click="handleConfirm">
          {{ t('确认') }}
        </bk-button>
      </div>
    </template>
  </bk-sideslider>
</template>

<script setup lang="ts">
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Props {
    visible: boolean;
    initialPrompt?: string;
  }

  const props = withDefaults(defineProps<Props>(), {
    visible: false,
    initialPrompt: '',
  });

  const emit = defineEmits<{(e: 'update:visible', value: boolean): void;
                            (e: 'confirm', value: string): void;
  }>();

  const { t } = useI18n();
  const isShowRight = ref(false);
  const prompt = ref('');

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
    }
  });

  const handleClose = () => {
    isShowRight.value = false;
  };

  const handleConfirm = () => {
    emit('confirm', prompt.value);
    isShowRight.value = false;
  };
</script>

<style lang="postcss" scoped>
.ai-agent-drawer-content {
  padding: 20px;
}

.form-item {
  margin-bottom: 20px;
}

.form-label {
  display: block;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 500;
  color: #313238;
}

.ai-agent-drawer-footer {
  display: flex;
  justify-content: flex-end;
  padding: 16px 24px;
  border-top: 1px solid #dcdee5;
}
</style>

