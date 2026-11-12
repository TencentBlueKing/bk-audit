<template>
  <bk-dialog
    v-model:is-show="isShow"
    :esc-close="false"
    :quick-close="false"
    :title="t('批量确认风险单')"
    width="720"
    @closed="handleClosed">
    <div
      class="batch-confirm-wrap bk-theme-form--compact"
      data-testid="batch-confirm-dialog">
      <bk-form
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
          property="description"
          required>
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
          <span
            v-bk-tooltips="{
              content: t('所选风险不属于同一审计策略，无法批量加白'),
              disabled: strategyUnique,
            }"
            class="whitelist-together-wrap"
            :class="{ 'is-disabled': !strategyUnique }">
            <bk-checkbox
              v-model="withWhitelist"
              class="whitelist-together"
              data-testid="batch-confirm-whitelist-together"
              :disabled="!strategyUnique">
              {{ t(roleText.text.value.together) }}
            </bk-checkbox>
          </span>
          <risk-whitelist-form
            v-if="withWhitelist && strategyUnique"
            ref="whitelistFormRef"
            data-testid="batch-confirm-whitelist-form"
            embedded
            :initial-scope="initialScope"
            show-apply-hint />
        </template>
      </bk-form>
      <whitelist-confirm-dialog ref="confirmRef" />
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
       
        :disabled="isSubmitting"
        @click="handleCancel" style="margin-left: var(--bk-theme-space-8)">
        {{ t('取消') }}
      </bk-button>
    </template>
  </bk-dialog>
</template>

<script setup lang="ts">
  import DOMPurify from 'dompurify';
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import useMessage from '@hooks/use-message';
  import useWhitelistRoleText from '@hooks/use-whitelist-role-text';

  import RichEditor from '@components/editor/index.vue';
  import RiskWhitelistForm from '@components/risk-whitelist-form/index.vue';
  import WhitelistConfirmDialog from '@components/whitelist-confirm-dialog/index.vue';

  import { buildScopeFromRisk } from '@views/risk-manage/whitelist';

  import { submitBatchConfirm, submitBatchWhitelist } from '../adapter';

  interface FieldItem {
    id: string;
    name: string;
  }

  interface Props {
    riskIds: string[];
    riskFields?: FieldItem[];
    eventFields?: FieldItem[];
    strategyId?: string;
    strategyUnique?: boolean;
  }

  const props = withDefaults(defineProps<Props>(), {
    riskFields: () => [],
    eventFields: () => [],
    strategyId: '',
    strategyUnique: false,
  });

  const emit = defineEmits<{(e: 'success'): void }>();
  const { t } = useI18n();
  const { messageSuccess, messageError } = useMessage();
  const roleText = useWhitelistRoleText();
  const isShow = ref(false);
  const isSubmitting = ref(false);
  const editorKey = ref(0);
  const formRef = ref();
  const whitelistFormRef = ref<InstanceType<typeof RiskWhitelistForm>>();
  const confirmRef = ref<InstanceType<typeof WhitelistConfirmDialog>>();
  const withWhitelist = ref(false);
  const failures = ref<Array<{ risk_id: string; reason: string }>>([]);
  const hasProcessed = ref(false);
  const formData = ref({
    confirm_result: 'confirm',
    description: '',
  });

  const strategyUnique = computed(() => props.strategyUnique);
  const initialScope = computed(() => (
    props.strategyUnique ? buildScopeFromRisk({ strategy_id: props.strategyId }) : null
  ));

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
      validator: (value: string) => isRichTextNotEmpty(value),
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
    withWhitelist.value = false;
    failures.value = [];
    hasProcessed.value = false;
    editorKey.value += 1;
    formRef.value?.clearValidate?.();
  };

  const handleClosed = () => {
    const shouldRefresh = hasProcessed.value;
    resetForm();
    if (shouldRefresh) {
      emit('success');
    }
  };

  const handleCancel = () => {
    isShow.value = false;
    handleClosed();
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
    const useWhitelist = formData.value.confirm_result === 'misreport' && withWhitelist.value;
    if (useWhitelist) {
      if (!whitelistFormRef.value?.validate()) {
        messageError(t('请完整填写加白信息'));
        return;
      }
      const payload = whitelistFormRef.value.getPayload();
      const confirmed = await confirmRef.value?.open({
        scope: payload.match_scope,
        whitelistType: payload.whitelist_type,
        validityMode: payload.validity_mode || 'permanent',
        customDays: payload.custom_days,
        source: 'risk',
      });
      if (!confirmed) {
        return;
      }
      isSubmitting.value = true;
      failures.value = [];
      try {
        const receipt = await submitBatchWhitelist({
          riskIds: props.riskIds,
          payload,
          withMisreport: true,
          misreportDescription: formData.value.description,
        });
        if (receipt.failed.length) {
          failures.value = receipt.failed;
          hasProcessed.value = hasProcessed.value || receipt.success_count > 0;
          return;
        }
        messageSuccess(t(roleText.text.value.misreportSuccess));
        isShow.value = false;
        emit('success');
      } catch {
        // 请求层已提示错误，弹窗保持打开
      } finally {
        isSubmitting.value = false;
      }
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
        hasProcessed.value = hasProcessed.value || receipt.success_count > 0;
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
  }

  .batch-confirm-wrap :deep(.bk-form-item:last-child) {
  }

  .batch-confirm-wrap :deep(.bk-form-label) {
    padding-bottom: 0;
    margin-bottom: var(--bk-theme-space-6);
    font-size: 12px;
    line-height: 20px;
    color: var(--bk-theme-text-strong);
  }

  .batch-confirm-radios {
    display: flex;
    flex-wrap: wrap;
    gap: var(--bk-theme-space-8) var(--bk-theme-space-24);
  }

  .misreport-alert {
    margin-bottom: var(--bk-theme-space-16);
  }

  .whitelist-together {
    margin-bottom: var(--bk-theme-space-12);
  }

  .whitelist-together-wrap.is-disabled :deep(.bk-checkbox) {
    pointer-events: none;
  }

  .batch-confirm-radios :deep(.bk-radio),
  .batch-confirm-radios :deep(.bk-radio .bk-radio-label) {
    font-size: 12px;
    font-weight: 400;
    line-height: 20px;
    color: var(--bk-theme-text-default);
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
    margin-top: var(--bk-theme-space-16);
    font-size: 12px;
    line-height: 20px;
    color: var(--bk-theme-color-danger-2);
  }

  .batch-confirm-failures__title {
    margin-bottom: var(--bk-theme-space-4);
  }
</style>
