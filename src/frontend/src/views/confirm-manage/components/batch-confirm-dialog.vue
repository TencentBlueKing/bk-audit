<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed on
  an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
  either express or implied. See the License for the
  specific language governing permissions and limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
-->
<template>
  <bk-dialog
    v-model:is-show="isShow"
    :esc-close="false"
    :is-loading="isSubmitting"
    :quick-close="false"
    theme="primary"
    :title="t('批量确认风险单')"
    width="720"
    @closed="handleClosed"
    @confirm="handleConfirm">
    <audit-form
      ref="formRef"
      form-type="vertical"
      :model="formData"
      :rules="rules">
      <bk-form-item
        :label="t('确认结果')"
        property="confirm_result"
        required>
        <bk-radio-group v-model="formData.confirm_result">
          <bk-radio label="confirm">
            {{ t('风险确认') }}
          </bk-radio>
          <bk-radio label="misreport">
            {{ t('标记误报') }}
          </bk-radio>
        </bk-radio-group>
      </bk-form-item>
      <bk-form-item
        :label="t('确认说明')"
        property="description">
        <rich-editor
          :key="editorKey"
          v-model:content="formData.description"
          :default="formData.description"
          :max-len="1000" />
      </bk-form-item>
    </audit-form>
  </bk-dialog>
</template>

<script setup lang="ts">
  import {
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskManageService from '@service/risk-manage';

  import useMessage from '@hooks/use-message';

  import RichEditor from '@components/editor/index.vue';

  interface Emits {
    (e: 'success'): void;
  }

  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const { messageSuccess } = useMessage();

  const isShow = ref(false);
  const formRef = ref();
  const editorKey = ref(0);
  const riskIds = ref<string[]>([]);
  const formData = ref({
    confirm_result: 'confirm',
    description: '',
  });

  const resetForm = () => {
    formData.value = {
      confirm_result: 'confirm',
      description: '',
    };
    editorKey.value += 1;
    formRef.value?.clearValidate?.();
  };

  const rules = {
    confirm_result: [
      {
        required: true,
        message: t('请选择确认结果'),
        trigger: 'change',
      },
    ],
  };

  const isSubmitting = ref(false);

  const show = (ids: string[]) => {
    riskIds.value = ids;
    resetForm();
    isShow.value = true;
  };

  const handleClosed = () => {
    resetForm();
    riskIds.value = [];
  };

  const handleConfirm = () => {
    formRef.value?.validate?.().then(async () => {
      if (!riskIds.value.length) {
        return;
      }
      isSubmitting.value = true;
      try {
        if (formData.value.confirm_result === 'misreport') {
          await Promise.all(riskIds.value.map(riskId => RiskManageService.confirmAsMisreport({
            risk_id: riskId,
            description: formData.value.description,
          })));
        } else {
          await RiskManageService.batchConfirmRisk({
            risk_ids: riskIds.value,
            description: formData.value.description,
          });
        }
        messageSuccess(t('操作成功'));
        isShow.value = false;
        emit('success');
      } finally {
        isSubmitting.value = false;
      }
    });
  };

  defineExpose({
    show,
  });
</script>
