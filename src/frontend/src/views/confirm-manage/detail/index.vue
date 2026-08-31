<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<template>
  <bk-loading :loading="pageLoading">
    <div class="confirm-manage-detail-wrap mb12">
      <div class="left">
        <base-info
          :data="detailData"
          :risk-status-common="riskStatusCommon"
          :strategy-list="strategyList"
          @updated-data="handleUpdatedData" />
        <bk-tab
          :key="detailData.has_report ? 'confirm-detail-with-report' : 'confirm-detail-link-only'"
          v-model:active="active"
          class="risk-detail-tab"
          :class="{ 'risk-detail-tab--hide-panel-header': !detailData.has_report }"
          type="card-grid">
          <bk-tab-panel
            v-for="item in visiblePanels"
            :key="item.name"
            :label="item.label"
            :name="item.name">
            <component
              :is="comMap[item.name]"
              ref="renderComRef"
              :data="detailData"
              :show-section-title="!detailData.has_report"
              :strategy-list="strategyList"
              @get-event-data="handleGetEventData"
              @updated-data="handleUpdatedData" />
          </bk-tab-panel>
        </bk-tab>
      </div>
      <risk-handle-dock
        :key="`confirm-handle-dock-${route.fullPath}`"
        :current-stage-name="t('风险确认')"
        :default-expanded="shouldExpandHandleDock">
        <confirm-risk-handle
          :key="`confirm-handle-${riskData.risk_id}`"
          :data="riskData"
          :risk-id="riskData.risk_id"
          @update="handleUpdate" />
      </risk-handle-dock>
    </div>
  </bk-loading>
  <teleport
    v-if="isHeaderSlotActive"
    to="#teleport-router-link">
    <bk-button
      :key="`confirm-copy-link-${route.fullPath}`"
      v-bk-tooltips="t('复制链接')"
      text
      theme="primary"
      @click="handleCopyLink">
      <audit-icon
        style="font-size: 14px;"
        type="link" />
    </bk-button>
  </teleport>
  <teleport
    v-if="isHeaderSlotActive && canGenerateReport"
    to="#teleport-generate-report">
    <bk-button
      :key="`confirm-generate-report-${route.fullPath}`"
      v-bk-tooltips="t('生成调查报告')"
      theme="primary"
      @click="handleGenerateReport">
      <audit-icon
        style="margin-right: 8px;font-size: 14px;"
        type="add" />
      {{ t('创建调查报告') }}
    </bk-button>
  </teleport>
  <edit-event-report
    v-model:isShowEditEventReport="isShowEditEventReport"
    :report-auto-render="detailData.report_auto_render"
    :report-enabled="detailData.report_enabled"
    :status="detailData.report?.status"
    :strategy-id="detailData.strategy_id"
    @update="handleUpdate" />
</template>

<script setup lang="ts">
  import {
    computed,
    nextTick,
    onBeforeUnmount,
    onMounted,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
    useRouter,
  } from 'vue-router';

  import RiskManageService from '@service/risk-manage';
  import StrategyManageService from '@service/strategy-manage';

  import RiskManageModel from '@model/risk/risk';
  import StrategyInfo from '@model/risk/strategy-info';

  import useRequest from '@hooks/use-request';
  import usePageHeaderSlot from '@hooks/use-page-header-slot';
  import useRouterBack from '@hooks/use-router-back';

  import { execCopy } from '@utils/assist';

  import ConfirmRiskHandle from '../components/confirm-risk-handle/index.vue';
  import BaseInfo from '@views/risk-manage/detail/components/base-info.vue';
  import EditEventReport from '@views/risk-manage/detail/components/event-report/edit-event-report.vue';
  import EventReport from '@views/risk-manage/detail/components/event-report/index.vue';
  import LinkEvent from '@views/risk-manage/detail/components/link-event.vue';
  import RiskHandleDock from '@views/risk-manage/detail/components/risk-handle-dock.vue';

  const router = useRouter();
  const route = useRoute();
  const { t } = useI18n();
  const eventDataList = ref();
  const isShowEditEventReport = ref(false);
  const renderComRef = ref();
  const { isActive: isHeaderSlotActive, refresh: refreshHeaderSlot } = usePageHeaderSlot();

  const comMap: Record<string, any> = {
    eventReport: EventReport,
    linkEvent: LinkEvent,
  };

  const panels = [
    { name: 'eventReport', label: t('事件调查报告') },
    { name: 'linkEvent', label: t('关联事件列表') },
  ];

  const active = ref<keyof typeof comMap>('eventReport');

  let timeout: undefined | number = undefined;
  let reportGeneratingTimer: undefined | number = undefined;
  let syncedActiveTabRiskId: string | undefined;

  const {
    loading: strategyLoading,
    data: strategyList,
  } = useRequest(StrategyManageService.fetchAllStrategyList, {
    manual: true,
    defaultValue: [],
  });

  const {
    data: riskStatusCommon,
    loading: statusLoading,
  } = useRequest(RiskManageService.fetchRiskStatusCommon, {
    manual: true,
    defaultValue: [],
  });

  const {
    loading,
    data: riskData,
    run: fetchRiskList,
  } = useRequest(RiskManageService.fetchRiskById, {
    defaultValue: new RiskManageModel(),
    defaultParams: {
      id: route.params.riskId,
    },
    manual: true,
    onSuccess(data) {
      const riskIdKey = String(data.risk_id ?? route.params.riskId);
      if (syncedActiveTabRiskId !== riskIdKey) {
        syncedActiveTabRiskId = riskIdKey;
        nextTick(() => {
          active.value = data.has_report ? 'eventReport' : 'linkEvent';
        });
      }
      if (data.report_generating) {
        startReportGeneratingPolling();
      } else {
        stopReportGeneratingPolling();
        if (['for_approve', 'auto_process'].includes(data.status)) {
          startPolling();
        } else {
          clearTimeout(timeout);
        }
      }
    },
  });

  const {
    data: strategyInfoData,
  } = useRequest(RiskManageService.fetchRiskInfo, {
    defaultValue: new StrategyInfo(),
    defaultParams: {
      id: route.params.riskId,
    },
    manual: true,
  });

  const shouldExpandHandleDock = computed(() => route.query.tab === 'handleRisk');

  const pageLoading = computed(() => (
    (!riskData.value.risk_id && loading.value)
    || strategyLoading.value
    || statusLoading.value
  ));

  const detailData = computed(() => ({
    ...riskData.value,
    ...strategyInfoData.value,
  }));

  const visiblePanels = computed(() => (
    detailData.value.has_report
      ? panels
      : panels.filter(item => item.name === 'linkEvent')
  ));

  const canGenerateReport = computed(() => (
    !!detailData.value.permission?.edit_risk_v2
    && !detailData.value.has_report
  ));

  const refreshLinkEventList = () => {
    nextTick(() => {
      const refs = renderComRef.value;
      const list = Array.isArray(refs) ? refs : [refs];
      list.forEach((item: any) => {
        item?.refreshLinkEvents?.();
      });
    });
  };

  const handleUpdate = () => {
    fetchRiskList({
      id: route.params.riskId,
    }).then(() => {
      refreshLinkEventList();
    });
  };

  const startPolling = () => {
    clearTimeout(timeout);
    timeout = setTimeout(() => {
      handleUpdate();
    }, 60 * 1000);
  };

  const startReportGeneratingPolling = () => {
    stopReportGeneratingPolling();
    const poll = () => {
      fetchRiskList({
        id: route.params.riskId,
      });
    };
    poll();
    reportGeneratingTimer = window.setInterval(poll, 5000);
  };

  const stopReportGeneratingPolling = () => {
    if (reportGeneratingTimer !== undefined) {
      clearInterval(reportGeneratingTimer);
      reportGeneratingTimer = undefined;
    }
  };

  const handleCopyLink = () => {
    execCopy(window.location.href, t('复制成功'));
  };

  const handleGenerateReport = () => {
    isShowEditEventReport.value = true;
  };

  const handleGetEventData = (data: any) => {
    eventDataList.value = data;
  };

  const handleUpdatedData = () => {
    handleUpdate();
  };

  useRouterBack(() => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { tab, ...rest } = route.query;
    router.push({
      name: 'confirmManageList',
      query: rest,
    });
  });

  watch(
    () => route.params.riskId,
    () => {
      syncedActiveTabRiskId = undefined;
    },
  );

  watch(
    () => route.fullPath,
    () => {
      refreshHeaderSlot();
    },
  );

  onMounted(() => {
    nextTick(() => {
      if (route.query.openEditReport === 'false') {
        handleGenerateReport();
      }
    });
  });

  onBeforeUnmount(() => {
    if (timeout) {
      clearTimeout(timeout);
    }
    stopReportGeneratingPolling();
  });
</script>

<style scoped lang="postcss">
.confirm-manage-detail-wrap {
  .left {
    width: 100%;
    padding-right: 0;
  }

  .risk-detail-tab {
    margin-top: 16px;
    overflow: visible;

    :deep(.bk-tab-content) {
      height: auto;
      min-height: 0;
      padding: 0;
      overflow: visible;
    }

    &.risk-detail-tab--hide-panel-header {
      margin-top: 16px;

      :deep(.bk-tab-header) {
        display: none;
      }

      :deep(.bk-tab-content) {
        padding: 0;
      }
    }
  }
}
</style>
