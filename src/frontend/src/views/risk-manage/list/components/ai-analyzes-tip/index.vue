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
    class="ai-analyzes">
    <div class="tip-content">
      <audit-icon
        class="info-fill"
        type="info-fill" />
      <span class="text">{{ t('共搜索出') }}</span>
      <span class="highlight">{{ total }}</span>
      <span class="text">{{ tipText }}</span>
      <span
        class="action-btn">
        <img
          class="ai-agent-ai"
          height="14"
          src="@images/ai.svg"
          width="24">
        <span
          v-bk-tooltips="{
            disabled: !(total === 0 || total >= 100),
            content: total === 0 ? t('至少包含 1 条风险数据才能使用') : t('最多支持 100 条，请添加筛选条件后使用')
          }"
          :class="(total > 0 && total < 100 && isSearch) ? '' : 'disabled'"
          @click="handleAnalyze">
          {{ t('智能分析') }}
        </span>
      </span>
      <span class="text">{{ t('或查看') }}</span>
      <span
        class="action-btn"
        @click="handleHistory">
        <img
          class="ai-agent-history"
          height="14"
          src="@images/history.svg"
          width="24">
        {{ t('历史分析报告') }}
      </span>
      <!-- 条件标签信息 -->
    </div>
  </div>
  <analyze-dialog
    ref="analyzeDialogRef"
    :condition-tags="conditionTags"
    :search-params="searchParams"
    :total="total"
    @analyze-finished="handleAnalyzeFinished" />

  <report-drawer
    v-model:isShow="showReportDrawer"
    :item-info="itemInfo"
    @refresh="handleRefreshList"
    @update:item-info="(val:string) => handleUpdate(val)" />

  <history-report-drawer
    ref="historyDrawerRef"
    v-model:isShow="showHistoryDrawer"
    @open-report="handleOpenReport"
    @view-risks="handleViewRisks" />
</template>

<script setup lang="tsx">
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskManageService from '@service/risk-manage';

  import useRequest from '@hooks/use-request';

  import AnalyzeDialog from './dialog.vue';
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

  const { t } = useI18n();

  const analyzeDialogRef = ref<InstanceType<typeof AnalyzeDialog>>();
  const historyDrawerRef = ref<InstanceType<typeof HistoryReportDrawer>>();
  const showReportDrawer = ref(false);
  const showHistoryDrawer = ref(false);
  const itemInfo = ref<string>('');
  const isSearch = ref(false);
  const tipText = computed(() => {
    if (isSearch.value) {
      if (props.total > 0 && props.total < 100) {
        return t('可对所有风险单进行');
      }
      return t('可修改筛选条件后进行');
    }
    return t('可添加筛选条件后进行');
  });

  const handleAnalyze = () => {
    if ((props.total > 0 && props.total < 100 && isSearch)) {
      analyzeDialogRef.value?.show();
    }
  };


  // 获取ai报告详情
  const {
    run: getAiAnalyseReportDetail,
  } = useRequest(RiskManageService.getAiAnalyseReportDetail, {
    defaultValue: [],
    onSuccess(data) {
      console.log('获取ai报告详情>>>>', data);
      showReportDrawer.value = true;
      itemInfo.value = JSON.stringify(data);
    },
  });
  const handleOpenReport = (item: HistoryReportItem) => {
    console.log('handleOpenReport', item);
    getAiAnalyseReportDetail({
      report_id: item.report_id,
    });
  };

  const handleViewRisks = () => {
    // TODO: 跳转到关联风险列表或弹窗
  };

  const handleRefreshList = () => {
    // 如果历史报告抽屉是打开的，刷新列表
    if (showHistoryDrawer.value && historyDrawerRef.value) {
      // 通过ref直接调用history-report-drawer组件的刷新方法
      historyDrawerRef.value?.listRef?.fetchData({ report_keyword: '' });
    }
  };

  const handleUpdate = (val: string) => {
    itemInfo.value = val;
  };

  const handleAnalyzeFinished = (data: string) => {
    itemInfo.value = data;
    showReportDrawer.value = true;
  };
  // 监听conditionTags变化，更新isSearch状态
  watch(() => props.conditionTags, (newTags) => {
    isSearch.value = newTags.length > 0;
  }, { immediate: true });

  const handleHistory = () => {
    showHistoryDrawer.value = true;
  };
  defineExpose<Exposes>({
    changeIsSearch() {
      isSearch.value = true;
    },
  });
</script>

<style lang='postcss' scoped>
.ai-analyzes {
  height: 32px;
  padding: 0 20px;
  margin-top: 16px;
  line-height: 32px;
  background-color: #fff;
  border: 1px solid #e2e6ed;

  .tip-content {
    display: flex;
    align-items: center;
    font-size: 12px;

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
    }

    .action-btn {
      display: flex;
      margin: 0 4px;
      color: #3a84ff;
      cursor: pointer;
      align-items: center;

      &:hover {
        color: #699df4;
      }

      .action-icon {
        margin-right: 4px;
        font-size: 14px;
      }

      .disabled {
        color: #979ba5;
        cursor: not-allowed;
      }
    }

    .condition-tags-info {
      display: flex;
      margin-left: 8px;
      align-items: center;
      flex-wrap: wrap;

      .condition-tag-item {
        display: inline-flex;
        padding: 2px 6px;
        margin: 0 4px;
        font-size: 12px;
        color: #63656e;
        background: #f0f1f5;
        border-radius: 2px;
        align-items: center;

        .tag-label {
          color: #4d4f56;
        }

        .tag-value {
          font-weight: 700;
          color: #4d4f56;
        }
      }
    }
  }

  :deep(.bk-alert-wraper) {
    .bk-alert-icon-info {
      height: 22px;
      line-height: 22px;
    }

    .bk-alert-title {
      font-size: 12px;
      line-height: 22px;
    }
  }
}
</style>
