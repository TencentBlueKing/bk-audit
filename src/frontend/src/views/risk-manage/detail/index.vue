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
      <div
        class="left"
        :style="{
          width: route.name === 'attentionManageDetail' ? '100%' : (
            isShowSide ? 'calc(100% - 368px)' : '100%'
          )
        }">
        <!-- {{ detailData }} -->
        <base-info
          :data="detailData"
          :risk-status-common="riskStatusCommon"
          :strategy-list="strategyList"
          @updated-data="handleUpdatedData" />
        <!-- 关联事件 -->
        <div
          v-if="!detailData.has_report"
          class="link-event-wrap">
          <link-event
            :data="detailData"
            :strategy-list="strategyList"
            @get-event-data="handleGetEventData"
            @updated-data="handleUpdatedData" />
        </div>
        <bk-tab
          v-else
          v-model:active="active"
          style="margin-top: 16px;"
          type="card-grid">
          <bk-tab-panel
            v-for="item in panels"
            :key="item.name"
            :label="item.label"
            :name="item.name">
            <scroll-faker>
              <component
                :is="renderCom"
                :data="detailData"
                :strategy-list="strategyList"
                @get-event-data="handleGetEventData"
                @updated-data="handleUpdatedData" />
            </scroll-faker>
          </bk-tab-panel>
        </bk-tab>
      </div>
      <!-- 事件处理 -->
      <scroll-faker
        v-if="route.name !== 'attentionManageDetail'"
        :style="isShowSide ? 'width: 368px; height: auto; min-height: 85vh;' : 'width: 0px; height: 0px;' ">
        <div class="right">
          <div
            class="open-right"
            @click="handleOpenRight">
            <audit-icon
              class="angle-double-up"
              :style="{ transform: isShowSide ? 'rotateZ(90deg)' : 'rotateZ(-90deg)' }"
              type="angle-double-up" />
            <span>{{ isShowSide ? t('收起工单处理') : t('展开工单处理') }}</span>
          </div>
          <risk-handle
            v-if="isShowSide"
            :data="riskData"
            :event-data-list="eventDataList"
            :risk-id="riskData.risk_id"
            @update="handleUpdate" />
        </div>
      </scroll-faker>
    </div>
    <teleport to="#teleport-router-link">
      <bk-button
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
      v-if="detailData.permission?.edit_risk_v2 && !detailData.has_report"
      to="#teleport-generate-report">
      <bk-button
        v-bk-tooltips="t('生成调查报告')"
        theme="primary"
        @click="handleGenerateReport">
        <audit-icon
          style="margin-right: 8px;font-size: 14px;"
          type="add" />
        {{ t('创建调查报告') }}
      </bk-button>
    </teleport>
  </bk-loading>
  <edit-event-report
    v-model:isShowEditEventReport="isShowEditEventReport"
    :report-enabled="detailData.report_enabled"
    :status="detailData.report?.status"
    :strategy-id="detailData.strategy_id"
    @update="handleUpdate" />
</template>

<script setup lang='ts'>
  import {
    computed,
    onBeforeUnmount,
    onMounted,
    ref,
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
  import useRouterBack from '@hooks/use-router-back';

  import {
    execCopy,
  } from '@utils/assist';

  import BaseInfo from './components/base-info.vue';
  import EditEventReport from './components/event-report/edit-event-report.vue';
  import EventReport from './components/event-report/index.vue';
  import LinkEvent from './components/link-event.vue';
  import RiskHandle from './components/risk-handle/index.vue';

  const router = useRouter();
  const route = useRoute();
  const { t } = useI18n();
  const eventDataList = ref();
  const isShowSide = ref(true);
  const isShowEditEventReport = ref(false);

  let timeout: undefined | number = undefined;
  const handleOpenRight = () => {
    isShowSide.value = !isShowSide.value;
  };

  const renderCom = computed(() => comMap[active.value]);
  const comMap: Record<string, any> = {
    eventReport: EventReport,
    linkEvent: LinkEvent,
  };

  const panels = [
    { name: 'eventReport', label: t('事件调查报告') },
    { name: 'linkEvent', label: t('关联事件列表') },
  ];

  const active = ref<keyof typeof comMap>('eventReport');

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
      if (['for_approve', 'auto_process'].includes(data.status)) {
        startPolling();
      } else {
        clearTimeout(timeout);
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

  const handleUpdate = () => {
    fetchRiskList({
      id: route.params.riskId,
    });
  };
  // 轮训查询详情
  const startPolling = () => {
    clearTimeout(timeout);
    timeout = setTimeout(() => {
      handleUpdate();
    }, 60 * 1000);
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
    };
    router.push({
      name: listNameMap[route.name as keyof typeof listNameMap],
      query: rest,
    });
  });

  onMounted(() => {
    const observer = new MutationObserver(() => {
      const left = document.querySelector('.left');
      const right = document.querySelector('.right') as HTMLDivElement;
      if (left && right) {
        right.style.height = `${left.scrollHeight}px`;
      }
    });
    observer.observe(document.querySelector('.left') as Node, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
    });

    onBeforeUnmount(() => {
      observer.takeRecords();
      observer.disconnect();
      clearTimeout(timeout);
    });
  });
</script>
<style scoped lang="postcss">
.risk-manage-detail-wrap {
  display: flex;

  .left {
    width: calc(100% - 368px);
    padding-right: 16px;

    .link-event-wrap {
      padding: 10px 16px;
      margin-top: 16px;
      background: #fff;
      border-radius: 2px;
      box-shadow: 0 2px 4px 0 #1919290d;
    }
  }

  .right {
    .open-right {
      position: absolute;
      top: 120px;
      left: -10px;
      z-index: 1000;
      width: 30px;
      padding: 10px;
      color: #fff;
      cursor: pointer;
      background: #cbccd2;
      border-radius: 8px;
      box-shadow: 0 2px 4px 0 #1919290d;

      &:hover {
        background: #c4c6cc;
      }

      .angle-double-up {
        display: inline-block;
      }
    }
  }
}

</style>
