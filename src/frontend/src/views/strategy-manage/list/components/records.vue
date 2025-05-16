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
        <div v-if="isStreamSource">
          {{ t('2. 本策略为“实时调度”，源数据每新增 1 条都会执行 1 次，所以运行记录简化为按每 1 分钟进行 1 次统计') }}
        </div>
        <div v-else>
          {{ t('2. 仅支持展示最近24条记录') }}
        </div>
      </template>
    </bk-alert>

    <bk-table
      ref="tableRef"
      :border="['outer']"
      :columns="columns"
      :data="strategyRunningStatus"
      :max-height="700"
      style="margin-top: 12px;"
      @scroll-bottom="handleScrollBottom" />
  </div>
</template>
<script setup lang="tsx">
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import type StrategyModel from '@model/strategy/strategy';

  import useRequest from '@/hooks/use-request';

  interface Props {
    data: StrategyModel,
  }

  const props = defineProps<Props>();

  const { t } = useI18n();

  // 当前偏移量
  const currentOffset = ref(0);
  const pageSize = 20;

  const strategyRunningStatus = ref<typeof runningData.value.strategy_running_status>([]);

  const riskCount = computed(() => props.data.risk_count);

  // 是否为实时调度
  const isStreamSource = computed(() => props.data.configs?.data_source?.source_type === 'stream_source');

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
      render: ({ data }: { data: Record<string, any> }) => <p
        style='display: flex; align-items: center;max-width: 200px; cursor: pointer;'>
        <audit-icon
          svg
          class='mr4'
          type={statusMap[data.status as keyof typeof statusMap]} />
        <span v-bk-tooltips={{
          content: data.status === 'finished'
          ? t('基于数据源执行成功，包括数据源有审计中心无法感知的问题时，但策略也会执行成功')
           : data.err_msg,
        }}>
          {data.status_str}
        </span>
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
    loading,
  } = useRequest(StrategyManageService.fetchRisksRunning, {
    defaultValue: {
      strategy_running_status: [],
    },
    onSuccess: (newData) => {
      // 将新数据拼接到现有数据后面
      strategyRunningStatus.value = [
        ...strategyRunningStatus.value,
        ...newData.strategy_running_status,
      ];
    },
  });

  const handleScrollBottom = () => {
    // 如果正在加载或者已经加载完所有数据，则不再请求
    if (loading.value || currentOffset.value >= riskCount.value) return;

    // 增加偏移量
    currentOffset.value += pageSize;

    // 加载更多数据
    fetchRisksRunning({
      limit: pageSize,
      offset: currentOffset.value,
      strategy_id: props.data.strategy_id,
    });
  };

  watch(() => props.data, (data) => {
    // 切换策略时重置数据
    currentOffset.value = 0;
    strategyRunningStatus.value = [];

    fetchRisksRunning({
      limit: pageSize,
      offset: 0,
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
