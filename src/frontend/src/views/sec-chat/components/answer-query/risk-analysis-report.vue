<template>
  <div class="report-section">
    <h3 class="report-title">
      {{ reportData.title }}
    </h3>

    <!-- 概览提示 -->
    <div class="overview-summary">
      <audit-icon
        class="summary-icon"
        type="info-fill" />
      <span class="summary-text">
        {{ reportData.summary.prefix }}
        <span class="highlight">{{ totalRisks }}</span>
        {{ reportData.summary.middle }}
        <span class="highlight">{{ totalHosts }}</span>
        {{ reportData.summary.suffix }}
      </span>
    </div>

    <!-- 风险概览 -->
    <div class="report-block">
      <h4 class="block-title">
        {{ reportData.riskOverview.title }}
      </h4>
      <primary-table
        bordered
        class="risk-overview-table"
        :columns="riskOverviewColumns"
        :data="riskOverviewData"
        size="small" />
    </div>

    <!-- 逐条风险解读 -->
    <div class="report-block">
      <h4 class="block-title">
        {{ reportData.riskDetail.title }}
      </h4>
      <div class="risk-cards">
        <risk-card
          v-for="risk in reportData.risks"
          :key="risk.id"
          :risk="risk" />
      </div>
    </div>

    <!-- 关联分析 -->
    <div class="report-block">
      <h4 class="block-title">
        {{ reportData.correlationAnalysis.title }}
      </h4>
      <div class="correlation-content">
        <!-- 按主机分组的风险统计 -->
        <div
          v-for="(hostGroup, index) in hostRiskGroups"
          :key="index"
          class="host-risk-group">
          <div class="host-risk-header">
            <span class="host-ip">{{ hostGroup.ip }}：</span>
            <span class="risk-count">共 {{ hostGroup.total }} 条风险</span>
            <span class="risk-stats">
              (<span class="stat-item serious">严重 {{ hostGroup.serious }}</span>
              <span class="stat-divider">/</span>
              <span class="stat-item high">高危 {{ hostGroup.high }}</span>)
            </span>
            <span class="chain-divider">|</span>
            <span class="risk-chain-label">风险链路：</span>
            <span class="risk-chain">{{ hostGroup.chain }}</span>
          </div>
        </div>
        <!-- 提示说明 -->
        <div class="analysis-tip">
          <info-line class="tip-icon" />
          <span class="tip-text">{{ reportData.correlationAnalysis.tip }}</span>
        </div>
      </div>
    </div>

    <!-- 处置建议 -->
    <div class="report-block">
      <h4 class="block-title">
        {{ reportData.suggestions.title }}
      </h4>
      <primary-table
        bordered
        class="suggestion-table"
        :columns="suggestionColumns"
        :data="reportData.suggestions.list"
        size="small" />
    </div>

    <!-- 综合建议 -->
    <div class="report-block">
      <h4 class="block-title">
        {{ reportData.comprehensiveAdvice.title }}
      </h4>
      <div class="comprehensive-advice">
        <p
          v-for="(item, index) in reportData.comprehensiveAdvice.items"
          :key="index">
          {{ item }}
        </p>
      </div>
    </div>

    <!-- 引用来源 -->
    <report-source />
  </div>
</template>

<script lang="tsx" setup>
  import { computed, type VNode } from 'vue';
  import { PrimaryTable } from '@blueking/tdesign-ui';
  import { InfoLine } from 'bkui-vue/lib/icon';
  import ReportSource from './report-source.vue';
  import RiskCard from './risk-card.vue';

  interface Risk {
    id: string;
    title: string;
    level: string;
    levelText: string;
    type: string;
    findTime: string;
    affectedAssets: string;
    operator: string;
    description: string;
    evidence: string;
    impact: string;
    suggestions: string[];
  }

  interface Suggestion {
    priority: string;
    priorityText: string;
    risk: string;
    suggestion: string;
  }

  interface ReportData {
    title: string;
    summary: {
      prefix: string;
      middle: string;
      suffix: string;
    };
    riskOverview: {
      title: string;
    };
    riskDetail: {
      title: string;
    };
    risks: Risk[];
    correlationAnalysis: {
      title: string;
      tip: string;
    };
    suggestions: {
      title: string;
      list: Suggestion[];
    };
    comprehensiveAdvice: {
      title: string;
      items: string[];
    };
  }

  const props = defineProps<{
    reportData: ReportData;
  }>();

  const totalRisks = computed(() => props.reportData.risks.length);
  const totalHosts = computed(() => new Set(props.reportData.risks.map(r => r.affectedAssets)).size);

  // 按主机分组的风险统计
  const hostRiskGroups = computed(() => {
    const groups: Record<string, { ip: string; total: number; serious: number; high: number; risks: Risk[] }> = {};

    props.reportData.risks.forEach((risk) => {
      const ip = risk.affectedAssets;
      if (!groups[ip]) {
        groups[ip] = { ip, total: 0, serious: 0, high: 0, risks: [] };
      }
      const group = groups[ip];
      group.total += 1;
      group.risks.push(risk);
      if (risk.levelText === '严重') {
        group.serious += 1;
      }
      if (risk.levelText === '高危') {
        group.high += 1;
      }
    });

    return Object.values(groups).map(group => ({
      ...group,
      chain: group.risks.map(r => r.title).join(' → '),
    }));
  });

  // 风险概览表格数据
  const riskOverviewData = computed(() => props.reportData.risks.map(risk => ({
    id: risk.id,
    level: risk.level,
    levelText: risk.levelText,
    type: risk.type,
    affectedAssets: risk.affectedAssets,
    findTime: risk.findTime,
  })));

  // 风险等级样式
  const getRiskLevelClass = (level: string) => {
    const map: Record<string, string> = {
      严重: 'risk-level-serious',
      高危: 'risk-level-high',
      中危: 'risk-level-medium',
      低危: 'risk-level-low',
    };
    return map[level] || '';
  };

  // 风险概览表格列
  const riskOverviewColumns = [
    { colKey: 'id', title: '风险 ID', width: 140 },
    {
      colKey: 'level',
      title: '风险等级',
      width: 100,
      cell: (_h: any, { row }: { row: Risk }): VNode => <span class={['risk-level-tag', getRiskLevelClass(row.levelText)]}>{row.levelText}</span>,
    },
    { colKey: 'type', title: '类型', width: 120 },
    { colKey: 'affectedAssets', title: '影响资产', width: 140 },
    { colKey: 'findTime', title: '发现时间', width: 160 },
  ];

  // 优先级样式（处置建议用 - 白字彩色底）
  const getPriorityClass = (priorityText: string) => {
    const map: Record<string, string> = {
      紧急: 'priority-serious',
      高: 'priority-high',
      中: 'priority-medium',
      低: 'priority-low',
    };
    return map[priorityText] || '';
  };

  // 处置建议表格列
  const suggestionColumns = [
    {
      colKey: 'priority',
      title: '优先级',
      width: 80,
      cell: (_h: any, { row }: { row: Suggestion }): VNode => <span class={['risk-level-tag', getPriorityClass(row.priorityText)]}>{row.priorityText}</span>,
    },
    { colKey: 'risk', title: '风险', width: 200 },
    { colKey: 'suggestion', title: '处理建议' },
  ];
</script>

<style lang="postcss" scoped>
.report-section {
  .report-title {
    margin: 0 0 12px;
    font-size: 20px;
    font-weight: 600;
    color: #313238;
  }

  .overview-summary {
    display: flex;
    padding: 10px 16px;
    margin-bottom: 20px;
    font-size: 13px;
    color: #63656e;
    background: #fff8e6;
    border-radius: 4px;
    align-items: center;
    gap: 8px;

    .summary-icon {
      font-size: 16px;
      color: #f59500;
    }

    .summary-text {
      flex: 1;
    }

    .highlight {
      font-weight: 600;
      color: #313238;
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
    }

    .risk-cards {
      .risk-card {
        padding: 16px;
        margin-bottom: 12px;
        background: #fafbfc;

        &:last-child {
          margin-bottom: 0;
        }
      }
    }

    .correlation-content {
      font-size: 13px;
      line-height: 1.6;
      color: #63656e;

      .host-risk-group {
        margin-bottom: 12px;

        &:last-child {
          margin-bottom: 0;
        }

        .host-risk-header {
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 4px;

          .host-ip {
            font-weight: 500;
            color: #313238;
          }

          .risk-count {
            color: #313238;
          }

          .risk-stats {
            color: #63656e;

            .stat-item {
              &.serious {
                color: #ea3636;
              }

              &.high {
                color: #ff9b29;
              }
            }

            .stat-divider {
              color: #c4c6cc;
            }
          }

          .chain-divider {
            margin: 0 8px;
            color: #dcdee5;
          }

          .risk-chain-label {
            color: #313238;
          }

          .risk-chain {
            color: #63656e;
          }
        }
      }

      .analysis-tip {
        display: flex;
        padding: 10px 12px;
        margin-top: 12px;
        background: #f0f8ff;
        border-radius: 4px;
        align-items: flex-start;
        gap: 8px;

        .tip-icon {
          flex-shrink: 0;
          width: 16px;
          height: 16px;
          font-size: 14px;
          color: #3a84ff;
        }

        .tip-text {
          line-height: 1.6;
          color: #63656e;
          flex: 1;
        }
      }
    }

    .comprehensive-advice {
      padding: 12px 16px;
      font-size: 13px;
      line-height: 1.8;
      color: #63656e;
      border-radius: 6px;

      p {
        margin: 0;

        &:not(:last-child) {
          margin-bottom: 4px;
        }
      }
    }
  }

  /* 穿透 PrimaryTable 子组件的样式 */
  :deep(.risk-level-tag) {
    display: inline-block;
    padding: 0 6px;
    font-size: 10px;
    font-weight: 500;
    border-radius: 2px;
  }

  :deep(.risk-level-serious) {
    color: #ea3636;
    background: #fff0f0;
  }

  :deep(.risk-level-high) {
    color: #ff9b29;
    background: #fff2e5;
  }

  :deep(.risk-level-medium) {
    color: #feb02c;
    background: #fffbe6;
  }

  :deep(.risk-level-low) {
    color: #3b84ff;
    background: #e6f7ff;
  }

  /* 处置建议优先级标签（白字彩色底） */
  :deep(.priority-serious) {
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 500;
    color: #fff;
    background: #ea3636;
    border-radius: 4px;
  }

  :deep(.priority-high) {
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 500;
    color: #fff;
    background: #ff9b29;
    border-radius: 4px;
  }

  :deep(.priority-medium) {
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 500;
    color: #fff;
    background: #feb02c;
    border-radius: 4px;
  }

  :deep(.priority-low) {
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 500;
    color: #fff;
    background: #3b84ff;
    border-radius: 4px;
  }
}
</style>
