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
  <div class="strategy-records">
    <bk-alert theme="info">
      <template #title>
        <div>
          {{ t('1. 产生风险单') }}
          <span style="color: #3a84ff;">{{ riskCount }}</span>
          {{ t('个') }}
        </div>
        <div>
          {{ t('2. 本策略为“实时调度”，源数据每新增 1 条都会执行 1 次，所以运行记录简化为按每 1 分钟进行 1 次统计') }}
        </div>
      </template>
    </bk-alert>

    <bk-table
      ref="tableRef"
      :border="['outer']"
      :columns="columns"
      :data="runningData"
      :max-height="650"
      style="margin-top: 12px;" />
  </div>
</template>
<script setup lang="tsx">
  import { computed, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import type StrategyModel from '@model/strategy/strategy';

  import useRequest from '@/hooks/use-request';

  interface Props {
    data: StrategyModel,
  }

  const props = defineProps<Props>();

  const { t } = useI18n();

  const riskCount = computed(() => props.data.risk_count);

  const columns = [
    {
      label: () => t('序号'),
      width: 60,
      type: 'index',
    },
    {
      label: () => t('发起时间'),
      field: () => 'schedule_time',
    },
    {
      label: () => t('执行结果'),
      field: () => 'status_str',
      render: ({ data }: { data: Record<string, any> }) => <p style='display: flex; align-items: center;max-width: 200px;'>
        <audit-icon
          svg
          class='mr4'
          type={statusMap[data.status as keyof typeof statusMap]} />
        {data.status_str}
      </p>,
    },
    {
      label: () => t('产生风险单'),
      field: () => 'risk_count',
    },
  ];

  const statusMap = {
    finished: 'normal',

    running: 'warning',
    none: 'warning',
    preparing: 'warning',
    recovering: 'warning',
    retried: 'warning',
    killed: 'warning',
    disabled: 'warning',
    skipped: 'warning',
    decommissioned: 'warning',
    failed_succeeded: 'warning',
    lost: 'warning',

    failed: 'abnormal',
  };

  // 获取运行记录
  const {
    data: runningData,
    run: fetchRisksRunning,
  } = useRequest(StrategyManageService.fetchRisksRunning, {
    defaultValue: [],
    onSuccess: (data) => {
      console.log(data);
    },
  });

  watch(() => props.data, (data) => {
    fetchRisksRunning({
      strategy_id: data.strategy_id,
    });
  }, {
    immediate: true,
  });
</script>
<style scoped lang="postcss">
.strategy-records {
  padding: 20px 40px;

  :deep(.bk-alert-wraper) {
    .bk-alert-icon-info {
      height: 22px;
      line-height: 22px;
    }

    .bk-alert-title {
      font-size: 14px;
      line-height: 22px;
    }
  }
}
</style>
