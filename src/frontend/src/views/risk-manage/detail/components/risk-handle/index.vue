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
    ref="rootRef"
    class="risk-manage-detail-handle-part"
    :class="{ 'is-embedded': embedded }">
    <div
      v-if="!embedded"
      class="title mb16">
      {{ t('工单处理') }}
    </div>
    <div
      v-if="showHeaderActions"
      class="header">
      <div style="margin-right: auto;">
        <!-- 标记误报 / 解除误报 -->
        <mark-misreport-btn
          v-if="showHeaderMisreportBtn"
          class="mr16"
          :data="data"
          :last-ticket-history="_.last(ticketHistory)"
          :user-info="userInfo"
          @update="handleUpdate" />
        <!-- 重开 -->
        <reopen-btn
          v-if="data.status==='closed' && data.risk_label ==='normal'"
          class="mr16"
          :data="data"
          :user-info="userInfo"
          @update="handleUpdate" />
        <!-- 跳转到风险总结的锚点 -->
        <span id="risk-manage-content-btn" />
        <!-- 风险总结 -->
        <risk-content-btn
          v-if="data.status==='closed'"
          :data="data"
          :user-info="userInfo"
          @update="handleUpdate" />
      </div>
    </div>
    <bk-timeline
      v-if="list && list.length"
      class="risk-handle-timeline"
      :list="list">
      <template #content="{tag}">
        <!-- {{ getIndexByTag(tag).action }} -->
        <component
          :is="comMap[getIndexByTag(tag).action as keyof typeof comMap]"
          :data="getIndexByTag(tag)"
          :detail-data="data"
          :event-data-list="eventDataList"
          :itsm-status-data="itsmStatusData"
          :process-application-list="processApplicationList"
          :process-detail="processPackageIdToDetailMap"
          :risk-field-map="riskFieldMap"
          :risk-id="riskId"
          :status-data="statusData"
          :user-info="userInfo"
          @update="handleUpdate" />
      </template>
    </bk-timeline>
  </div>
</template>

<script setup lang='tsx'>
  import _ from 'lodash';
  import {
    computed,
    nextTick,
    onMounted,
    ref,
    watch,
  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';

  import AccountManageService from '@service/account-manage';
  import ItsmManageService from '@service/itsm-manage';
  import ProcessApplicationManageService from '@service/process-application-manage';
  import RiskManageService from '@service/risk-manage';
  import SoapManageService from '@service/soap-manage';

  import AccountModel from '@model/account/account';
  import type RiskManageModel from '@model/risk/risk';

  import useRequest from '@hooks/use-request';
  import useUrlSearch from '@hooks/use-url-search';

  import AwaitDeal from './components/await-deal.vue';
  import MarkMisreportBtn from './components/button/mark-misreport.vue';
  import ReopenBtn from './components/button/re-open.vue';
  import RiskContentBtn from './components/button/risk-content.vue';
  import CloseRisk from './components/closerisk.vue';
  import CustomProcess  from './components/custom-process.vue';
  import ForApprove from './components/for-approve.vue';
  import MisReport from './components/misreport.vue';
  import ReOpenMisReport from './components/reopen-misreport.vue';

  interface Emits{
    (e:'update'): void
  }
  interface Props{
    data: RiskManageModel,
    riskId: number,
    eventDataList: Record<string, any>[],
    embedded?: boolean,
  }
  const props = withDefaults(defineProps<Props>(), {
    embedded: false,
  });
  const emits = defineEmits<Emits>();

  const showHeaderMisreportBtn = computed(() => {
    // 已标记误报时展示「解除误报」
    if (props.data.risk_label === 'misreport') {
      return true;
    }
    // 单据关闭后不展示「标记误报」
    if (props.data.status === 'closed') {
      return false;
    }
    if (props.data.risk_label !== 'normal') {
      return false;
    }
    if (props.embedded && ['await_deal', 'processing'].includes(props.data.status)) {
      return false;
    }
    return true;
  });

  const showHeaderActions = computed(() => (
    showHeaderMisreportBtn.value
    || (props.data.status === 'closed' && props.data.risk_label === 'normal')
    || props.data.status === 'closed'
  ));

  const { getSearchParams, removeSearchParam } = useUrlSearch();
  const { t } = useI18n();
  const ticketHistory = ref([] as Record<string, any>[]);

  const rootRef = ref();
  const needScrollToContent = ref(false);

  const historyActionMap: Record<string, {
    name: string,
    icon: string,
  }> = {
    await_deal: {
      name: t('人工处理'),
      icon: 'user',
    },
    NewRisk: {
      name: t('风险单产生'),
      icon: 'gaojingshijian',
    },
    MisReport: {
      name: t('标记误报'),
      icon: 'biaojiwubao',
    },
    ReOpenMisReport: {
      name: t('解除误报'),
      icon: 'jiechuwubao',
    },
    ForApprove: {
      name: t('执行处理套餐'),
      icon: 'taocanchulizhong',
    },
    CustomProcess: {
      name: t('人工处理'),
      icon: 'user',
    },
    OperateFailed: {
      name: t('自动处理失败'),
      icon: 'alert',
    },
    AutoProcess: {
      name: t('执行处理套餐'),
      icon: 'taocanchulizhong',
    },
    CloseRisk: {
      name: t('风险单关闭'),
      icon: 'jieshu',
    },
    ReOpen: {
      name: t('重开单据'),
      icon: 'reopen',
    },
  };
  const comMap = {
    ReOpenMisReport,
    MisReport,
    ForApprove,
    CloseRisk,
    OperateFailed: CloseRisk,
    CustomProcess,
    ReOpen: ReOpenMisReport,
    AutoProcess: ForApprove,
    NewRisk: 'div',
    await_deal: AwaitDeal,
  };
  const processPackageIdToDetailMap = ref<Record<string, any>>({});
  let isInit = false;
  const list = ref<Record<string, any>[]>([]);
  const riskFieldMap = ref<Record<string, string>>({});

  // 自动处理节点 - 获取单据状态枚举值
  const {
    data: statusData,
  } = useRequest(SoapManageService.fetchStatusCommon, {
    manual: true,
    defaultValue: [],
  });

  // 审批节点=状态
  const {
    data: itsmStatusData,
  } = useRequest(ItsmManageService.fetchStatusCommon, {
    manual: true,
    defaultValue: [],
  });
  // 获取处理套餐列表
  const {
    data: processApplicationList,
    run: fetchApplicationsAll,
  } = useRequest(ProcessApplicationManageService.fetchApplicationsAll, {
    defaultValue: [],
    defaultParams: {
      scene_id: props.data.scene_id,
    },
    // manual: true,
    onSuccess() {
      // 查询所有套餐详情参数
      handleFetchParamsDetail();
    },
  });
  //  获取风险可用字段
  useRequest(RiskManageService.fetchFields, {
    defaultValue: [],
    manual: true,
    onSuccess(data) {
      riskFieldMap.value = data.reduce((res, item) => {
        res[item.id] = item.name;
        return res;
      }, {} as Record<string, string>);
    },
  });
  // 获取处理套餐详情
  const {
    run: fetchDetail,
  } = useRequest(SoapManageService.fetchDetail, {
    defaultValue: {},
  });
  // 获取userinfo
  const {
    data: userInfo,
  } = useRequest(AccountManageService.fetchUserInfo, {
    defaultValue: new AccountModel(),
    manual: true,
  });

  const handleUpdate = () => {
    isInit = false;
    emits('update');
  };

  const renderTimelineIcon = (action: string, active = false) => (
    <span
      class="risk-handle-timeline-icon"
      style={{
        background: active ? '#E1ECFF' : '#F0F1F5',
        color: active ? '#3A84FF' : '#989CA7',
      }}>
      <audit-icon type={ historyActionMap[action].icon } />
    </span>
  );

  const renderTimelineTag = (action: string, index: number, title: string, time: string) => (
    `<p class="risk-handle-timeline-tag ${action}-${index}">
      <span class="risk-handle-timeline-tag__title">${title}</span>
      <span class="risk-handle-timeline-tag__time">${time}</span>
    </p>`
  );

  const getTimelineTitle = (item: Record<string, any>) => (
    ['MisReport', 'ReOpenMisReport'].includes(item.action)
      ? `${item.operator} ${historyActionMap[item.action].name}`
      : historyActionMap[item.action].name || item.action
  );

  const getIndexByTag = (tag: string) => {
    const index = list.value.findIndex(item => item.tag === tag);
    return ticketHistory.value[index];
  };
  // 查询所有套餐详情参数
  const handleFetchParamsDetail = () => {
    if (!isInit) return;
    const paIds = [] as string[];
    ticketHistory.value.forEach((item) => {
      if (item.action === 'CustomProcess') {
        if (item.pa_id && !paIds.includes(item.pa_id)) {
          paIds.push(item.pa_id);
        }
      }
    });
    paIds.forEach((id) => {
      const sopsTemplateId = processApplicationList.value
        .find(item => item.id === id)?.sops_template_id;
      if (sopsTemplateId) {
        fetchDetail({
          id: sopsTemplateId,
        }).then((data) => {
          if (!data) return;
          processPackageIdToDetailMap.value[id] = data;
        });
      }
    });
  };
  onMounted(() => {
    const params = getSearchParams();
    if (params.scrollToContent) {
      needScrollToContent.value = true;
    }
  });

  watch(() => props.data, (data) => {
    if (data && data.ticket_history && !isInit) {
      list.value = [];
      ticketHistory.value = [];
      data.ticket_history.forEach((item, index) => {
        const listParam = {
          tag: renderTimelineTag(item.action, index, getTimelineTitle(item), item.time),
          content: '<template/>',
          icon: () => renderTimelineIcon(item.action),
        };
        if (!['ForApprove', 'AutoProcess'].includes(item.action)) {
          list.value.push(listParam);
          ticketHistory.value.push(item);
        } else {
          // 不合并的情况
          if ((item.action === 'ForApprove' && data.ticket_history[index + 1]?.action !== 'AutoProcess')
            || (item.action === 'AutoProcess' && data.ticket_history[index - 1]?.action !== 'ForApprove')) {
            list.value.push(listParam);
            ticketHistory.value.push(item);
          } else if (item.action === 'AutoProcess' && data.ticket_history[index - 1]?.action === 'ForApprove') {
            // 合并
            const lastForApproveItem = data.ticket_history[index - 1];
            if (lastForApproveItem) {
              const tmpItem = item;
              tmpItem.forApproveItem = lastForApproveItem;
              list.value.push(listParam);
              ticketHistory.value.push(item);
            }
          }
        }
      });
      // await_deal和processing的情况多渲染一个表单
      if (data.status === 'await_deal' || data.status === 'processing') {
        const item = Object.assign({}, data.ticket_history[data.ticket_history.length - 1]);
        item.action = 'await_deal'; // 使用await_deal组件来处理两种状态
        list.value.push({
          tag: renderTimelineTag(
            item.action,
            data.ticket_history.length,
            historyActionMap[item.action].name || item.action,
            item.time,
          ),
          content: '<template/>',
          icon: () => renderTimelineIcon(item.action, true),
        });
        ticketHistory.value.push(item);
      }
      // 翻转列表
      list.value.reverse();
      ticketHistory.value.reverse();
      isInit = true;

      if (ticketHistory.value.length > 0) {
        handleFetchParamsDetail();
      }
      nextTick(() => {
        const el =  document.getElementById('risk-manage-content-btn');
        if (el && needScrollToContent.value) {
          el.scrollIntoView();
          needScrollToContent.value = false;
          removeSearchParam('scrollToContent');
        }
      });
    }
    if (data.scene_id) {
      fetchApplicationsAll({
        scene_id: data.scene_id,
      });
    }
  }, {
    immediate: true,
    deep: true,
  });
</script>
<style scoped lang="postcss">
.risk-manage-detail-handle-part {
  padding: 0 14px 14px;

  &.is-embedded {
    padding: 0;

    .risk-handle-timeline {
      padding-left: 0;
    }
  }

  .title {
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    color: #313238;
  }

  .header {
    display: flex;
    padding-bottom: 12px;
    justify-content: space-between;
    align-items: center;
  }
}

.risk-handle-timeline {
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

  :deep(.bk-timeline-item-custom-icon) {
    margin-top: 0 !important;
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

    .bk-timeline-icon-inner {
      display: flex;
      width: var(--timeline-icon-size);
      height: var(--timeline-icon-size);
      align-items: center;
      justify-content: center;
      transform: none !important;
    }
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

  :deep(.risk-handle-timeline-tag) {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin: 0;
  }

  :deep(.risk-handle-timeline-tag__title) {
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    color: #313238;
  }

  :deep(.risk-handle-timeline-tag__time) {
    font-size: 12px;
    line-height: 20px;
    color: #979ba5;
  }

  :deep(.risk-handle-timeline-icon) {
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
  :deep(.bk-timeline-content .approve-wrap) {
    padding: 0;
    font-size: 12px;
    color: #63656e;
    background: transparent;
    border: none;
    border-radius: 0;
    box-shadow: none;
  }

  :deep(.bk-timeline-content .approve-wrap > .mis-content),
  :deep(.bk-timeline-content .reopen-mis-report-wrap > .mis-content) {
    padding: 12px 8px 12px 12px;
    margin-top: 8px;
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

  :deep(.bk-timeline-content .reopen-mis-report-wrap > .mis-title),
  :deep(.bk-timeline-content .approve-wrap > .mis-title) {
    padding: 0;
  }
}
</style>
