<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<template>
  <div class="confirm-risk-handle">
    <bk-timeline
      v-if="timelineList.length"
      class="confirm-risk-handle-timeline"
      :list="timelineList">
      <template #content="{ tag }">
        <confirm-deal-form
          v-if="getNodeByTag(tag)?.type === 'confirm'"
          :detail-data="data"
          :risk-id="riskId"
          :user-info="userInfo"
          @update="handleFormUpdate" />
        <misreport
          v-else-if="isMisreportHistoryNode(getNodeByTag(tag))"
          :data="getNodeByTag(tag)!.historyData!" />
        <confirm-description
          v-else-if="isConfirmRiskHistoryNode(getNodeByTag(tag))"
          :data="getNodeByTag(tag)!.historyData!" />
      </template>
    </bk-timeline>
  </div>
</template>

<script setup lang="tsx">
  import {
    nextTick,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import AccountManageService from '@service/account-manage';

  import AccountModel from '@model/account/account';
  import type RiskManageModel from '@model/risk/risk';

  import useRequest from '@hooks/use-request';

  import ConfirmDealForm from '../confirm-deal-form.vue';
  import ConfirmDescription from '@views/risk-manage/detail/components/risk-handle/components/confirm-description.vue';
  import Misreport from '@views/risk-manage/detail/components/risk-handle/components/misreport.vue';

  interface Props {
    data: RiskManageModel,
    riskId: number | string,
  }

  interface Emits {
    (e: 'update'): void,
  }

  interface TimelineNode {
    type: 'confirm' | 'history',
    action: string,
    title: string,
    time: string,
    tag: string,
    historyData?: RiskManageModel['ticket_history'][number],
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const MISREPORT_HISTORY_ACTIONS = ['MisReport', 'ConfirmAsMisreport', 'ConfirmAsMisReport'];

  const timelineList = ref<Array<Record<string, any>>>([]);
  const timelineNodes = ref<TimelineNode[]>([]);
  let isInit = false;

  const {
    data: userInfo,
  } = useRequest(AccountManageService.fetchUserInfo, {
    defaultValue: new AccountModel(),
  });

  const historyActionMap: Record<string, string> = {
    NewRisk: t('风险单产生'),
    ConfirmRisk: t('风险确认'),
    ConfirmAsMisreport: t('标记误报'),
    ConfirmAsMisReport: t('标记误报'),
    MisReport: t('标记误报'),
    ReOpenMisReport: t('解除误报'),
    CloseRisk: t('风险单关闭'),
    TransOperator: t('转单'),
  };

  const CONFIRM_HISTORY_ACTIONS = ['ConfirmRisk', 'ConfirmAsMisreport', 'ConfirmAsMisReport'];

  const isAlreadyConfirmed = (historyList: Array<Record<string, any>>) => (
    historyList.some(item => CONFIRM_HISTORY_ACTIONS.includes(item.action))
  );

  const isMisreportHistoryNode = (node?: TimelineNode) => (
    !!node?.historyData && MISREPORT_HISTORY_ACTIONS.includes(node.action)
  );

  const isConfirmRiskHistoryNode = (node?: TimelineNode) => (
    !!node?.historyData && node.action === 'ConfirmRisk'
  );

  const shouldRenderTimelineContent = (node: TimelineNode) => (
    node.type === 'confirm'
    || isMisreportHistoryNode(node)
    || isConfirmRiskHistoryNode(node)
  );

  const canShowConfirmForm = (data: RiskManageModel) => {
    if (['closed'].includes(data.status)) {
      return false;
    }
    return !isAlreadyConfirmed(data.ticket_history || []);
  };

  const renderTimelineIcon = (action: string, active = false) => {
    const iconMap: Record<string, string> = {
      await_confirm: 'user',
      NewRisk: 'gaojingshijian',
      ConfirmRisk: 'user',
      ConfirmAsMisreport: 'biaojiwubao',
      ConfirmAsMisReport: 'biaojiwubao',
    };
    const iconType = iconMap[action] || 'gaojingshijian';
    return (
      <span
        class="confirm-risk-handle-timeline-icon"
        style={{
          background: active ? '#E1ECFF' : '#F0F1F5',
          color: active ? '#3A84FF' : '#989CA7',
        }}>
        <audit-icon type={ iconType } />
      </span>
    );
  };

  const renderTimelineTag = (title: string, time: string, index: number | string) => (
    `<p class="confirm-risk-handle-timeline-tag confirm-node-${index}">
      <span class="confirm-risk-handle-timeline-tag__title">${title}</span>
      <span class="confirm-risk-handle-timeline-tag__time">${time}</span>
    </p>`
  );

  const getHistoryTitle = (item: Record<string, any>) => {
    const title = historyActionMap[item.action] || item.action;
    if (['MisReport', 'ReOpenMisReport', 'ConfirmAsMisreport', 'ConfirmAsMisReport'].includes(item.action) && item.operator) {
      return `${item.operator} ${title}`;
    }
    return title;
  };

  const buildTimeline = (data: RiskManageModel) => {
    const historyList = data.ticket_history || [];
    const nodes: TimelineNode[] = [];
    const confirmed = isAlreadyConfirmed(historyList);

    if (canShowConfirmForm(data)) {
      const confirmTime = data.last_operate_time || data.event_time || '';
      nodes.push({
        type: 'confirm',
        action: 'await_confirm',
        title: t('风险确认'),
        time: confirmTime,
        tag: '',
      });
    }

    const newRiskHistory = historyList.find(item => item.action === 'NewRisk');
    nodes.push({
      type: 'history',
      action: 'NewRisk',
      title: t('风险单产生'),
      time: newRiskHistory?.time || data.event_time || '',
      tag: 'new-risk',
    });

    if (confirmed) {
      const confirmHistory = [...historyList]
        .reverse()
        .find(item => CONFIRM_HISTORY_ACTIONS.includes(item.action));
      if (confirmHistory) {
        nodes.push({
          type: 'history',
          action: confirmHistory.action,
          title: getHistoryTitle(confirmHistory),
          time: confirmHistory.time,
          tag: 'confirm-history',
          historyData: confirmHistory,
        });
      }
    }

    historyList.forEach((item, index) => {
      if ([
        'ForApprove',
        'AutoProcess',
        'NewRisk',
        ...CONFIRM_HISTORY_ACTIONS,
      ].includes(item.action)) {
        return;
      }
      nodes.push({
        type: 'history',
        action: item.action,
        title: getHistoryTitle(item),
        time: item.time,
        tag: `history-${index}`,
        historyData: item,
      });
    });

    timelineList.value = nodes.map((node, index) => ({
      tag: renderTimelineTag(node.title, node.time, index),
      content: shouldRenderTimelineContent(node) ? '<template/>' : '',
      icon: () => renderTimelineIcon(node.action, node.type === 'confirm'),
    }));
    timelineNodes.value = nodes.map((node, index) => ({
      ...node,
      tag: timelineList.value[index].tag,
    }));
  };

  const getNodeByTag = (tag: string) => {
    const index = timelineList.value.findIndex(item => item.tag === tag);
    return index >= 0 ? timelineNodes.value[index] : undefined;
  };

  const handleFormUpdate = () => {
    isInit = false;
    emits('update');
  };

  watch(() => props.riskId, () => {
    isInit = false;
    timelineList.value = [];
    timelineNodes.value = [];
  });

  watch(() => props.data, (data) => {
    if (!data?.risk_id) {
      return;
    }
    if (isInit && timelineNodes.value.length) {
      return;
    }
    buildTimeline(data);
    isInit = true;
  }, {
    immediate: true,
    deep: true,
  });

  watch(
    () => [props.data.status, props.data.ticket_history?.length],
    () => {
      if (!props.data?.risk_id) {
        return;
      }
      isInit = false;
      nextTick(() => {
        buildTimeline(props.data);
        isInit = true;
      });
    },
  );
</script>

<style scoped lang="postcss">
.confirm-risk-handle {
  width: 100%;
}

.confirm-risk-handle-timeline {
  --timeline-icon-size: 26px;
  --timeline-icon-gap: 12px;

  width: 100%;
  margin-top: 0;

  :deep(.bk-timeline) {
    margin-top: 0;
  }

  :deep(.bk-timeline-dot) {
    position: relative;
    display: grid;
    grid-template-columns: var(--timeline-icon-size) minmax(0, 1fr);
    grid-template-rows: auto auto;
    column-gap: var(--timeline-icon-gap);
    padding: 0 0 24px !important;
    margin-top: 0 !important;
    overflow: visible;
    font-size: 12px;
    border-left: none !important;

    &::before {
      display: none !important;
    }

    &:not(:last-child)::after {
      position: absolute;
      top: var(--timeline-icon-size);
      bottom: 0;
      left: calc(var(--timeline-icon-size) / 2 - .5px);
      width: 1px;
      background: #dcdee5;
      content: '';
    }

    &:last-child {
      padding-bottom: 0 !important;
    }
  }

  :deep(.bk-timeline-icon) {
    position: relative !important;
    top: auto !important;
    left: auto !important;
    z-index: 1;
    display: flex;
    width: var(--timeline-icon-size) !important;
    height: var(--timeline-icon-size) !important;
    background: transparent !important;
    border: none !important;
    grid-column: 1;
    grid-row: 1;
    align-self: start;
    align-items: center;
    justify-content: center;
  }

  :deep(.bk-timeline-section) {
    position: static !important;
    top: auto !important;
    display: contents !important;
  }

  :deep(.bk-timeline-title) {
    display: block;
    grid-column: 2;
    grid-row: 1;
    align-self: start;
    padding-bottom: 12px;
    margin-top: 0;
    font-size: 12px;
    line-height: 20px;
    color: inherit;
    cursor: default;
  }

  :deep(.bk-timeline-dot:has(.bk-timeline-content:empty) .bk-timeline-title) {
    padding-bottom: 0;
  }

  :deep(.bk-timeline-content) {
    position: relative;
    z-index: 1;
    width: 100%;
    max-width: none !important;
    font-size: 12px;
    color: inherit;
    word-break: normal;
    grid-column: 2;
    grid-row: 2;

    &:empty {
      display: none;
    }
  }

  :deep(.confirm-risk-handle-timeline-tag) {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin: 0;
  }

  :deep(.confirm-risk-handle-timeline-tag__title) {
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    color: #313238;
  }

  :deep(.confirm-risk-handle-timeline-tag__time) {
    font-size: 12px;
    line-height: 20px;
    color: #979ba5;
  }

  :deep(.confirm-risk-handle-timeline-icon) {
    display: inline-flex;
    width: var(--timeline-icon-size);
    height: var(--timeline-icon-size);
    border-radius: 50%;
    align-items: center;
    justify-content: center;

    .audit-icon {
      font-size: 16px;
      line-height: 1;
    }
  }

  :deep(.bk-timeline-content .reopen-mis-report-wrap),
  :deep(.bk-timeline-content .approve-wrap),
  :deep(.bk-timeline-content .risk-experience-wrap) {
    padding: 0;
    font-size: 12px;
    color: #63656e;
    background: transparent;
    border: none;
    border-radius: 0;
    box-shadow: none;
  }

  :deep(.bk-timeline-content .approve-wrap > .mis-content),
  :deep(.bk-timeline-content .reopen-mis-report-wrap > .mis-content),
  :deep(.bk-timeline-content .risk-experience-wrap > .mis-content) {
    padding: 12px 8px 12px 12px;
    margin-top: 0;
    background: #f5f7fa;
    border-radius: 2px;

    .render-info-item .info-label {
      width: auto !important;
      max-width: none !important;
      min-width: 0 !important;
      text-align: left;
      flex: 0 0 auto !important;
    }

    .render-info-item .info-value {
      padding-left: 4px;
    }
  }
}
</style>
