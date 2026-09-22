<template>
  <bk-dialog
    v-model:is-show="isShow"
    :esc-close="false"
    :quick-close="false"
    :title="t('批量确认风险单')"
    width="720"
    @closed="resetForm">
    <div
      class="batch-confirm-wrap"
      data-testid="batch-confirm-dialog">
      <audit-form
        ref="formRef"
        form-type="vertical"
        :model="formData"
        :rules="rules">
        <bk-form-item
          :label="t('确认结果')"
          property="confirm_result"
          required>
          <bk-radio-group
            v-model="formData.confirm_result"
            class="batch-confirm-radios">
            <bk-radio label="confirm">
              {{ t('风险确认') }}
            </bk-radio>
            <bk-radio label="misreport">
              {{ t('标记误报') }}
            </bk-radio>
          </bk-radio-group>
        </bk-form-item>
        <bk-form-item
          v-if="formData.confirm_result === 'confirm'"
          :label="t('确认说明')"
          property="description">
          <rich-editor
            :key="`${editorKey}-confirm`"
            v-model:content="formData.description"
            class="await-deal-rich-editor"
            :default="formData.description"
            :event-fields="eventFields"
            :max-len="1000"
            :risk-fields="riskFields"
            support-variable />
        </bk-form-item>
        <template v-else>
          <bk-alert
            class="misreport-alert"
            theme="warning"
            :title="t('标记误报后，风险单会自动关闭，请谨慎确认是否为误报？')" />
          <bk-form-item
            class="is-required"
            :label="t('误报说明')"
            property="description"
            required>
            <rich-editor
              :key="`${editorKey}-misreport`"
              v-model:content="formData.description"
              class="await-deal-rich-editor"
              :default="formData.description"
              :event-fields="eventFields"
              :max-len="1000"
              :risk-fields="riskFields"
              support-variable />
          </bk-form-item>
        </template>
      </audit-form>
      <div
        v-if="failures.length"
        class="batch-confirm-failures"
        data-testid="batch-handle-failures">
        <div class="batch-confirm-failures__title">
          {{ t('部分风险处理失败') }}
        </div>
        <div
          v-for="item in failures"
          :key="item.risk_id">
          {{ item.risk_id }}：{{ item.reason }}
        </div>
      </div>
    </div>
    <template #footer>
      <bk-button
        data-testid="batch-confirm-submit"
        :loading="isSubmitting"
        theme="primary"
        @click="handleSubmit">
        {{ t('确定') }}
      </bk-button>
      <bk-button
        class="ml8"
        :disabled="isSubmitting"
        @click="isShow = false">
        {{ t('取消') }}
      </bk-button>
    </template>
  </bk-dialog>
</template>

<script setup lang="ts">
  import DOMPurify from 'dompurify';
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import useMessage from '@hooks/use-message';

  import RichEditor from '@components/editor/index.vue';

  import { submitBatchConfirm } from '../adapter';

  interface FieldItem {
    id: string;
    name: string;
  }

  interface Props {
    riskIds: string[];
    riskFields?: FieldItem[];
    eventFields?: FieldItem[];
  }

  const props = withDefaults(defineProps<Props>(), {
    riskFields: () => [],
    eventFields: () => [],
  });

  const emit = defineEmits<{(e: 'success'): void }>();
  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const isShow = ref(false);
  const isSubmitting = ref(false);
  const editorKey = ref(0);
  const formRef = ref();
  const failures = ref<Array<{ risk_id: string; reason: string }>>([]);
  const formData = ref({
    confirm_result: 'confirm',
    description: '',
  });

  const isRichTextNotEmpty = (html: string) => {
    if (!html) {
      return false;
    }
    return DOMPurify.sanitize(html, { ALLOWED_TAGS: [] }).trim().length > 0;
  };

  const rules = {
    confirm_result: [{
      required: true,
      message: t('请选择确认结果'),
      trigger: 'change',
    }],
    description: [{
      validator: (value: string) => formData.value.confirm_result !== 'misreport' || isRichTextNotEmpty(value),
      message: t('说明不能为空'),
      trigger: 'change',
    }],
  };

  watch(() => formData.value.confirm_result, () => {
    formRef.value?.clearValidate?.('description');
  });

  const resetForm = () => {
    formData.value = {
      confirm_result: 'confirm',
      description: '',
    };
    failures.value = [];
    editorKey.value += 1;
    formRef.value?.clearValidate?.();
  };

  const open = () => {
    resetForm();
    isShow.value = true;
  };

  const handleSubmit = async () => {
    try {
      await formRef.value?.validate?.();
    } catch {
      return;
    }
    if (!props.riskIds.length || isSubmitting.value) {
      return;
    }
    isSubmitting.value = true;
    failures.value = [];
    try {
      const receipt = await submitBatchConfirm({
        result: formData.value.confirm_result as 'confirm' | 'misreport',
        riskIds: props.riskIds,
        description: formData.value.description,
      });
      if (receipt.failed.length) {
        failures.value = receipt.failed;
        return;
      }
      messageSuccess(t('操作成功'));
      isShow.value = false;
      emit('success');
    } catch {
      // 请求层已提示错误，弹窗保持打开
    } finally {
      isSubmitting.value = false;
    }
  };

  defineExpose({ open });
</script>

<style lang="postcss" scoped>
  .batch-confirm-wrap {
    font-size: 12px;
  }

  .batch-confirm-wrap :deep(.bk-form),
  .batch-confirm-wrap :deep(.bk-form-item),
  .batch-confirm-wrap :deep(.bk-form-content) {
    width: 100%;
    max-width: 100%;
  }

  .batch-confirm-wrap :deep(.bk-form-content) {
    line-height: 20px;
  }

  .batch-confirm-wrap :deep(.bk-form-item) {
    margin-bottom: 16px;
  }

  .batch-confirm-wrap :deep(.bk-form-item:last-child) {
    margin-bottom: 0;
  }

  .batch-confirm-wrap :deep(.bk-form-label) {
    padding-bottom: 0;
    margin-bottom: 6px;
    font-size: 12px;
    line-height: 20px;
    color: #313238;
  }

  .batch-confirm-radios {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 24px;
  }

  .misreport-alert {
    margin-bottom: 16px;
  }

  .batch-confirm-radios :deep(.bk-radio),
  .batch-confirm-radios :deep(.bk-radio .bk-radio-label) {
    font-size: 12px;
    font-weight: 400;
    line-height: 20px;
    color: #4d4f56;
  }

  :deep(.await-deal-rich-editor),
  :deep(.await-deal-rich-editor .editor-wrap),
  :deep(.await-deal-rich-editor .quill-editor) {
    width: 100%;
    max-width: 100%;
    box-sizing: border-box;
  }

  :deep(.await-deal-rich-editor .ql-container) {
    min-height: 180px;
  }

  .batch-confirm-failures {
    margin-top: 16px;
    font-size: 12px;
    line-height: 20px;
    color: #ea3636;
  }

  .batch-confirm-failures__title {
    margin-bottom: 4px;
  }
</style>
