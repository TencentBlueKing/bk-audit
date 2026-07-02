<template>
  <div class="report-section">
    <h3 class="report-title">
      多主机行为分析报告
    </h3>
    <div class="report-meta">
      <span>分析时间：{{ analysisTime }}</span>
      <span class="meta-divider" />
      <span>分析范围：{{ hosts.length }} 台主机</span>
      <span class="meta-divider" />
      <span>时间窗口：{{ timeRangeText }}</span>
    </div>

    <!-- 一、分析概览 -->
    <div class="report-block">
      <h4 class="block-title">
        一、分析概览
      </h4>
      <div class="overview-summary">
        <audit-icon
          class="title-icon"
          type="info-fill" />
        <span class="summary-text">
          共发现 <span class="highlight">{{ totalBehaviors }}</span> 条行为记录，
          <span class="highlight risk">{{ totalRisks }}</span> 条安全风险
        </span>
      </div>
      <primary-table
        bordered
        class="overview-table"
        :columns="overviewColumns"
        :data="overviewData"
        size="small" />
    </div>

    <!-- 二、各主机详细分析 -->
    <div class="report-block">
      <h4 class="block-title">
        二、各主机详细分析
      </h4>
      <div class="host-analysis-list">
        <div
          v-for="host in hostAnalysisList"
          :key="host.ip"
          class="host-analysis-item">
          <div class="host-analysis-header">
            <span
              class="status-badge"
              :class="host.statusClass">{{ host.status }}</span>
            <span class="host-name">{{ host.ip }}（{{ host.hostName }}）</span>
          </div>
          <p class="host-analysis-desc">
            {{ host.description }}
          </p>
        </div>
      </div>
    </div>

    <!-- 三、处置建议 -->
    <div class="report-block">
      <h4 class="block-title">
        三、处置建议
      </h4>
      <primary-table
        bordered
        class="suggestion-table"
        :columns="suggestionColumns"
        :data="suggestions"
        size="small" />
    </div>

    <!-- 引用来源 -->
    <report-source />
  </div>
</template>

<script lang="tsx" setup>
  import { computed, type VNode } from 'vue';
  import { PrimaryTable } from '@blueking/tdesign-ui';
  import ReportSource from './report-source.vue';

  const props = defineProps<{
    hosts: Array<{
      ip: string;
      hostName?: string;
      os?: string;
      abnormalCount?: number;
      riskCount?: number;
      riskLevel?: string;
      status?: string;
      statusClass?: string;
      description?: string;
    }>;
    analysisTime: string;
    timeRangeText: string;
    totalBehaviors: number;
    totalRisks: number;
    suggestions?: Array<{
      priority: string;
      suggestion: string;
      scope: string;
    }>;
  }>();

  // 分析概览表格列定义
  const overviewColumns = [
    { colKey: 'ip', title: 'IP 地址', width: 120 },
    { colKey: 'hostName', title: '主机名', width: 120 },
    { colKey: 'os', title: '操作系统', width: 120 },
    {
      colKey: 'abnormalCount',
      title: '异常行为',
      width: 100,
      cell: (_: any, { row }: { row: any }): VNode => <span class={{ 'risk-num': row.abnormalCount > 0 }}>{row.abnormalCount}</span>,
    },
    {
      colKey: 'riskCount',
      title: '风险数',
      width: 100,
      cell: (_: any, { row }: { row: any }): VNode => <span class={{ 'risk-num': row.riskCount > 0 }}>{row.riskCount}</span>,
    },
    {
      colKey: 'riskLevel',
      title: '风险等级',
      width: 100,
      cell: (_: any, { row }: { row: any }): VNode => {
        const colorMap: Record<string, string> = {
          严重: '#ea3636',
          高危: '#ff9b29',
          中危: '#feb02c',
          低危: '#3a84ff',
          安全: '#2caf5e',
        };
        const color = colorMap[row.riskLevel] || '#979ba5';
        return <bk-tag size="small" style={{ color, borderColor: color }}>{row.riskLevel}</bk-tag>;
      },
    },
  ];

  // 处置建议表格列定义
  const suggestionColumns = [
    {
      colKey: 'priority',
      title: '优先级',
      width: 80,
      cell: (_: any, { row }: { row: any }): VNode => {
        const colorMap: Record<string, string> = {
          紧急: '#ea3636',
          高: '#ff9b29',
          中: '#feb02c',
          低: '#3a84ff',
          建议: '#63656e',
        };
        const color = colorMap[row.priority] || '#63656e';
        return <bk-tag size="small" style={{ color, borderColor: color }}>{row.priority}</bk-tag>;
      },
    },
    { colKey: 'suggestion', title: '建议' },
    { colKey: 'scope', title: '范围', width: 100 },
  ];

  // 概览表格数据：从 props.hosts 映射
  const overviewData = computed(() => (props.hosts || []).map(host => ({
    ip: host.ip,
    hostName: host.hostName || `host-${host.ip.split('.').pop()}`,
    os: host.os || '--',
    abnormalCount: host.abnormalCount ?? 0,
    riskCount: host.riskCount ?? 0,
    riskLevel: host.riskLevel || '安全',
  })));

  // 主机详细分析列表：从 props.hosts 映射
  const hostAnalysisList = computed(() => (props.hosts || []).map(host => ({
    ip: host.ip,
    hostName: host.hostName || `host-${host.ip.split('.').pop()}`,
    status: host.status || (host.riskCount ? '存在风险' : '未发现异常'),
    statusClass: host.statusClass || (host.riskCount ? 'warning' : 'safe'),
    description: host.description || (host.riskCount
      ? `该主机在${props.timeRangeText}内发现 ${host.riskCount} 条安全风险，${host.abnormalCount ?? 0} 条异常行为。`
      : `该主机在${props.timeRangeText}内无异常行为记录和安全风险，运行状态正常。`),
  })));
</script>

<style lang="postcss" scoped>
.report-section {
  .report-title {
    margin: 0 0 12px;
    font-size: 16px;
    font-weight: 600;
    color: #313238;
  }

  .report-meta {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;
    font-size: 13px;
    color: #313238;

    .meta-divider {
      width: 1px;
      height: 12px;
      background: #dcdee5;
    }
  }

  .report-block {
    margin-bottom: 24px;

    .block-title {
      display: flex;
      align-items: center;
      gap: 6px;
      margin: 0 0 12px;
      font-size: 14px;
      font-weight: 600;
      color: #313238;

      .title-icon {
        font-size: 12px;
        color: #f7a931;
      }
    }

    .overview-summary {
      display: flex;
      padding: 10px 16px;
      margin-bottom: 12px;
      font-size: 13px;
      color: #63656e;
      background: #fff8e6;
      border-radius: 4px;
      align-items: center;
      gap: 8px;

      .title-icon {
        font-size: 14px;
        font-weight: 400;
        color: #f7a931;
      }

      .summary-text {
        flex: 1;
      }

      .highlight {
        font-weight: 600;
        color: #313238;
      }
    }

    .overview-table,
    .suggestion-table {
      :deep(.risk-num) {
        font-weight: 600;
        color: #ea3636;
      }
    }

    .host-analysis-list {
      .host-analysis-item {
        padding: 12px 16px;
        margin-bottom: 12px;
        background: #f5f7fa;
        border-radius: 6px;

        &:last-child {
          margin-bottom: 0;
        }

        .host-analysis-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 8px;

          .status-badge {
            display: inline-block;
            padding: 2px 8px;
            font-size: 12px;
            border-radius: 4px;

            &.safe {
              color: #1f9c43;
              background: #e5f6ea;
            }

            &.warning {
              color: #f7a931;
              background: #fff8e6;
            }

            &.danger {
              color: #ea3636;
              background: #ffebeb;
            }
          }

          .host-name {
            font-size: 14px;
            font-weight: 500;
            color: #313238;
          }
        }

        .host-analysis-desc {
          margin: 0;
          font-size: 13px;
          line-height: 1.5;
          color: #63656e;
        }
      }
    }
  }

}
</style>
