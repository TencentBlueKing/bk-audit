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
  <bk-sideslider
    v-model:isShow="isShow"
    background-color="#f5f7fa"
    :before-close="handleCancel"
    :esc-close="false"
    :quick-close="false"
    render-directive="if"
    :title="t( isEdit ? '新建风险' : '风险单预览')"
    :width="800">
    <edit
      v-if="isEdit"
      ref="editRef"
      @validate-success="handlePreviewSuccess" />
    <preview
      v-else
      ref="previewRef"
      :edit-data="editData" />
    <template #footer>
      <div class="foot-button">
        <bk-button
          v-if="isEdit"
          theme="primary"
          @click="handlePreview">
          {{ t('预览') }}
        </bk-button>
        <bk-button
          v-if="!isEdit"
          theme="primary"
          @click="handleSubmit">
          {{ t('提交') }}
        </bk-button>
        <bk-button
          v-if="!isEdit"
          @click="handleReturn">
          {{ t('返回修改') }}
        </bk-button>
        <bk-button @click="handleCancel">
          {{ t('取消') }}
        </bk-button>
      </div>
    </template>
  </bk-sideslider>
</template>

<script setup lang="ts">
  import { InfoBox } from 'bkui-vue';
  import { nextTick, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskManageService from '@service/risk-manage';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import edit from './edit.vue';
  import preview from './preview.vue';

  import { convertToTimestamp } from '@/utils/assist/timestamp-conversion';

  interface Exposes{
    show(): void,
  }
  interface Emits {
    (e: 'addSuccess'): void
  }

  const emits = defineEmits<Emits>();
  const isShow = ref(false);
  const { t } = useI18n();
  const editRef = ref();
  const previewRef = ref();
  const isEdit = ref(true);
  const editData = ref();
  const { messageSuccess } = useMessage();

  const handlePreview = () => {
    editRef.value?.validate();
  };

  // 预览表单验证成功
  const handlePreviewSuccess = () => {
    editData.value = editRef.value?.getEditData();
    isEdit.value = false;
    nextTick(() => {
      previewRef.value?.initData(editData.value);
    });
  };

  const handleReturn = () => {
    isEdit.value = true;
    nextTick(() => {
      editRef.value?.handlerReturnData(editData.value);
    });
  };
  const handleCancel = () => new Promise<boolean>((resolve) => {
    if (!window.changeConfirm) {
      isEdit.value = true;
      isShow.value = false;
      resolve(true);
      return;
    }
    InfoBox({
      title: t('确认取消当前操作?'),
      content: t('已填写的内容将会丢失，请谨慎操作！'),
      cancelText: t('取消'),
      confirmText: t('确认'),
      onConfirm() {
        isEdit.value = true;
        isShow.value = false;
        resolve(true);
      },
      onCancel() {
        resolve(false);
      },
    });
  });

  const {
    run: addEvent,
  } = useRequest(RiskManageService.addEvent, {
    defaultValue: [],
    onSuccess: (data) => {
      if (sessionStorage.getItem('addEventRiskIds')) {
        const existingRiskIds = sessionStorage.getItem('addEventRiskIds');
        const riskId = existingRiskIds ? JSON.parse(existingRiskIds).concat(data.risk_ids) : data.risk_ids;
        sessionStorage.setItem('addEventRiskIds', JSON.stringify(riskId));
      } else {
        sessionStorage.setItem('addEventRiskIds', JSON.stringify(data?.risk_ids));
      }
      messageSuccess(t('添加成功'));
      window.changeConfirm = false;
      isShow.value = false;
      isEdit.value = true;
      editData.value = null;
      emits('addSuccess');
    },
  });

  // 提交
  const handleSubmit = () => {
    const eventDataParams = editData.value.eventData.reduce((acc: any, item: any) => ({
      ...acc,
      [item.field_name]: item.value,
    }), {});
    const params = {
      events: [
        {
          strategy_id: editData.value.formData.strategy_id,
          event_data: eventDataParams,
          event_time: convertToTimestamp(editData.value.formData.event_time),
        },
      ],
      gen_risk: true,
    };
    addEvent(params);
  };
  defineExpose<Exposes>({
    show() {
      isShow.value = true;
      window.changeConfirm = false;
    },
  });
</script>

<style lang="postcss" scoped>
.foot-button {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
}
</style>
