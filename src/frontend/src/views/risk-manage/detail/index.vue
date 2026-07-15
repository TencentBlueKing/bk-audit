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
  <bk-loading :loading="loading || strategyLoading || statusLoading">
    <div class="risk-manage-detail-wrap mb12">
      <div class="left">
        <!-- {{ detailData }} -->
        <base-info
          :data="detailData"
          :risk-status-common="riskStatusCommon"
          :strategy-list="strategyList"
          @updated-data="handleUpdatedData" />
        <!-- 关联事件 / 事件调查报告 -->
        <bk-tab
          v-model:active="active"
          class="risk-detail-tab"
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
              :strategy-list="strategyList"
              @get-event-data="handleGetEventData"
              @updated-data="handleUpdatedData" />
          </bk-tab-panel>
        </bk-tab>
      </div>
      <risk-handle-dock
        v-if="route.name !== 'attentionManageDetail'"
        :current-stage-name="currentStageName">
        <risk-handle
          :data="riskData"
          embedded
          :event-data-list="eventDataList"
          :risk-id="riskData.risk_id"
          @update="handleUpdate" />
      </risk-handle-dock>
    </div>
  </bk-loading>
  <teleport
    v-if="isHeaderSlotActive"
    to="#teleport-router-link">
    <bk-button
      :key="`risk-copy-link-${route.fullPath}`"
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
      :key="`risk-generate-report-${route.fullPath}`"
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

<script setup lang='ts'>
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

  import {
    execCopy,
  } from '@utils/assist';

  import BaseInfo from './components/base-info.vue';
  import EditEventReport from './components/event-report/edit-event-report.vue';
  import EventReport from './components/event-report/index.vue';
  import LinkEvent from './components/link-event.vue';
  import RiskHandleDock from './components/risk-handle-dock.vue';
  import RiskHandle from './components/risk-handle/index.vue';

  const router = useRouter();
  const route = useRoute();
  const { t } = useI18n();
  const eventDataList = ref();
  const isShowEditEventReport = ref(false);
  const renderComRef = ref();
  const hasAutoOpenedReport = ref(false);
  const { isActive: isHeaderSlotActive, isPageActive, claim: claimHeaderSlot } = usePageHeaderSlot();

  const stageNameMap: Record<string, string> = {
    await_deal: t('人工处理'),
    processing: t('人工处理'),
    for_approve: t('执行处理套餐'),
    auto_process: t('执行处理套餐'),
    closed: t('风险单关闭'),
    new: t('风险单产生'),
    stand_by: t('风险创建中'),
  };

  const comMap: Record<string, any> = {
    eventReport: EventReport,
    linkEvent: LinkEvent,
  };

  const panels = [
    { name: 'eventReport', label: t('事件调查报告') },
    { name: 'linkEvent', label: t('关联事件') },
  ];

  const active = ref<keyof typeof comMap>('linkEvent');

  let timeout: undefined | number = undefined;
  let reportGeneratingTimer: undefined | number = undefined;

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
  // 查询详情
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
      // 如果正在生成报告，启动快速轮询（每3秒）
      if (data.report_generating) {
        startReportGeneratingPolling();
      } else {
        stopReportGeneratingPolling();
        // 原有的状态轮询逻辑
        if (['for_approve', 'auto_process'].includes(data.status)) {
          startPolling();
        } else {
          clearTimeout(timeout);
        }
      }
    },
  });

  // 获取策略事件信息
  const {
    data: strategyInfoData,
  } = useRequest(RiskManageService.fetchRiskInfo, {
    defaultValue: new StrategyInfo(),
    defaultParams: {
      id: route.params.riskId,
    },
    manual: true,
  });

  const currentStageName = computed(() => stageNameMap[riskData.value.status] || t('人工处理'));

  const handleUpdate = () => {
    fetchRiskList({
      id: route.params.riskId,
    });
  };
  // 轮训查询详情（原有逻辑，60秒一次）
  const startPolling = () => {
    clearTimeout(timeout);
    timeout = setTimeout(() => {
      handleUpdate();
    }, 60 * 1000);
  };
  // 报告生成时的轮询（10秒一次）
  const startReportGeneratingPolling = () => {
    stopReportGeneratingPolling();
    const poll = () => {
      fetchRiskList({
        id: route.params.riskId,
      });
    };
    // 立即执行一次 +++
    poll();
    // 每5秒轮询一次
    reportGeneratingTimer = window.setInterval(poll, 5000);
  };
  // 停止报告生成轮询
  const stopReportGeneratingPolling = () => {
    if (reportGeneratingTimer !== undefined) {
      clearInterval(reportGeneratingTimer);
      reportGeneratingTimer = undefined;
    }
  };

  const handleCopyLink = () => {
    const route = window.location.href;
    execCopy(route, t('复制成功'));
  };

  const handleGenerateReport = () => {
    isShowEditEventReport.value = true;
  };

  // 合并数据（包含事件信息配置）
  const detailData = computed(() => ({
    ...riskData.value,
    ...strategyInfoData.value,
  }));

  // 无调查报告时只展示「关联事件」页签，保证标题可见
  const visiblePanels = computed(() => (
    detailData.value.has_report
      ? panels
      : panels.filter(item => item.name === 'linkEvent')
  ));

  // 有无调查报告时，保证当前页签始终有效；有报告时默认落在报告页签
  watch(
    () => detailData.value.has_report,
    (hasReport) => {
      active.value = hasReport ? 'eventReport' : 'linkEvent';
    },
    {
      immediate: true,
    },
  );

  const canGenerateReport = computed(() => (
    !!detailData.value.permission?.edit_risk_v2
    && !detailData.value.has_report
  ));

  // 获取事件信息
  const handleGetEventData = (data: any) => {
    eventDataList.value = data;
  };
  // 更新
  const handleUpdatedData = () => {
    handleUpdate();
  };
  useRouterBack(() => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { tab, ...rest } = route.query;
    const listNameMap = {
      riskManageDetail: 'riskManageList',
      handleManageDetail: 'handleManageList',
      attentionManageDetail: 'attentionManageList',
      processedManageDetail: 'processedManageList',
      sceneRiskManageDetail: 'sceneRiskManageList',
    };
    router.push({
      name: listNameMap[route.name as keyof typeof listNameMap],
      query: rest,
    });
  });
  const tryOpenEditReport = () => {
    if (hasAutoOpenedReport.value) {
      return;
    }
    if (route.query.openEditReport !== 'true' || active.value !== 'eventReport') {
      return;
    }
    nextTick(() => {
      const refs = renderComRef.value;
      const reportRef = Array.isArray(refs)
        ? refs.find((item: any) => typeof item?.showReport === 'function')
        : refs;
      if (reportRef?.showReport) {
        reportRef.showReport();
        hasAutoOpenedReport.value = true;
      }
    });
  };

  watch(
    () => [detailData.value, active.value, route.query.openEditReport],
    (val) => {
      if (val[0]) {
        tryOpenEditReport();
      }
    },
    {
      immediate: true,
    },
  );
  watch(
    () => route.fullPath,
    () => {
      if (isPageActive.value) {
        claimHeaderSlot();
      }
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
.risk-manage-detail-wrap {
  .left {
    width: 100%;
    padding-right: 0;

    .risk-detail-tab {
      margin-top: 16px;
      overflow: visible;

      :deep(.bk-tab-content) {
        height: auto;
        min-height: 0;
        overflow: visible;
      }
    }
  }
}

</style>
