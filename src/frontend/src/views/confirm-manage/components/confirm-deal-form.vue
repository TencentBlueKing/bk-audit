<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<template>
  <div
    class="confirm-deal-form-wrap"
    :class="{ 'is-editor-boosted': isDockEditorBoosted }">
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
          class="confirm-deal-form__radios">
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
          ref="richEditor"
          v-model:content="formData.description"
          class="confirm-deal-rich-editor"
          :default="formData.description"
          fullscreen-scope="parent"
          :max-len="1000"
          @expand-change="handleEditorExpandChange" />
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
            ref="misreportRichEditor"
            v-model:content="formData.description"
            class="await-deal-rich-editor"
            :default="formData.description"
            fullscreen-scope="parent"
            :max-len="1000"
            @expand-change="handleEditorExpandChange" />
        </bk-form-item>
      </template>
      <bk-form-item
        class="submit-actions-form-item"
        label="">
        <auth-button
          action-id="process_risk"
          :loading="isSubmitting"
          :permission="detailData.permission.process_risk || detailData.current_operator.includes(userInfo.username)"
          :resource="detailData.risk_id"
          style="min-width: 72px;"
          theme="primary"
          @click="handleSubmit">
          {{ t('提交') }}
        </auth-button>
        <bk-button
          style="min-width: 72px;margin-left: 8px;"
          @click="handleCancel">
          {{ t('取消') }}
        </bk-button>
      </bk-form-item>
    </audit-form>
  </div>
</template>

<script setup lang="ts">
  import DOMPurify from 'dompurify';
  import {
    computed,
    inject,
    ref,
    type Ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskManageService from '@service/risk-manage';

  import type RiskManageModel from '@model/risk/risk';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import RichEditor from '@components/editor/index.vue';

  interface Props {
    riskId: string | number,
    detailData: RiskManageModel,
    userInfo: {
      username: string,
    },
  }

  interface Emits {
    (e: 'update'): void,
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const dockEditorExpand = inject<(expanded: boolean) => void>('dockEditorExpand', () => {});
  const dockBoostState = inject<{
    isEditorBoosted: Ref<boolean>;
    panelHeight: Ref<number>;
  } | null>('dockBoostState', null);
  const dockCollapse = inject<(() => void) | null>('dockCollapse', null);
  const isDockEditorBoosted = computed(() => dockBoostState?.isEditorBoosted.value ?? false);
  const { t } = useI18n();
  const { messageSuccess } = useMessage();

  const formRef = ref();
  const formData = ref({
    confirm_result: 'confirm',
    description: '',
  });

  const isRichTextNotEmpty = (html: string) => {
    if (!html) return false;
    const text = DOMPurify.sanitize(html, { ALLOWED_TAGS: [] }).trim();
    return text.length > 0;
  };

  const rules = {
    confirm_result: [{
      validator: (value: string) => !!value,
      trigger: 'change',
      message: t('请选择确认结果'),
    }],
    description: [{
      validator: (value: string) => {
        if (formData.value.confirm_result !== 'misreport') {
          return true;
        }
        return isRichTextNotEmpty(value);
      },
      trigger: 'change',
      message: t('说明不能为空'),
    }],
  };

  const {
    run: submitConfirmRisk,
    loading: confirmLoading,
  } = useRequest(RiskManageService.confirmRisk, {
    defaultValue: null,
    onSuccess: () => {
      messageSuccess(t('操作成功'));
      emits('update');
    },
  });

  const {
    run: submitConfirmAsMisreport,
    loading: misreportLoading,
  } = useRequest(RiskManageService.confirmAsMisreport, {
    defaultValue: null,
    onSuccess: () => {
      messageSuccess(t('操作成功'));
      emits('update');
    },
  });

  const isSubmitting = computed(() => confirmLoading.value || misreportLoading.value);

  const handleEditorExpandChange = (expanded: boolean) => {
    dockEditorExpand(expanded);
  };

  const resetForm = () => {
    formData.value = {
      confirm_result: 'confirm',
      description: '',
    };
  };

  const handleSubmit = async () => {
    await formRef.value?.validate?.();
    if (formData.value.confirm_result === 'misreport') {
      await submitConfirmAsMisreport({
        risk_id: props.riskId,
        description: formData.value.description,
      });
      return;
    }
    await submitConfirmRisk({
      risk_id: props.riskId,
      description: formData.value.description,
    });
  };

  const handleCancel = () => {
    handleEditorExpandChange(false);
    resetForm();
    dockCollapse?.();
  };
</script>

<style scoped lang="postcss">
.confirm-deal-form-wrap {
  width: 100%;
  padding: 16px;
  font-size: 12px;
  background: #f5f7fa;
  border: 1px solid #eaebf0;
  border-radius: 4px;
  box-sizing: border-box;
}

.confirm-deal-form-wrap :deep(.bk-form),
.confirm-deal-form-wrap :deep(.bk-form-item),
.confirm-deal-form-wrap :deep(.bk-form-content) {
  width: 100%;
  max-width: 100%;
}

.confirm-deal-form-wrap :deep(.bk-form-item) {
  margin-bottom: 16px;
}

.confirm-deal-form-wrap :deep(.bk-form-item:last-child) {
  margin-bottom: 0;
}

.confirm-deal-form-wrap :deep(.bk-form-label) {
  font-size: 12px;
  line-height: 20px;
  color: #313238;
}

.confirm-deal-form__radios {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
}

.confirm-deal-form__radios :deep(.bk-radio) {
  font-size: 12px;
  font-weight: 400;
  line-height: 20px;
  color: #4d4f56;
}

:deep(.confirm-deal-rich-editor),
:deep(.confirm-deal-rich-editor .editor-wrap),
:deep(.confirm-deal-rich-editor .quill-editor) {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}

.submit-actions-form-item {
  margin-top: 8px !important;
  margin-bottom: 0 !important;
}

.misreport-alert {
  margin-bottom: 16px;
}

:deep(.await-deal-rich-editor),
:deep(.await-deal-rich-editor .editor-wrap),
:deep(.await-deal-rich-editor .quill-editor) {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}
</style>
