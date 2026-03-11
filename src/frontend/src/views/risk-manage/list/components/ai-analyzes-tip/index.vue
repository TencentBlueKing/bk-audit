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
    v-if="total > 0"
    class="ai-analyzes">
    <div class="tip-content">
      <audit-icon
        class="info-fill"
        type="info-fill" />
      <span class="text">{{ t('共搜索出') }}</span>
      <span class="highlight">{{ total }}</span>
      <span class="text">{{ t('条风险单，可对所有风险单进行') }}</span>
      <span
        class="action-btn"
        @click="handleAnalyze">
        <img
          class="ai-agent-ai"
          height="14"
          src="@images/ai.svg"
          width="24">
        {{ t('智能分析') }}
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
    </div>
  </div>
  <analyze-dialog
    ref="analyzeDialogRef"
    :total="total"
    @analyze-finished="handleAnalyzeFinished" />

  <report-drawer
    v-model:isShow="showReportDrawer"
    :meta-list="currentReportMeta"
    :title="currentReportTitle" />

  <history-report-drawer
    v-model:isShow="showHistoryDrawer"
    @open-report="handleOpenReport"
    @view-risks="handleViewRisks" />
</template>

<script setup lang="tsx">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import AnalyzeDialog from './dialog.vue';
  import type { HistoryReportItem } from './history-report-drawer.vue';
  import HistoryReportDrawer from './history-report-drawer.vue';
  import ReportDrawer from './report-drawer.vue';

  interface Props {
    total?: number;
  }

  withDefaults(defineProps<Props>(), {
    total: 0,
  });

  const { t } = useI18n();

  const analyzeDialogRef = ref<InstanceType<typeof AnalyzeDialog>>();
  const showReportDrawer = ref(false);
  const showHistoryDrawer = ref(false);
  const currentReportTitle = ref('');
  const currentReportMeta = ref<Array<{ key: string, label: string, value: string }>>([]);

  const handleAnalyze = () => {
    analyzeDialogRef.value?.show();
  };

  const handleHistory = () => {
    showHistoryDrawer.value = true;
  };

  const handleOpenReport = (row: HistoryReportItem) => {
    currentReportTitle.value = row.title;
    currentReportMeta.value = [
      { key: 'type', label: t('报告类型'), value: row.reportTypeLabel },
      { key: 'scope', label: t('分析范围'), value: row.analysisScope },
      { key: 'count', label: t('风险条数'), value: `${row.riskCount} ${t('条')}` },
      { key: 'creator', label: t('生成人'), value: row.creator },
      { key: 'time', label: t('生成时间'), value: row.createTime },
    ];
    showHistoryDrawer.value = false;
    showReportDrawer.value = true;
  };

  const handleViewRisks = () => {
    // TODO: 跳转到关联风险列表或弹窗
  };

  const handleAnalyzeFinished = (payload: { type: 'recommend' | 'custom', title?: string, requirement?: string }) => {
    if (payload.type === 'recommend') {
      currentReportTitle.value = payload.title || t('智能分析报告');
    } else {
      currentReportTitle.value = t('自定义分析报告');
    }
    currentReportMeta.value = [
      { key: 'type', label: t('报告类型'), value: t('人员调查') },
      { key: 'scope', label: t('分析范围'), value: t('责任人-张三') },
      { key: 'count', label: t('风险条数'), value: `11 ${t('条')}` },
      { key: 'creator', label: t('生成人'), value: 'admin' },
      { key: 'time', label: t('生成时间'), value: '2026-02-03 14:50' },
    ];
    showReportDrawer.value = true;
  };
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
