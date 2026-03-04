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
    :confirm-handler="handleConfirm"
    :confirm-text="isMisreport ? t('解除') : t('标记')"
    :content="isMisreport
      ? resetMisreportTipMap[data.status as keyof typeof resetMisreportTipMap]
      : markMisreportTipMap[data.status as keyof typeof markMisreportTipMap]"
    :hide-on-click="false"
    :title="isMisreport ? t('确认解除误报？'):t('确认标记误报？')"
    :z-index="3999"
    @hide="handlePopHide">
    <template #content>
      <audit-form
        ref="formRef"
        form-type="vertical"
        :label-width="80"
        :model="formData"
        :rules="rules">
        <template
          v-if="!isMisreport">
          <bk-form-item
            class="is-required mr16"
            :label="t('误报说明')"
            property="description"
            style="margin-bottom: 6px;">
            <bk-input
              v-model.trim="formData.description"
              :maxlength="100"
              :placeholder="t('请输入')"
              show-word-limit
              style="resize: none;"
              type="textarea" />
          </bk-form-item>
          <p
            v-if="data.status === 'auto_process'"
            style="display: flex; margin-top: 24px;color: #63656e; align-items: center;">
            <bk-checkbox v-model="isForce" />
            <span style="margin-left: 4px;">{{ t('强制终止套餐') }}</span>
          </p>
        </template>

        <template v-else>
          <bk-form-item
            v-if="isShowOperators"
            class="is-required mr16"
            :label="t('处理人')"
            property="new_operators">
            <audit-user-selector
              v-model="formData.new_operators"
              multiple />
          </bk-form-item>
        </template>
      </audit-form>
    </template>
    <div>
      <bk-button
        v-if="data.permission.process_risk || data.current_operator.includes(userInfo.username)"
        style="font-size: 12px;"
        text
        theme="primary">
        <audit-icon
          style="margin-right: 6px;"
          :type="isMisreport ? 'jiechuwubao' : 'biaojiwubao'" />
        {{ isMisreport ? t('解除误报') : t('标记误报') }}
      </bk-button>
      <auth-button
        v-else
        action-id="process_risk"
        :permission="data.permission.process_risk || data.current_operator.includes(userInfo.username)"
        :resource="data.risk_id"
        style="font-size: 12px;"
        text
        theme="primary">
        <audit-icon
          style="margin-right: 6px;"
          :type="isMisreport ? 'jiechuwubao' : 'biaojiwubao'" />
        {{ isMisreport ? t('解除误报') : t('标记误报') }}
      </auth-button>
    </div>
  </audit-popconfirm>
</template>

<script setup lang='ts'>
  import {
    computed,
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
    (e:'update'): void,
  }
  interface Props{
    data: RiskManageModel,
    userInfo: {
      username: string,
    },
    lastTicketHistory?: Record<string, any>
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const isForce = ref(true);
  const rules = {
    new_operators: [{
      validator: (value: string) => !!value && value.length > 0,
      trigger: 'change',
      message: t('处理人不能为空'),
    }],
    description: [{
      validator: (value: string) => !!value,
      trigger: 'blur',
      message: t('说明不能为空'),
    }],
  };


  const popRef = ref();
  const formRef = ref();
  const formData = ref<Record<string, any>>({});

  const isMisreport = computed(() => props.data.risk_label === 'misreport');
  const isShowOperators = computed(() => !(props.lastTicketHistory && props.lastTicketHistory.action === 'AutoProcess'));
  // 标记误报的tip
  const markMisreportTipMap = {
    closed: t('策略方案可能采集误报数据作为优化依据，请谨慎确认是否为误报？'),
    for_approve: t('标记误报后，风险单会自动关闭，请谨慎确认是否为误报？'),
    await_deal: t('标记误报后，风险单会自动关闭，请谨慎确认是否为误报？'),
    new: t('标记误报后，风险单会自动关闭，请谨慎确认是否为误报？'),
    auto_process: t('标记误报后，风险单会在套餐处理结束（终止）后自动关闭，请谨慎确认是否为误报？'),
  };
  // 解除误报的tip
  const resetMisreportTipMap = {
    closed: t('解除误报后，风险单会重新打开至“待处理” 请谨慎确认是否解除误报？'),
    for_approve: t('解除误报后，风险单会按原流程继续执行，请谨慎确认是否解除误报？'),
    await_deal: t('解除误报后，风险单会按原流程继续执行，请谨慎确认是否解除误报？'),
    new: t('解除误报后，风险单会按原流程继续执行，请谨慎确认是否解除误报？'),
    auto_process: t('解除误报后，风险单会按原流程继续执行，请谨慎确认是否解除误报？'),
  };

  // 更新状态
  const {
    run: updateRiskLabel,
  } = useRequest(RiskManageService.updateRiskLabel, {
    defaultValue: null,
    onSuccess() {
      emits('update');
      messageSuccess(isMisreport.value ? t('解除误报成功') : t('标记误报成功'));
      popRef.value.hide();
    },
  });

  const handlePopHide = () => {
    popRef.value.hide();
    if (isMisreport.value) {
      formData.value.new_operators = [props.userInfo.username];
    } else {
      formData.value = {};
    }
  };
  const handleConfirm = () => formRef.value.validate().then(() => {
    const params: Record<string, any> = {
      risk_id: props.data.risk_id,
      risk_label: isMisreport.value ? 'normal' : 'misreport',
    };
    // 如果标记误报 并且是auto_process  传递强制终止参数
    if (!isMisreport.value && props.data.status === 'auto_process' && props.lastTicketHistory) {
      params.revoke_process =  isForce.value ;
    }
    if (!isMisreport.value) {
      params.description = formData.value.description;
    } else if (isShowOperators.value) {
      params.new_operators = formData.value.new_operators;
    }
    return updateRiskLabel(params);
  });
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
