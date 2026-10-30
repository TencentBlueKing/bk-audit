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
          :max-len="2000"
          @expand-change="handleEditorExpandChange" />
      </bk-form-item>
      <template v-else>
        <bk-alert
          class="misreport-alert"
          theme="warning"
          :title="misreportAlertTitle" />
        <bk-form-item
          class="is-required"
          :label="t('误报说明')"
          property="misreport_description"
          required>
          <rich-editor
            ref="misreportRichEditor"
            v-model:content="formData.misreport_description"
            class="await-deal-rich-editor"
            :default="formData.misreport_description"
            fullscreen-scope="parent"
            :max-len="2000"
            @expand-change="handleEditorExpandChange" />
        </bk-form-item>
        <bk-checkbox
          v-model="withWhitelist"
          class="whitelist-together">
          {{ t(roleText.text.value.together) }}
        </bk-checkbox>
        <risk-whitelist-form
          v-if="withWhitelist"
          ref="whitelistFormRef"
          embedded
          :initial-scope="initialScope"
          show-apply-hint />
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
    <whitelist-confirm-dialog ref="confirmRef" />
  </div>
</template>

<script setup lang="ts">
  import DOMPurify from 'dompurify';
  import {
    computed,
    inject,
    onBeforeUnmount,
    ref,
    type Ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { onBeforeRouteLeave, useRoute } from 'vue-router';

  import RiskManageService from '@service/risk-manage';
  import RiskWhitelistService from '@service/risk-whitelist';

  import type RiskManageModel from '@model/risk/risk';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';
  import useWhitelistRoleText from '@hooks/use-whitelist-role-text';

  import RichEditor from '@components/editor/index.vue';
  import RiskWhitelistForm from '@components/risk-whitelist-form/index.vue';
  import WhitelistConfirmDialog from '@components/whitelist-confirm-dialog/index.vue';

  import { buildScopeFromRisk } from '@views/risk-manage/whitelist';

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
  const route = useRoute();
  const { messageSuccess, messageError } = useMessage();
  const roleText = useWhitelistRoleText();

  const formRef = ref();
  const whitelistFormRef = ref<InstanceType<typeof RiskWhitelistForm>>();
  const confirmRef = ref<InstanceType<typeof WhitelistConfirmDialog>>();
  const withWhitelist = ref(false);
  const initialScope = computed(() => buildScopeFromRisk({
    strategy_id: props.detailData.strategy_id,
    strategy_name: (props.detailData as RiskManageModel & { strategy_name?: string }).strategy_name,
    raw_event_id: props.detailData.raw_event_id,
  }));
  const formData = ref({
    confirm_result: route.query.handleMethod === 'misreport' ? 'misreport' : 'confirm',
    description: '',
    misreport_description: '',
  });
  const misreportAlertTitle = computed(() => (
    `${t('标记误报后，风险单将自动关闭。若需避免后续同类风险再次命中，')}${t(roleText.text.value.misreportAlertTail)}`
  ));

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
      validator: () => true,
      trigger: 'change',
      message: '',
    }],
    misreport_description: [{
      validator: (value: string) => isRichTextNotEmpty(value),
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
      window.changeConfirm = false;
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
      window.changeConfirm = false;
      messageSuccess(t('操作成功'));
      emits('update');
    },
  });

  const {
    run: applyWhitelist,
    loading: applyLoading,
  } = useRequest(RiskWhitelistService.applyFromRisk, {
    defaultValue: null,
    onSuccess: () => {
      window.changeConfirm = false;
      messageSuccess(t(roleText.text.value.misreportSuccess));
      emits('update');
    },
  });

  const isSubmitting = computed(() => confirmLoading.value || misreportLoading.value || applyLoading.value);

  const hasSubstantialInput = () => {
    if (formData.value.confirm_result === 'misreport') {
      return isRichTextNotEmpty(formData.value.misreport_description || '')
        || (withWhitelist.value && (whitelistFormRef.value?.isDirty() ?? false));
    }
    return isRichTextNotEmpty(formData.value.description);
  };

  const clearLeaveConfirmIfEmpty = () => {
    if (!hasSubstantialInput()) {
      window.changeConfirm = false;
    }
  };

  const handleEditorExpandChange = (expanded: boolean) => {
    dockEditorExpand(expanded);
  };

  const resetForm = () => {
    formData.value = {
      confirm_result: 'confirm',
      description: '',
      misreport_description: '',
    };
    withWhitelist.value = false;
  };

  const handleSubmit = async () => {
    await formRef.value?.validate?.();
    if (formData.value.confirm_result === 'misreport') {
      if (withWhitelist.value) {
        if (!whitelistFormRef.value?.validate()) {
          messageError(t('请完整填写加白信息'));
          return;
        }
        const payload = whitelistFormRef.value.getPayload();
        const confirmed = await confirmRef.value?.open({
          scope: payload.match_scope,
          whitelistType: payload.whitelist_type,
          validityMode: payload.validity_mode,
          customDays: payload.custom_days,
          source: 'risk',
        });
        if (!confirmed) return;
        await applyWhitelist({
          risk_id: props.riskId,
          ...payload,
          with_misreport: true,
          misreport_description: formData.value.misreport_description || '',
          source: 'confirm',
        });
        return;
      }
      await submitConfirmAsMisreport({
        risk_id: props.riskId,
        description: formData.value.misreport_description || '',
      });
      return;
    }
    await submitConfirmRisk({
      risk_id: props.riskId,
      description: formData.value.description,
    });
  };

  const handleCancel = () => {
    clearLeaveConfirmIfEmpty();
    handleEditorExpandChange(false);
    resetForm();
    dockCollapse?.();
  };

  onBeforeRouteLeave(() => {
    clearLeaveConfirmIfEmpty();
  });

  onBeforeUnmount(() => {
    window.changeConfirm = false;
  });
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

.whitelist-together {
  margin-bottom: 16px;
  font-size: 12px;
}

.whitelist-apply-hint,
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
