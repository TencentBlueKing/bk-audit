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
    class="risk-manage-detail-handle-part">
    <div class="title mb16">
      {{ t('工单处理') }}
    </div>
    <div class="header">
      <div style="margin-right: auto;">
        <!-- 标记误报 / 解除误报 -->
        <mark-misreport-btn
          v-if="(data.risk_label === 'misreport')|| (data.risk_label==='normal')"
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
    nextTick,
    // computed,
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
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
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
  } = useRequest(ProcessApplicationManageService.fetchApplicationsAll, {
    defaultValue: [],
    manual: true,
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
          tag: `<p style='font-size: 12px;' class='${item.action}-${index}'>
                <span style='color: #313238;margin-left:4px;'>
                  ${['MisReport', 'ReOpenMisReport'].includes(item.action)
          ? `${item.operator} ${historyActionMap[item.action].name}`
          : historyActionMap[item.action].name || item.action}</span>
                <span style='color: #979BA5;margin-left: 8px;'>${item.time}</span>
              <p>`,
          content: '<template/>',
          icon: () => <span style='background: #F0F1F5;width: 26px;height: 26px;border-radius: 50%;display: inline-block;text-align:center;line-height: 26px;'>
            <audit-icon type={ historyActionMap[item.action].icon }  style='color: #989CA7;font-size: 16px;' />
          </span>,
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
          tag: `<p style='font-size: 12px;' class='${item.action}-${data.ticket_history.length}'>
                <span style='color: #313238;margin-left: 4px;'>${historyActionMap[item.action].name || item.action}</span>
                <span style='color: #979BA5;margin-left: 8px;'>${item.time}</span>
              <p>`,
          content: '<template/>',
          icon: () => <span style='background: #F0F1F5;width: 26px;height: 26px;border-radius: 50%;display: inline-block;text-align:center;line-height: 26px;'>
            <audit-icon type={ historyActionMap[item.action].icon }  style='color: #989CA7;font-size: 16px;'/>
          </span>,
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
  }, {
    immediate: true,
    deep: true,
  });
</script>
<style scoped lang="postcss">
.risk-manage-detail-handle-part {
  padding: 0 14px 14px;

  .title {
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    color: #313238;
  }

  .header {
    display: flex;
    padding-bottom: 20px;
    justify-content: space-between;
    align-items: center;
  }
}

.risk-handle-timeline {
  :deep(.bk-timeline-dot .bk-timeline-content) {
    max-width: 100%;
  }
}
</style>
