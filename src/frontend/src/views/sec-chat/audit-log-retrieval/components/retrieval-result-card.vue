<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
    10|  software distributed under the License is distributed on
  an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
  either express or implied. See the License for the
  specific language governing permissions and limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
-->
<template>
  <div
    class="retrieval-result-wrap"
    :class="{ 'is-embedded': embedded }">
    <div
      class="retrieval-result-card"
      :class="{ 'is-embedded': embedded }">
      <!-- 已识别筛选条件：自然语言检索气泡展示，条件筛选内嵌结果不展示 -->
      <div
        v-if="!embedded"
        class="condition-section">
        <div class="condition-header">
          <audit-icon
            class="condition-icon"
            type="search1" />
          <span>已识别到 {{ result.conditions.length }} 个筛选条件进行检索</span>
        </div>
        <div class="condition-tags">
          <span
            v-for="(item, index) in result.conditions"
            :key="`${item.field}-${index}`"
            class="condition-tag">
            <span class="tag-label">{{ item.field }}：</span>
            <span class="tag-value">{{ item.value }}</span>
          </span>
        </div>
      </div>

      <!-- 过程信息 -->
      <div
        v-if="!embedded"
        class="process-section">
        <div
          class="process-row"
          @click="toolsExpanded = !toolsExpanded">
          <audit-icon
            class="process-arrow"
            :class="{ 'is-collapsed': !toolsExpanded }"
            type="angle-line-down" />
          <span>已调用 {{ result.toolCount }} 个工具</span>
        </div>
        <div
          v-if="toolsExpanded"
          class="process-detail">
          已调用检索解析、权限校验、日志查询工具
        </div>
        <div
          class="process-row"
          @click="thinkExpanded = !thinkExpanded">
          <audit-icon
            class="process-arrow"
            :class="{ 'is-collapsed': !thinkExpanded }"
            type="angle-line-down" />
          <span>思考了 {{ result.thinkSeconds }} 秒</span>
        </div>
        <div
          v-if="thinkExpanded"
          class="process-detail">
          已根据自然语言意图匹配字段并生成检索条件
        </div>
      </div>

      <!-- 结果摘要 -->
      <div class="summary-section">
        <div class="summary-main">
          <h3 class="summary-title">
            {{ result.title }}
          </h3>
          <p class="summary-desc">
            共命中
            <span class="summary-num">{{ formatNumber(result.totalHit) }}</span>
            条日志，数据量较大，已展示前
            <span class="summary-num">{{ result.previewCount }}</span>
            条预览
          </p>
        </div>
        <bk-dropdown
          class="export-dropdown"
          placement="bottom-start"
          trigger="click">
          <bk-button class="export-btn">
            <audit-icon
              class="export-icon"
              type="download" />
            导出
          </bk-button>
          <template #content>
            <bk-dropdown-menu>
              <bk-dropdown-item @click="handleExport('preview')">
                导出前 {{ result.previewCount }} 条数据
              </bk-dropdown-item>
              <bk-dropdown-item @click="handleExport('all')">
                导出全量数据
              </bk-dropdown-item>
            </bk-dropdown-menu>
          </template>
        </bk-dropdown>
      </div>

      <!-- 数据预览表 -->
      <div class="table-section">
        <div class="table-scroll">
          <table class="result-table">
            <thead>
              <tr>
                <th>操作起始时间</th>
                <th>操作人</th>
                <th>操作人账号类型</th>
                <th>来源系统</th>
                <th>操作结果</th>
                <th>操作途径</th>
                <th>来源IP</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, index) in pageRows"
                :key="`${row.startTime}-${index}`">
                <td>{{ row.startTime }}</td>
                <td>{{ row.operator }}</td>
                <td>{{ row.accountType }}</td>
                <td>{{ row.system }}</td>
                <td>{{ row.result }}</td>
                <td>{{ row.method }}</td>
                <td>{{ row.sourceIp }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="table-pagination">
          <bk-pagination
            v-model="currentPage"
            align="right"
            :count="result.rows.length"
            :layout="['total', 'limit', 'list']"
            :limit="pageSize"
            :limit-list="[10, 20, 50]"
            location="right"
            size="small"
            @change="handlePageChange"
            @limit-change="handleLimitChange" />
        </div>
      </div>

      <!-- 后续操作 -->
      <div class="action-section">
        <bk-button
          class="analyze-btn"
          outline
          @click="analyzeDialogShow = true">
          <img
            alt=""
            class="ai-agent-ai"
            height="14"
            :src="aiSvg"
            width="24">
          智能分析
        </bk-button>
        <bk-button
          class="statistics-btn"
          outline
          @click="handleStatistics">
          <audit-icon
            class="action-icon"
            type="shujutongji" />
          数据统计
        </bk-button>
      </div>

      <!-- 报告生成状态 -->
      <div
        v-if="reportItems.length"
        class="report-status-section"
        :class="{ 'is-done': hasDoneReport }">
        <div
          v-for="item in reportItems"
          :key="item.id"
          class="report-status-row">
          <template v-if="item.status === 'loading'">
            <audit-icon
              class="status-icon is-loading"
              type="loading" />
            <span class="status-text">{{ item.title }}生成中...</span>
          </template>
          <template v-else>
            <audit-icon
              class="status-icon is-success"
              type="success" />
            <span class="status-text">{{ item.title }}已生成</span>
            <span class="status-time">{{ item.createdAt }}</span>
            <button
              class="view-report-btn"
              type="button"
              @click="openReport(item)">
              <audit-icon
                class="view-icon"
                type="help-document-fill" />
              查看报告
            </button>
          </template>
        </div>
      </div>

      <!-- 反馈操作：位于对话框内部底部 -->
      <div class="feedback-row">
        <button
          class="feedback-btn"
          title="复制"
          type="button"
          @click="handleCopy">
          <audit-icon type="copy" />
        </button>
        <button
          class="feedback-btn"
          :class="{ 'is-active': feedback === 'up' }"
          title="有用"
          type="button"
          @click="feedback = feedback === 'up' ? '' : 'up'">
          <svg
            class="feedback-svg"
            fill="none"
            height="16"
            viewBox="0 0 16 16"
            width="16">
            <path
              :d="thumbUpPath"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.2" />
          </svg>
        </button>
        <button
          class="feedback-btn"
          :class="{ 'is-active': feedback === 'down' }"
          title="无用"
          type="button"
          @click="feedback = feedback === 'down' ? '' : 'down'">
          <svg
            class="feedback-svg"
            fill="none"
            height="16"
            viewBox="0 0 16 16"
            width="16">
            <path
              :d="thumbDownPath"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.2" />
          </svg>
        </button>
        <button
          class="feedback-btn"
          title="重新生成"
          type="button"
          @click="$emit('regenerate')">
          <audit-icon type="refresh" />
        </button>
      </div>
    </div>

    <log-analyze-dialog
      v-model="analyzeDialogShow"
      :conditions="result.conditions"
      :total-hit="result.totalHit"
      @select="handleAnalyzeSelect" />

    <log-statistics-dialog
      v-model="statisticsDialogShow"
      @confirm="handleStatisticsConfirm" />

    <log-report-drawer
      v-model:is-show="reportDrawerShow"
      :conditions="result.conditions"
      :report="activeReport"
      :systems="systemNames"
      :total-hit="result.totalHit" />

    <log-statistics-drawer
      v-model:is-show="statisticsDrawerShow"
      :created-at="statisticsCreatedAt"
      :fields="statisticsFields" />
  </div>
</template>

<script lang="ts" setup>
  import { computed, onBeforeUnmount, ref, watch } from 'vue';

  import useMessage from '@hooks/use-message';

  import aiSvg from '@images/ai.svg';

  import LogAnalyzeDialog from './log-analyze-dialog.vue';
  import LogReportDrawer, { type LogReportInfo } from './log-report-drawer.vue';
  import LogStatisticsDialog from './log-statistics-dialog.vue';
  import LogStatisticsDrawer from './log-statistics-drawer.vue';
  import type { RetrievalResultPayload } from '../../types';

  interface ReportStatusItem extends LogReportInfo {
    status: 'loading' | 'done';
  }

  const props = withDefaults(defineProps<{
    result: RetrievalResultPayload;
    embedded?: boolean;
  }>(), {
    embedded: false,
  });

  const emit = defineEmits<{
    export: [mode: 'preview' | 'all'];
    analyze: [];
    statistics: [];
    regenerate: [];
  }>();

  const { messageSuccess } = useMessage();

  const thumbUpPath = 'M5.2 14.5H3.4c-.5 0-.9-.4-.9-.9V7.8c0-.5.4-.9.9-.9h1.8v7.6z'
    + 'M13.4 6.9H9.7l.5-2.4c.1-.6-.1-1.2-.5-1.6L9 2.2c-.2-.2-.5-.2-.7 0l-.2.2'
    + 'c-.2.2-.3.5-.2.8l.6 2.4H6.1v7.6h5.8c.7 0 1.3-.5 1.4-1.2l.7-4.2'
    + 'c.1-.7-.4-1.4-1.2-1.4h-.4z';
  const thumbDownPath = 'M10.8 1.5h1.8c.5 0 .9.4.9.9v5.8c0 .5-.4.9-.9.9h-1.8V1.5z'
    + 'M2.6 9.1h3.7l-.5 2.4c-.1.6.1 1.2.5 1.6l.7.7c.2.2.5.2.7 0l.2-.2'
    + 'c.2-.2.3-.5.2-.8l-.6-2.4h2.4V1.5H4.1c-.7 0-1.3.5-1.4 1.2L2 6.9'
    + 'c-.1.7.4 1.4 1.2 1.4h-.6z';

  const toolsExpanded = ref(false);
  const thinkExpanded = ref(false);
  const currentPage = ref(1);
  const pageSize = ref(10);
  const feedback = ref<'up' | 'down' | ''>('');
  const analyzeDialogShow = ref(false);
  const statisticsDialogShow = ref(false);
  const reportItems = ref<ReportStatusItem[]>([]);
  const reportDrawerShow = ref(false);
  const activeReport = ref<LogReportInfo | null>(null);
  const statisticsDrawerShow = ref(false);
  const statisticsCreatedAt = ref('');
  const statisticsFields = ref<string[]>([]);
  let generateTimer: ReturnType<typeof setTimeout> | null = null;

  const pageRows = computed(() => {
    const start = (currentPage.value - 1) * pageSize.value;
    return props.result.rows.slice(start, start + pageSize.value);
  });

  const hasDoneReport = computed(() => reportItems.value.some(item => item.status === 'done'));

  const systemNames = computed(() => {
    const systemCond = props.result.conditions.find(item => item.field === '来源系统');
    return systemCond?.value || '已选系统';
  });

  watch(() => props.result, () => {
    currentPage.value = 1;
    feedback.value = '';
    reportItems.value = [];
    reportDrawerShow.value = false;
    activeReport.value = null;
    statisticsDrawerShow.value = false;
    statisticsFields.value = [];
    if (generateTimer) {
      clearTimeout(generateTimer);
      generateTimer = null;
    }
  });

  onBeforeUnmount(() => {
    if (generateTimer) clearTimeout(generateTimer);
  });

  const formatNumber = (num: number) => num.toLocaleString('en-US');

  const formatNow = () => {
    const d = new Date();
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  };

  const handlePageChange = (page: number) => {
    currentPage.value = page;
  };

  const handleLimitChange = (limit: number) => {
    pageSize.value = limit;
    currentPage.value = 1;
  };

  const handleExport = (mode: 'preview' | 'all') => {
    emit('export', mode);
    messageSuccess(mode === 'preview'
      ? `已选择导出前 ${props.result.previewCount} 条数据`
      : '已选择导出全量数据');
  };

  const startGenerate = (
    items: Array<{ id: string; type: 'analyze' | 'statistics'; title: string }>,
    options?: { openStatistics?: boolean; fields?: string[] },
  ) => {
    if (generateTimer) clearTimeout(generateTimer);
    reportItems.value = items.map(item => ({
      ...item,
      status: 'loading',
      createdAt: '',
    }));
    generateTimer = setTimeout(() => {
      const createdAt = formatNow();
      reportItems.value = reportItems.value.map(item => ({
        ...item,
        status: 'done',
        createdAt,
      }));
      if (options?.openStatistics) {
        statisticsFields.value = options.fields || [];
        statisticsCreatedAt.value = createdAt;
        statisticsDrawerShow.value = true;
      } else {
        const primary = reportItems.value.find(item => item.type === 'analyze') || reportItems.value[0];
        if (primary) openReport(primary);
      }
      generateTimer = null;
    }, 1600);
  };

  const handleAnalyzeSelect = (payload: { type: 'recommend' | 'custom'; title: string; prompt?: string }) => {
    emit('analyze');
    void payload;
    startGenerate([
      { id: `analyze-${Date.now()}`, type: 'analyze', title: '智能分析报告' },
      { id: `stats-${Date.now()}`, type: 'statistics', title: '数据统计报告' },
    ]);
  };

  const handleStatistics = () => {
    statisticsDialogShow.value = true;
  };

  const handleStatisticsConfirm = (payload: { fields: string[]; customPrompt?: string }) => {
    emit('statistics');
    void payload.customPrompt;
    startGenerate(
      [{ id: `stats-${Date.now()}`, type: 'statistics', title: '数据统计报告' }],
      { openStatistics: true, fields: payload.fields },
    );
  };

  const openReport = (item: ReportStatusItem | LogReportInfo) => {
    if (item.type === 'statistics') {
      statisticsFields.value = statisticsFields.value.length ? statisticsFields.value : [];
      statisticsCreatedAt.value = ('createdAt' in item && item.createdAt) ? item.createdAt : formatNow();
      statisticsDrawerShow.value = true;
      return;
    }
    activeReport.value = {
      id: item.id,
      type: item.type,
      title: item.title,
      createdAt: 'createdAt' in item ? item.createdAt : formatNow(),
    };
    reportDrawerShow.value = true;
  };

  const handleCopy = async () => {
    const text = [
      props.result.title,
      `共命中 ${props.result.totalHit} 条`,
      ...props.result.conditions.map(item => `${item.field}：${item.value}`),
    ].join('\n');
    try {
      await navigator.clipboard.writeText(text);
      messageSuccess('已复制');
    } catch {
      // ignore
    }
  };
</script>

<style lang="postcss" scoped>
  .retrieval-result-wrap {
    display: flex;
    width: 900px;
    max-width: 100%;
    flex-direction: column;

    &.is-embedded {
      width: 100%;
    }
  }

  .retrieval-result-card {
    width: 100%;
    padding: 20px 24px 24px;
    font-size: 14px;
    line-height: 22px;
    color: #63656e;
    background: #fff;
    border-radius: 16px;
    box-shadow: 0 12px 32px 0 rgb(0 0 0 / 4%);
    box-sizing: border-box;

    &.is-embedded {
      padding: 0;
      background: transparent;
      border: none;
      border-radius: 0;
      box-shadow: none;
    }
  }

  .condition-section {
    margin-bottom: 16px;
  }

  .condition-header {
    display: flex;
    margin-bottom: 12px;
    font-size: 14px;
    line-height: 22px;
    color: #313238;
    align-items: center;
    gap: 8px;

    .condition-icon {
      font-size: 18px;
      color: #979ba5;
    }
  }

  .condition-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .condition-tag {
    display: inline-flex;
    height: 32px;
    padding: 0 12px;
    font-size: 12px;
    line-height: 30px;
    color: #63656e;
    background: #f0f1f5;
    border: 1px solid #dcdee5;
    border-radius: 2px;
    align-items: center;
    box-sizing: border-box;

    .tag-value {
      font-weight: 700;
      color: #313238;
    }
  }

  .process-section {
    margin-bottom: 20px;
  }

  .process-row {
    display: flex;
    height: 28px;
    font-size: 12px;
    line-height: 28px;
    color: #979ba5;
    cursor: pointer;
    align-items: center;
    gap: 4px;
    user-select: none;

    &:hover {
      color: #63656e;
    }

    .process-arrow {
      font-size: 14px;
      transition: transform .2s;

      &.is-collapsed {
        transform: rotate(-90deg);
      }
    }
  }

  .process-detail {
    padding: 4px 0 8px 18px;
    font-size: 12px;
    line-height: 20px;
    color: #c4c6cc;
  }

  .summary-section {
    display: flex;
    margin-bottom: 16px;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
  }

  .summary-main {
    min-width: 0;
    flex: 1;
  }

  .summary-title {
    margin: 0 0 19px;
    font-size: 20px;
    font-weight: 700;
    line-height: 24px;
    color: #313238;
  }

  .summary-desc {
    margin: 0;
    font-size: 12px;
    line-height: 22px;
    color: #63656e;

    .summary-num {
      font-weight: 700;
      color: #313238;
    }
  }

  .export-dropdown {
    flex-shrink: 0;
  }

  .export-btn {
    height: 32px;
    padding: 0 12px;
    color: #63656e;
    background: #fff;
    border-color: #dcdee5;

    &:hover {
      color: #3a84ff;
      border-color: #3a84ff;
    }

    .export-icon {
      margin-right: 4px;
      font-size: 14px;
    }
  }

  .table-section {
    margin-bottom: 20px;
    overflow: hidden;
  }

  .table-scroll {
    width: 100%;
    overflow: auto;
    scrollbar-width: thin;
    scrollbar-color: #dcdee5 transparent;

    &::-webkit-scrollbar {
      height: 4px;
      width: 4px;
    }

    &::-webkit-scrollbar-thumb {
      background: #dcdee5;
      border-radius: 2px;
    }
  }

  .result-table {
    width: 100%;
    min-width: 760px;
    border-collapse: collapse;
    table-layout: fixed;

    th,
    td {
      height: 42px;
      padding: 0 12px;
      overflow: hidden;
      font-size: 12px;
      line-height: 42px;
      color: #63656e;
      text-align: left;
      text-overflow: ellipsis;
      white-space: nowrap;
      border: none;
      box-sizing: border-box;
    }

    th {
      font-weight: 400;
      color: #313238;
      background: #fafbfd;
      border-bottom: 1px solid #dcdee5;
    }

    td {
      background: #fff;
    }

    tbody tr:nth-child(even) td {
      background: #fafbfd;
    }
  }

  .table-pagination {
    display: flex;
    padding: 8px 12px;
    background: #fff;
    border-top: 1px solid #dcdee5;
    align-items: center;
    justify-content: flex-end;
  }

  .action-section {
    display: flex;
    margin-bottom: 0;
    gap: 12px;
  }

  .analyze-btn {
    color: #7b29ff;
    border-color: #7b29ff;

    &:not(.is-disabled, [disabled]):hover {
      color: #9b5cff;
      border-color: #9b5cff;
    }

    .ai-agent-ai {
      margin-right: 4px;
    }
  }

  .statistics-btn {
    color: #63656e;
    border-color: #dcdee5;

    .action-icon {
      margin-right: 4px;
      font-size: 16px;
    }

    &:hover {
      color: #3a84ff;
      border-color: #3a84ff;
    }
  }

  .report-status-section {
    margin-top: 16px;

    &.is-done {
      padding: 8px 12px;
      background: #f5f7fa;
      border-radius: 2px;
    }
  }

  .report-status-row {
    display: flex;
    min-height: 32px;
    align-items: center;
    gap: 8px;

    & + .report-status-row {
      margin-top: 4px;
    }

    .status-icon {
      font-size: 16px;
      flex-shrink: 0;

      &.is-loading {
        color: #3a84ff;
        animation: log-report-spin 1s linear infinite;
      }

      &.is-success {
        color: #2dcb56;
      }
    }

    .status-text {
      font-size: 12px;
      line-height: 20px;
      color: #63656e;
    }

    .status-time {
      margin-left: 8px;
      font-size: 12px;
      color: #979ba5;
    }

    .view-report-btn {
      display: inline-flex;
      margin-left: auto;
      padding: 0;
      font-size: 12px;
      line-height: 20px;
      color: #3a84ff;
      cursor: pointer;
      background: none;
      border: none;
      align-items: center;
      gap: 4px;

      .view-icon {
        font-size: 14px;
      }

      &:hover {
        color: #699df4;
      }
    }
  }

  @keyframes log-report-spin {
    from {
      transform: rotate(0deg);
    }

    to {
      transform: rotate(360deg);
    }
  }

  .feedback-row {
    display: flex;
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid #dcdee5;
    align-items: center;
    gap: 8px;
  }

  .feedback-btn {
    display: inline-flex;
    width: 28px;
    height: 28px;
    font-size: 16px;
    color: #c4c6cc;
    cursor: pointer;
    background: transparent;
    border: none;
    border-radius: 2px;
    align-items: center;
    justify-content: center;

    .feedback-svg {
      display: block;
    }

    &:hover,
    &.is-active {
      color: #3a84ff;
      background: #f0f5ff;
    }
  }
</style>
