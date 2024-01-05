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
  <div class="approve-wrap">
    <template v-if="forApproveData">
      <div class="mis-title">
        <span style="color: #313238">{{ t('执行前审批') }}</span>
        <span
          class="ml8"
          style="color: #979ba5">
          {{ forApproveData.process_result?.status?.update_at || forApproveData.time }}
        </span>
      </div>
      <div class="mis-content">
        <render-info-item
          :label="t('审批结果')"
          :label-width="labelWidth">
          <div style="display: flex;align-items: center;">
            <audit-icon
              :class="forApproveStatusCom.icon==='loading' ? 'rotate-loading' : '' "
              :style="`margin-right: 4px;color: ${forApproveStatusCom.color};`"
              :svg="forApproveStatusCom.svg"
              :type="forApproveStatusCom.icon" />
            <span>{{ forApproveStatusCom.label }}</span>
          </div>
        </render-info-item>
        <render-info-item
          class="mt8"
          :label="t('关联单据')"
          :label-width="labelWidth">
          <a
            v-if="forApproveData.process_result?.ticket?.ticket_url"
            :href="forApproveData.process_result.ticket.ticket_url"
            target="_blank">
            {{ forApproveData.process_result?.ticket?.sn || '--' }}
          </a>
          <span v-else>--</span>
        </render-info-item>
      </div>
    </template>

    <!-- 执行套餐 - AutoProcess -->
    <template v-if="data.action === 'AutoProcess'">
      <div class="mis-title mt16">
        <span style="color: #313238">{{ t('执行套餐动作') }}</span>
        <span
          class="ml8"
          style="color: #979ba5">{{ data.process_result?.status?.update_at || data.time }}</span>
      </div>
      <div class="mis-content">
        <render-info-item
          :label="t('任务名称')"
          :label-width="labelWidth">
          <!-- 任务名称，没有默认展示 loading -->
          <a
            v-if="data.process_result?.status?.name"
            :href="data.process_result?.task?.task_url"
            target="_blank">
            {{ data.process_result?.status.name }}
          </a>
          <audit-icon
            v-else
            class="rotate-loading"
            style="margin-right: 4px;"
            svg
            type="loading" />
        </render-info-item>
        <render-info-item
          class="mt8"
          :label="t('任务状态')"
          :label-width="labelWidth">
          <!-- 没有则展示执行中 -->
          <div style="display: flex;align-items: center;">
            <audit-icon
              v-if="autoProcessStatusCom.showIcon"
              :class="autoProcessStatusCom.icon==='loading'? 'rotate-loading':''"
              :style="`margin-right: 4px; color: ${autoProcessStatusCom.color}`"
              :svg="autoProcessStatusCom.svg"
              :type="autoProcessStatusCom.icon" />
            <span>{{ autoProcessStatusCom.label }}</span>
            <bk-button
              v-if="data.process_result?.status?.state==='RUNNING'"
              class="ml16"
              :loading="forceLoading"
              text
              theme="primary"
              @click="handleRevoke">
              <audit-icon
                style="margin-right: 4px;"
                type="stop-2" />
              {{ t('强制终止') }}
            </bk-button>
            <bk-button
              v-else-if="data.process_result?.status?.state==='FAILED'"
              class="ml16"
              :loading="retryLoading"
              text
              theme="primary"
              @click="handleRetry">
              <audit-icon
                style="margin-right: 4px;"
                type="redo" />
              {{ t('重试') }}
            </bk-button>
          </div>
        </render-info-item>
        <render-info-item
          class="mt8"
          :label="t('执行开始时间')"
          :label-width="labelWidth">
          <span v-if="data.process_result?.status?.start_time">
            {{ data.process_result.status.start_time || '--' }}
          </span>
          <span v-else>--</span>
        </render-info-item>
        <render-info-item
          class="mt8"
          :label="t('执行结束时间')"
          :label-width="labelWidth">
          <span v-if="data.process_result?.status?.finish_time">
            {{ data.process_result?.status.finish_time || '--' }}
          </span>
          <span v-else>--</span>
        </render-info-item>
      </div>
    </template>
  </div>
</template>

<script setup lang='ts'>
  import {
    computed,
  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';

  import RiskManageService from '@service/risk-manage';

  import type RiskManageModel from '@model/risk/risk';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import RenderInfoItem from '@views/risk-manage/detail/components/render-info-item.vue';

  interface Emits{
    (e: 'update'): void,
  }
  interface DataType{
    id: string,
    name: string
  }
  interface Props {
    data: RiskManageModel['ticket_history'][0],
    riskId: string,
    statusData: DataType[],
    itsmStatusData:DataType[],
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t, locale } = useI18n();
  const { messageSuccess } = useMessage();
  const labelWidth = computed(() => (locale.value === 'en-US' ? 100 : 80));

  // 执行前审批的状态
  const currentStatus = computed(() => {
    if (!props.data.process_result?.status) return '';
    const statu = props.data.process_result?.status.current_status;
    return props.itsmStatusData.find(item => item.id === statu)?.name;
  });
  const forApproveStatusCom = computed(() => {
    const data = forApproveData.value;
    // 如果为空显示正在审批中
    if (!data.process_result?.status) {
      return {
        label: t('正在审批中'),
        icon: 'loading',
        color: '#3A84FF',
        svg: true,
      };
    }
    const status = data.process_result?.status.current_status;
    if (status === 'REVOKED') {
      return {
        label: currentStatus.value,
        icon: 'stop',
        color: '#EB3333',
      };
    }
    if (['FINISHED', 'TERMINATED', 'FAILED'].includes(status)) {
      if (data.process_result.status.approve_result) {
        return {
          label: t('通过'),
          icon: 'completed',
          color: '#15AD89',
          svg: true,
        };
      }
      return {
        label: t('不通过'),
        icon: 'delete-fill',
        color: '#EB3333',
      };
    }
    return {
      label: currentStatus.value,
      icon: 'loading',
      color: '#3A84FF;',
      svg: true,
    };
  });
  const forApproveData = computed(() => {
    if (props.data.action === 'AutoProcess') {
      return props.data.forApproveItem ;
    }
    return props.data ;
  });
  // 执行套餐的状态
  const autoProcessStatus = computed(() => {
    if (!props.data.process_result.status) return '';
    const statu = props.data.process_result.status.state;
    return props.statusData.find(item => item.id === statu)?.name || '';
  });
  const autoProcessStatusCom = computed(() => {
    const params = {
      label: t('执行中'),
      icon: 'loading',
      color: '#3A84FF',
      svg: true,
      showIcon: true,
    };
    // 如果为空显示正在审批中
    if (props.data.process_result.status) {
      const { state } = props.data.process_result.status;
      params.label = autoProcessStatus.value || t('执行中');
      // 未执行不显示loading icon
      if (state === 'CREATED') {
        params.showIcon = false;
      }
      if (state === 'FINISHED') {
        params.icon = 'completed';
        params.color = '#15AD89';
        return params;
      }
      if (state === 'REVOKED') {
        params.icon = 'stop';
        params.color = '#EB3333';
        return params;
      }
      if (state === 'FAILED') {
        params.icon = 'delete-fill';
        params.color = '#EB3333';
        return params;
      }
    }
    return params;
  });


  // 强制处理
  const {
    run: forceRevokeAutoProcess,
    loading: forceLoading,
  } = useRequest(RiskManageService.forceRevokeAutoProcess, {
    defaultValue: null,
    onSuccess() {
      messageSuccess('强制终止执行中');
      emits('update');
    },
  });
  // 重试处理套餐
  const {
    run: retryAutoProcess,
    loading: retryLoading,
  } = useRequest(RiskManageService.retryAutoProcess, {
    defaultValue: null,
    onSuccess() {
      messageSuccess('重试成功');
      emits('update');
    },
  });


  // 强制终止
  const handleRevoke = () => {
    forceRevokeAutoProcess({
      risk_id: props.riskId,
      node_id: props.data.id,
    });
  };
  // 重试
  const handleRetry = () => {
    retryAutoProcess({
      risk_id: props.riskId,
      node_id: props.data.id,
    });
  };
</script>
<style scoped lang="postcss">
.approve-wrap {
  padding: 10px 16px;
  background: #fff;
  border: 1px solid #eaebf0;
  border-radius: 6px;
  box-shadow: 0 2px 6px 0 #0000000a;

  .mis-title {
    font-size: 12px;
  }

  >.mis-content {
    padding: 12px 16px;
    margin-top: 8px;
    background: #f5f7fa;
    border-radius: 4px;
  }
}
</style>
