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
  <audit-popconfirm
    ref="popRef"
    :confirm-auto-hide="false"
    :confirm-handler="handleReOpen"
    :confirm-text="t('重开')"
    :content="t('重打开单据后，风险单会重新打开至“待处理”')"
    :hide-on-click="false"
    :title="t('确认重开单据？')"
    :z-index="3999"
    @hide="handlePopHide">
    <template #content>
      <audit-form
        ref="formRef"
        form-type="vertical"
        :label-width="80"
        :model="formData"
        :rules="rules">
        <bk-form-item
          class="is-required mr16"
          :label="t('处理人')"
          property="new_operators">
          <audit-user-selector-tenant
            v-model="formData.new_operators"
            multiple />
        </bk-form-item>
      </audit-form>
    </template>
    <auth-button
      action-id="process_risk"
      :permission="data.permission.process_risk || data.current_operator.includes(userInfo.username)"
      :resource="data.risk_id"
      style="font-size: 12px;"
      text
      theme="primary">
      <audit-icon
        style="margin-right: 6px;"
        type="reopen" />
      {{ t('重开单据') }}
    </auth-button>
  </audit-popconfirm>
</template>

<script setup lang='ts'>
  import {
    ref,
    watch,
  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';

  import RiskManageService from '@service/risk-manage';

  import type RiskManageModel from '@model/risk/risk';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  interface Emits{
    (e:'update'): void
  }
  interface Props{
    data: RiskManageModel,
    userInfo: {
      username: string,
    }
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const { messageSuccess } = useMessage();


  const formRef = ref();
  const popRef = ref();
  const formData = ref({
    new_operators: [] as string[],
  });
  const rules = {
    new_operators: [{
      validator: (value: string) => !!value && value.length > 0,
      trigger: 'change',
      message: t('处理人不能为空'),
    }],
  };

  const {
    run: reopen,
  } = useRequest(RiskManageService.reopen, {
    defaultValue: null,
    onSuccess() {
      messageSuccess(t('重开单据成功'));
      emits('update');
      popRef.value.hide();
    },
  });

  const handlePopHide = () => {
    formData.value.new_operators = [props.userInfo.username];
  };
  const handleReOpen = () => formRef.value.validate().then(() => reopen({
    risk_id: props.data.risk_id,
    new_operators: formData.value.new_operators,
  }));

  watch(() => props.userInfo, (data) => {
    if (data) {
      formData.value.new_operators = [data.username];
    }
  }, {
    immediate: true,
  });
</script>
<!-- <style scoped>

</style> -->
