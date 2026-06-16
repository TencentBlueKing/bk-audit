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
  <div class="ai-analyzes">
    <div class="tip-bar">
      <audit-icon
        class="info-fill"
        type="info-fill" />
      <span class="text">{{ tipContent.prefix }}</span>
      <span class="highlight">{{ total }}</span>
      <span class="text">{{ tipContent.suffix }}</span>
    </div>
    <div class="list-panel">
      <div class="action-toolbar">
        <div class="action-left">
          <bk-button
            v-bk-tooltips="analyzeTooltip"
            class="analyze-btn"
            :disabled="!isAnalyzeEnabled"
            outline
            @click="handleAnalyze">
            <img
              class="ai-agent-ai"
              height="14"
              src="@images/ai.svg"
              width="24">
            {{ t('智能分析') }}
          </bk-button>
          <slot name="toolbar-after-analyze" />
        </div>
        <div class="action-right">
          <bk-button
            class="history-btn"
            outline
            @click="handleHistory">
            <img
              class="ai-agent-history"
              height="14"
              src="@images/history.svg"
              width="24">
            {{ t('历史分析报告') }}
          </bk-button>
        </div>
      </div>
      <div class="list-content">
        <slot />
      </div>
    </div>
  </div>
  <analyze-dialog
    ref="analyzeDialogRef"
    :condition-tags="conditionTags"
    :search-params="searchParams"
    :total="total"
    @analyze-failed="handleAnalyzeFailed"
    @analyze-started="handleAnalyzeStarted" />

  <report-drawer
    v-model:isShow="showReportDrawer"
    :item-info="itemInfo"
    @refresh="handleRefreshList"
    @update:item-info="(val:string) => handleUpdate(val)" />

  <history-report-drawer
    ref="historyDrawerRef"
    v-model:isShow="showHistoryDrawer"
    @analyze-finished="handleAnalyzeFinished"
    @open-report="handleOpenReport"
    @view-risks="handleViewRisks" />
</template>

<script setup lang="tsx">
  import { computed, nextTick, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskManageService from '@service/risk-manage';

  import useRequest from '@hooks/use-request';

  import AnalyzeDialog from './dialog.vue';
  import type { AnalyzeStartPayload } from './dialog.vue';
  import type { HistoryReportItem } from './history-report-drawer.vue';
  import HistoryReportDrawer from './history-report-drawer.vue';
  import ReportDrawer from './report-drawer.vue';

  interface Props {
    total?: number;
    conditionTags?: any[];
    searchParams?: Record<string, any>;
  }

  interface Exposes {
    changeIsSearch: () => void;
  }

  const props = withDefaults(
    defineProps<Props>(),
    {
      total: 0,
      conditionTags: () => [],
      searchParams: () => ({}),
    },
  );

  const hasTagValue = (value: unknown) => {
    if (value === undefined || value === null || value === '') {
      return false;
    }
    if (Array.isArray(value)) {
      return value.some(item => item !== undefined && item !== null && item !== '');
    }
    return true;
  };

  const hasUserSearchConditions = computed(() => {
    const hasFieldFilters = props.conditionTags.some((tag: any) => tag.removable && hasTagValue(tag.value));
    const eventFilters = props.searchParams?.event_filters;
    const hasEventFilters = Array.isArray(eventFilters)
      ? eventFilters.length > 0
      : !!eventFilters;
    return hasFieldFilters || hasEventFilters;
  });

  const { t } = useI18n();

  const analyzeDialogRef = ref<InstanceType<typeof AnalyzeDialog>>();
  const historyDrawerRef = ref<InstanceType<typeof HistoryReportDrawer>>();
  const showReportDrawer = ref(false);
  const showHistoryDrawer = ref(false);
  const itemInfo = ref<string>('');

  const tipContent = computed(() => {
    if (!hasUserSearchConditions.value) {
      return {
        prefix: t('当前共有'),
        suffix: t('条风险单，可选择目标风险单进行智能分析，或查看历史分析报告'),
      };
    }
    if (props.total === 0) {
      return {
        prefix: t('共搜索到'),
        suffix: t('条风险单，可重置筛选条件或选择目标风险单后进行智能分析，或查看历史分析报告'),
      };
    }
    if (props.total >= 100) {
      return {
        prefix: t('共搜索到'),
        suffix: t('条风险单，可添加筛选条件或选择目标风险单后进行智能分析，或查看历史分析报告'),
      };
    }
    return {
      prefix: t('共搜索到'),
      suffix: t('条风险单，可选择目标风险单进行智能分析，或查看历史分析报告'),
    };
  });

  const isAnalyzeEnabled = computed(() => props.total > 0 && props.total < 100 && hasUserSearchConditions.value);

  const analyzeTooltip = computed(() => ({
    disabled: !(props.total === 0 || props.total >= 100),
    content: props.total === 0
      ? t('至少选择 1 条风险数据才能使用')
      : t('当前数据量为 {total} 条，最多支持分析 100 条数据', { total: props.total }),
  }));

  const handleAnalyze = () => {
    if (isAnalyzeEnabled.value) {
      analyzeDialogRef.value?.show();
    }
  };


  // 获取ai报告详情
  const {
    run: getAiAnalyseReportDetail,
  } = useRequest(RiskManageService.getAiAnalyseReportDetail, {
    defaultValue: [],
    onSuccess(data) {
      showReportDrawer.value = true;
      itemInfo.value = JSON.stringify(data);
    },
  });
  const handleOpenReport = (item: HistoryReportItem) => {
    getAiAnalyseReportDetail({
      report_id: item.report_id ?? item.id,
    });
  };

  const handleViewRisks = () => {
    // TODO: 跳转到关联风险列表或弹窗
  };

  const handleRefreshList = () => {
    // 如果历史报告抽屉是打开的，刷新列表
    if (showHistoryDrawer.value && historyDrawerRef.value) {
      // 通过ref直接调用history-report-drawer组件的刷新方法
      historyDrawerRef.value?.listRef?.fetchData({ keyword: undefined, sort: ['-created_at'] });
    }
  };

  const handleUpdate = (val: string) => {
    itemInfo.value = val;
  };

  const handleAnalyzeStarted = (payload: AnalyzeStartPayload) => {
    showHistoryDrawer.value = true;
    nextTick(() => {
      historyDrawerRef.value?.beginAnalyzeWatch(payload);
    });
  };

  const handleAnalyzeFailed = (payload: { title: string }) => {
    historyDrawerRef.value?.markAnalyzeFailed(payload.title);
  };

  const handleAnalyzeFinished = (data: string) => {
    itemInfo.value = data;
    showReportDrawer.value = true;
  };

  const handleHistory = () => {
    showHistoryDrawer.value = true;
  };
  defineExpose<Exposes>({
    changeIsSearch() {
      // 保留对外接口，搜索状态由筛选条件自动计算
    },
  });
</script>

<style lang='postcss' scoped>
.ai-analyzes {
  position: relative;
  z-index: 1;
  width: 100%;
  min-width: 0;
  margin-top: 16px;

  .tip-bar {
    display: flex;
    height: 32px;
    padding: 0;
    margin-bottom: 8px;
    font-size: 12px;
    line-height: 32px;
    align-items: center;

    .info-fill {
      margin-right: 4px;
      color: #979ba5;
    }

    .text {
      color: #4d4f56;
    }

    .highlight {
      margin: 0 4px;
      font-weight: bold;
      color: #4d4f56;
    }
  }

  .list-panel {
    width: 100%;
    min-width: 0;
    padding: 0 20px 16px;
    overflow: hidden;
    background-color: #fff;
    border: 1px solid #e2e6ed;
    box-sizing: border-box;
  }

  .action-toolbar {
    display: flex;
    padding: 8px 0 12px;
    align-items: center;
    justify-content: space-between;

    .action-left,
    .action-right {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    :deep(.analyze-btn) {
      color: #7b29ff;
      border-color: #7b29ff;

      &:not(.is-disabled):hover {
        color: #9b5cff;
        border-color: #9b5cff;
      }

      &.is-disabled {
        color: #c4c6cc;
        border-color: #dcdee5;
      }

      .ai-agent-ai {
        margin-right: 4px;
      }
    }

    :deep(.history-btn) {
      color: #4d4f56;
      border-color: #c4c6cc;

      &:hover {
        color: #4d4f56;
        border-color: #979ba5;
      }

      .ai-agent-history {
        margin-right: 4px;
      }
    }
  }

  .list-content {
    width: 100%;
    min-width: 0;
    padding: 0;
    overflow: hidden;

    :deep(.audit-tdesign-list) {
      width: 100%;
      max-width: 100%;
      min-width: 0;
    }

    :deep(.tdesign-list-pagination) {
      padding: 12px 0;
      margin-top: 16px;
    }
  }
}
</style>
