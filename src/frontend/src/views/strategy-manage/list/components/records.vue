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
  <div
    ref="panelRef"
    class="strategy-records">
    <bk-alert
      class="strategy-records-alert"
      theme="info">
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

    <div class="strategy-records-table-wrap">
      <table-skeleton
        v-if="showSkeleton"
        class="strategy-records-skeleton"
        :columns="skeletonColumns"
        :row-count="8"
        row-size="medium" />
      <bk-table
        v-else
        ref="tableRef"
        :append-last-row="{ type: 'default' }"
        :border="['outer']"
        class="strategy-records-table"
        :columns="columns"
        :data="strategyRunningStatus"
        :max-height="tableMaxHeight"
        @scroll-bottom="handleScrollBottom">
        <template
          v-if="loadingMore"
          #appendLastRow>
          <div class="records-load-more">
            <audit-icon
              class="rotate-loading"
              svg
              type="loading" />
            <span>{{ t('加载中...') }}</span>
          </div>
        </template>
      </bk-table>
    </div>
  </div>
</template>
<script setup lang="tsx">
  import type { Column } from 'bkui-vue/lib/table/props';
  import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import type StrategyModel from '@model/strategy/strategy';

  import TableSkeleton from '@components/table-skeleton/index.vue';

  import useRequest from '@/hooks/use-request';

  interface Props {
    data: StrategyModel,
  }

  const props = defineProps<Props>();

  const { t } = useI18n();

  // 当前偏移量
  const currentOffset = ref(0);
  const pageSize = 20;
  const hasMore = ref(true);

  const strategyRunningStatus = ref<typeof runningData.value.strategy_running_status>([]);

  const riskCount = computed(() => props.data.risk_count);
  const skeletonColumns = [
    { width: 60 },
    { width: 220 },
    { width: 280 },
    { width: 160, grow: true },
  ];

  // 是否为实时调度
  const isStreamSource = computed(() => props.data.configs?.data_source?.source_type === 'stream_source');

  const columns = [
    {
      label: () => t('序号'),
      width: '8%',
      minWidth: 72,
      type: 'index',
    },
    {
      label: () => t('发起时间'),
      field: () => 'schedule_time',
      width: '26%',
      minWidth: 168,
    },
    {
      label: () => t('执行结果'),
      width: '34%',
      minWidth: 120,
      field: () => 'status_str',
      render: ({ data }: { data: Record<string, any> }) => <p
        style='display: flex; align-items: center; cursor: pointer;'>
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
      width: '28%',
      minWidth: 96,
    },
  ] as Column[];

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
      const list = newData.strategy_running_status || [];
      strategyRunningStatus.value = [
        ...strategyRunningStatus.value,
        ...list,
      ];
      hasMore.value = list.length >= pageSize;
    },
  });
  const tableRef = ref<{
    scrollTo?:(x?: number, y?: number) => void;
    getRoot?: () => HTMLElement | undefined;
  } | null>(null);
  const loadingMore = computed(() => loading.value && strategyRunningStatus.value.length > 0);
  const showSkeleton = computed(() => loading.value && strategyRunningStatus.value.length === 0);
  let keepScrollTop = 0;
  let stickToLoader = false;
  let holdingScroll = false;
  let restoreTimer = 0;

  const scrollBody = () => tableRef.value?.getRoot?.()?.querySelector('.bk-table-body') as HTMLElement | null;

  const restoreScroll = () => {
    if (!holdingScroll) return;
    const body = scrollBody();
    const top = stickToLoader && loadingMore.value && body
      ? Math.max(0, body.scrollHeight - body.clientHeight)
      : keepScrollTop;
    tableRef.value?.scrollTo?.(0, top);
    if (body) body.scrollTop = top;
  };

  const handleScrollBottom = () => {
    if (loading.value || !hasMore.value || holdingScroll) return;

    keepScrollTop = scrollBody()?.scrollTop ?? 0;
    const body = scrollBody();
    const gap = body ? body.scrollHeight - body.scrollTop - body.clientHeight : 0;
    stickToLoader = gap <= 8;
    holdingScroll = true;
    const nextOffset = currentOffset.value + pageSize;
    currentOffset.value = nextOffset;
    const settle = () => {
      nextTick(restoreScroll);
      window.clearTimeout(restoreTimer);
      restoreTimer = window.setTimeout(() => {
        restoreScroll();
        window.setTimeout(() => {
          restoreScroll();
          holdingScroll = false;
        }, 160);
      }, 90);
    };
    fetchRisksRunning({
      limit: pageSize,
      offset: nextOffset,
      strategy_id: props.data.strategy_id,
    }).then(settle)
      .catch(() => {
        currentOffset.value = nextOffset - pageSize;
        settle();
      });
  };

  const panelRef = ref<HTMLElement>();
  const tableMaxHeight = ref(360);
  let layoutObserver: ResizeObserver | undefined;
  let layoutRetry = 0;

  const syncTableMaxHeight = () => {
    const panel = panelRef.value;
    if (!panel) return;
    const { top } = panel.getBoundingClientRect();
    if (top < 1 || window.innerHeight - top < 80) {
      if (layoutRetry < 20) {
        layoutRetry += 1;
        window.setTimeout(syncTableMaxHeight, 50);
      }
      return;
    }
    const panelHeight = Math.floor(window.innerHeight - top);
    if (panel.clientHeight !== panelHeight) {
      panel.style.height = `${panelHeight}px`;
    }
    const wrap = panel.querySelector('.strategy-records-table-wrap') as HTMLElement | null;
    const height = wrap?.clientHeight ?? 0;
    if (height < 80) {
      if (layoutRetry < 20) {
        layoutRetry += 1;
        window.setTimeout(syncTableMaxHeight, 50);
      }
      return;
    }
    layoutRetry = 0;
    const nextHeight = height - 2;
    if (Math.abs(nextHeight - tableMaxHeight.value) > 1) {
      tableMaxHeight.value = nextHeight;
    }
  };

  onMounted(() => {
    nextTick(() => {
      const panel = panelRef.value;
      if (!panel) return;
      layoutObserver = new ResizeObserver(() => syncTableMaxHeight());
      layoutObserver.observe(panel);
      const wrap = panel.querySelector('.strategy-records-table-wrap');
      if (wrap) layoutObserver.observe(wrap);
      syncTableMaxHeight();
    });
    window.addEventListener('resize', syncTableMaxHeight);
  });

  onBeforeUnmount(() => {
    layoutObserver?.disconnect();
    window.removeEventListener('resize', syncTableMaxHeight);
  });

  watch(loadingMore, (visible) => {
    if (!visible) return;
    nextTick(restoreScroll);
    window.setTimeout(restoreScroll, 80);
    window.setTimeout(restoreScroll, 200);
  });

  watch(() => props.data, (data) => {
    holdingScroll = false;
    currentOffset.value = 0;
    hasMore.value = true;
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
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  height: calc(100vh - 52px);
  max-height: calc(100vh - 52px);
  min-height: 0;
  padding: 20px 40px;
  overflow: hidden;

  .strategy-records-alert {
    flex-shrink: 0;
  }

  .strategy-records-table-wrap {
    flex: 1;
    min-height: 0;
    margin-top: 12px;
    overflow: hidden;
  }

  .strategy-records-skeleton {
    height: 100%;
  }

  .strategy-records-table :deep(thead th) {
    border-right-color: transparent;
  }

  .records-load-more {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    width: 100%;
    height: 32px;
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-02);
  }

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
