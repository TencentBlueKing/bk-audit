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
    :confirm-handler="handleConfirm"
    :is-loading="isSubmitting"
    theme="primary"
    :title="t('批量确认风险单')"
    width="720"
    @closed="handleClosed">
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
          v-model:content="formData.description"
          :default="formData.description"
          :max-len="1000"
          :placeholder="t('@通知他人, ctrl+enter快速提交')" />
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
  import useRequest from '@hooks/use-request';

  import RichEditor from '@components/editor/index.vue';

  interface Emits {
    (e: 'success'): void;
  }

  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const { messageSuccess } = useMessage();

  const isShow = ref(false);
  const formRef = ref();
  const riskIds = ref<string[]>([]);
  const formData = ref({
    confirm_result: 'confirm',
    description: '',
  });

  const rules = {
    confirm_result: [
      {
        required: true,
        message: t('请选择确认结果'),
        trigger: 'change',
      },
    ],
  };

  const {
    run: submitBatchConfirm,
    loading: isSubmitting,
  } = useRequest(RiskManageService.batchConfirmRisk, {
    manual: true,
    onSuccess: () => {
      messageSuccess(t('操作成功'));
      isShow.value = false;
      emit('success');
    },
  });

  const {
    run: updateRiskLabel,
  } = useRequest(RiskManageService.updateRiskLabel, {
    manual: true,
  });

  const show = (ids: string[]) => {
    riskIds.value = ids;
    formData.value = {
      confirm_result: 'confirm',
      description: '',
    };
    isShow.value = true;
  };

  const handleClosed = () => {
    formData.value = {
      confirm_result: 'confirm',
      description: '',
    };
    riskIds.value = [];
  };

  const handleConfirm = async () => {
    await formRef.value?.validate?.();
    if (formData.value.confirm_result === 'misreport') {
      await Promise.all(riskIds.value.map(riskId => updateRiskLabel({
        risk_id: riskId,
        risk_label: 'misreport',
        description: formData.value.description,
        new_operators: [],
      })));
      messageSuccess(t('操作成功'));
      isShow.value = false;
      emit('success');
      return;
    }
    await submitBatchConfirm({
      risk_ids: riskIds.value,
      description: formData.value.description,
    });
  };

  defineExpose({
    show,
  });
</script>
