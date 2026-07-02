<template>
  <div class="host-behavior-detail-report">
    <!-- 报告标题 -->
    <h3 class="report-title">
      主机行为分析报告 — {{ hostInfo.ip }}（{{ hostInfo.name }}）
    </h3>

    <!-- 概览信息 -->
    <div class="info-section">
      <h4 class="section-title">
        概览信息
      </h4>
      <div class="info-table">
        <div class="info-row">
          <div class="info-label">
            主机
          </div>
          <div class="info-value">
            {{ hostInfo.ip }}（{{ hostInfo.name }}）
          </div>
        </div>
        <div class="info-row">
          <div class="info-label">
            操作系统
          </div>
          <div class="info-value">
            {{ hostInfo.os }}
          </div>
        </div>
        <div class="info-row">
          <div class="info-label">
            风险评分
          </div>
          <div class="info-value">
            {{ hostInfo.riskScore }} / 100
          </div>
        </div>
        <div class="info-row">
          <div class="info-label">
            风险等级
          </div>
          <div class="info-value">
            <span
              class="risk-level-tag"
              :class="getRiskLevelClass(hostInfo.riskLevel)">{{ hostInfo.riskLevel }}</span>
          </div>
        </div>
        <div class="info-row">
          <div class="info-label">
            分析时间范围
          </div>
          <div class="info-value">
            {{ hostInfo.timeRange }}
          </div>
        </div>
        <div class="info-row">
          <div class="info-label">
            异常行为数
          </div>
          <div class="info-value">
            {{ hostInfo.abnormalCount }} 条
          </div>
        </div>
        <div class="info-row">
          <div class="info-label">
            关联行为数
          </div>
          <div class="info-value">
            {{ hostInfo.relatedCount }} 条
          </div>
        </div>
      </div>
    </div>

    <!-- 关键发现 -->
    <div class="info-section">
      <h4 class="section-title">
        关键发现
      </h4>
      <div class="finding-list">
        <div
          v-for="(finding, index) in findings"
          :key="index"
          class="finding-item">
          <div class="finding-header">
            <span
              class="risk-level-tag"
              :class="getRiskLevelClass(finding.level)">{{ finding.level }}</span>
            <span class="finding-title">{{ finding.title }}</span>
          </div>
          <div
            class="finding-desc"
            v-html="finding.description" /> <!-- eslint-disable-line vue/no-v-html -->
        </div>
      </div>
    </div>

    <!-- 攻击链分析 -->
    <div class="info-section">
      <h4 class="section-title">
        攻击链分析（MITRE ATT&CK）
      </h4>
      <div class="attack-chain-mermaid">
        <!-- TODO: MermaidRenderer 组件待项目接入后启用 -->
        <!-- <MermaidRenderer :code="attackChainMermaidCode" /> -->
        <pre class="attack-chain-placeholder">{{ attackChainMermaidCode }}</pre>
      </div>
    </div>

    <!-- 异常行为时间线 -->
    <div class="info-section">
      <h4 class="section-title">
        异常行为时间线
      </h4>
      <primary-table
        cell-empty-content="--"
        :columns="timelineColumns"
        :data="timelineData"
        hover
        :pagination="false" />
    </div>

    <!-- 处置建议 -->
    <div class="info-section">
      <h4 class="section-title">
        处置建议
      </h4>
      <primary-table
        cell-empty-content="--"
        :columns="suggestionColumns"
        :data="suggestions"
        hover
        :pagination="false" />
    </div>

    <!-- 引用来源 -->
    <div class="reference-section">
      <div class="reference-title">
        引用来源
      </div>
      <div class="reference-list">
        <div
          v-for="(ref, index) in references"
          :key="index"
          class="reference-item">
          [{{ index + 1 }}] {{ ref }}
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { computed } from 'vue';
  import { PrimaryTable } from '@blueking/tdesign-ui';
  // import MermaidRenderer from '@/components/mermaid-renderer/index.vue';

  const props = defineProps<{
    hostInfo: {
      ip: string;
      name: string;
      os: string;
      riskScore: number;
      riskLevel: string;
      timeRange: string;
      abnormalCount: number;
      relatedCount: number;
    };
    findings: Array<{
      level: string;
      title: string;
      description: string;
    }>;
    attackChain: {
      rows: Array<{
        nodes: Array<{
          title: string;
          subtitle: string;
        }>;
        direction: string;
      }>;
    };
    timeline: Array<{
      time: string;
      type: string;
      detail: string;
      level: string;
    }>;
    suggestions: Array<{
      priority: string;
      priorityText: string;
      action: string;
      description: string;
    }>;
    references: string[];
  }>();

  // 将 attackChain 数据转换为 mermaid 语法
  const attackChainMermaidCode = computed(() => {
    if (!props.attackChain?.rows?.length) {
      return 'flowchart LR\n  A[暂无攻击链数据]';
    }

    const row0 = props.attackChain.rows[0];
    const row1 = props.attackChain.rows[1];

    // 第一行节点ID列表
    const row0Ids: string[] = [];
    // 第二行节点ID列表
    const row1Ids: string[] = [];

    const lines: string[] = ['flowchart TB'];

    // 第一行 subgraph
    if (row0?.nodes?.length) {
      lines.push('  subgraph r0[ ]');
      lines.push('    direction LR');
      row0.nodes.forEach((node, i) => {
        const id = `A${i}`;
        row0Ids.push(id);
        const label = node.subtitle ? `${node.title} - ${node.subtitle}` : node.title;
        lines.push(`    ${id}[${label}]`);
      });
      for (let i = 0; i < row0Ids.length - 1; i++) {
        lines.push(`    ${row0Ids[i]} --> ${row0Ids[i + 1]}`);
      }
      lines.push('  end');
    }

    // 第二行 subgraph
    if (row1?.nodes?.length) {
      lines.push('  subgraph r1[ ]');
      lines.push('    direction RL');
      row1.nodes.forEach((node, i) => {
        const id = `B${i}`;
        row1Ids.push(id);
        const label = node.subtitle ? `${node.title} - ${node.subtitle}` : node.title;
        lines.push(`    ${id}[${label}]`);
      });
      // RL 方向：箭头从右到左，数据顺序 命令控制→发现→防御规避
      for (let i = 0; i < row1Ids.length - 1; i++) {
        lines.push(`    ${row1Ids[i]} --> ${row1Ids[i + 1]}`);
      }
      lines.push('  end');
    }

    // 行间连接：凭证访问(第一行最右) --> 命令控制(第二行最右，RL方向第一个定义的节点)
    if (row0Ids.length && row1Ids.length) {
      lines.push(`  ${row0Ids[row0Ids.length - 1]} --> ${row1Ids[0]}`);
    }

    // 隐藏 subgraph 边框
    lines.push('  style r0 fill:none,stroke:none');
    lines.push('  style r1 fill:none,stroke:none');

    return lines.join('\n');
  });

  const getRiskLevelClass = (level: string) => {
    const map: Record<string, string> = {
      严重: 'risk-level-serious',
      高危: 'risk-level-high',
      中危: 'risk-level-medium',
      低危: 'risk-level-low',
    };
    return map[level] || '';
  };

  // 时间线表格列
  const timelineColumns = [
    {
      colKey: 'time',
      title: '时间',
      width: 100,
    },
    {
      colKey: 'type',
      title: '行为类型',
      width: 120,
    },
    {
      colKey: 'detail',
      title: '详情',
      width: 'auto',
    },
    {
      colKey: 'level',
      title: '等级',
      width: 80,
      cell: (h: any, { row }: { row: any }) => h('span', {
        class: ['risk-level-tag', getRiskLevelClass(row.level)],
      }, row.level),
    },
  ];

  const timelineData = computed(() => props.timeline || []);

  // 处置建议表格列
  const suggestionColumns = [
    {
      colKey: 'priority',
      title: '优先级',
      width: 100,
      cell: (h: any, { row }: { row: any }) => h('span', {
        class: ['priority-tag', `priority-${row.priority}`],
      }, row.priorityText),
    },
    {
      colKey: 'action',
      title: '动作',
      width: 150,
    },
    {
      colKey: 'description',
      title: '说明',
      width: 'auto',
    },
  ];
</script>

<style lang="postcss" scoped>
.host-behavior-detail-report {
  .report-title {
    margin: 0 0 16px;
    font-size: 20px;
    font-weight: 600;
    color: #313238;
  }

  .info-section {
    margin-bottom: 24px;

    .section-title {
      margin: 0 0 12px;
      font-size: 14px;
      font-weight: 600;
      color: #313238;
    }
  }

  /* 概览信息表格 */
  .info-table {
    overflow: hidden;
    border: 1px solid #dcdee5;
    border-radius: 4px;

    .info-row {
      display: flex;
      border-bottom: 1px solid #dcdee5;

      &:last-child {
        border-bottom: none;
      }

      .info-label {
        width: 120px;
        padding: 10px 16px;
        font-size: 13px;
        color: #63656e;
        background: #fafbfd;
        border-right: 1px solid #dcdee5;
        flex-shrink: 0;
      }

      .info-value {
        padding: 10px 16px;
        font-size: 13px;
        color: #313238;
        flex: 1;
      }
    }
  }

  /* 关键发现 */
  .finding-list {
    .finding-item {
      padding: 12px 16px;
      margin-bottom: 12px;
      background: #f5f7fa;
      border-radius: 4px;

      &:last-child {
        margin-bottom: 0;
      }

      .finding-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;

        .finding-title {
          font-size: 13px;
          font-weight: 600;
          color: #313238;
        }
      }

      .finding-desc {
        font-size: 12px;
        line-height: 1.6;
        color: #4d4f56;

        :deep(strong) {
          font-weight: 600;
          color: #313238;
        }
      }
    }
  }

  /* 攻击链 mermaid 容器 */
  .attack-chain-mermaid {
    min-height: 200px;
    padding: 16px;
    overflow: auto;
    background: #f5f7fa;
    border-radius: 4px;

    .attack-chain-placeholder {
      margin: 0;
      font-family: SFMono-Regular, Consolas, monospace;
      font-size: 12px;
      line-height: 1.6;
      color: #63656e;
      word-break: break-all;
      white-space: pre-wrap;
    }
  }

  /* 引用来源 */
  .reference-section {
    padding-top: 16px;
    margin-top: 24px;
    border-top: 1px solid #dcdee5;

    .reference-title {
      margin-bottom: 8px;
      font-size: 13px;
      font-weight: 600;
      color: #313238;
    }

    .reference-list {
      .reference-item {
        margin-bottom: 4px;
        font-size: 12px;
        color: #63656e;

        &:last-child {
          margin-bottom: 0;
        }
      }
    }
  }

  /* 风险等级标签 */
  .risk-level-tag {
    display: inline-block;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 500;
    border-radius: 2px;
  }

  .risk-level-serious {
    color: #fff;
    background: #ea3636;
  }

  .risk-level-high {
    color: #ff9b29;
    background: #fff2e5;
  }

  .risk-level-medium {
    color: #feb02c;
    background: #fffbe6;
  }

  .risk-level-low {
    color: #3b84ff;
    background: #e6f7ff;
  }

  /* 优先级标签 */
  .priority-tag {
    display: inline-block;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 500;
    border-radius: 2px;
  }

  .priority-critical {
    color: #fff;
    background: #ea3636;
  }

  .priority-high {
    color: #fff;
    background: #ff9b29;
  }

  .priority-medium {
    color: #fff;
    background: #feb02c;
  }

  .priority-low {
    color: #fff;
    background: #3b84ff;
  }

  /* PrimaryTable 样式穿透 */
  :deep(.t-table) {
    border: 1px solid #dcdee5;
    border-radius: 4px;

    th {
      font-size: 13px;
      font-weight: 600;
      color: #313238;
      background: #fafbfd !important;
    }

    td {
      font-size: 13px;
      color: #63656e;

      /* 单元格内的标签样式 */
      .risk-level-tag {
        display: inline-block;
        padding: 2px 8px;
        font-size: 12px;
        font-weight: 500;
        border-radius: 2px;
      }

      .priority-tag {
        display: inline-block;
        padding: 2px 8px;
        font-size: 12px;
        font-weight: 500;
        border-radius: 2px;
      }
    }
  }

  /* 表格内的风险等级标签样式 */
  :deep(.t-table) td .risk-level-serious {
    color: #fff;
    background: #ea3636;
  }

  :deep(.t-table) td .risk-level-high {
    color: #ff9b29;
    background: #fff2e5;
  }

  :deep(.t-table) td .risk-level-medium {
    color: #feb02c;
    background: #fffbe6;
  }

  :deep(.t-table) td .risk-level-low {
    color: #3b84ff;
    background: #e6f7ff;
  }

  /* 表格内的优先级标签样式 */
  :deep(.t-table) td .priority-critical {
    color: #fff;
    background: #ea3636;
  }

  :deep(.t-table) td .priority-high {
    color: #fff;
    background: #ff9b29;
  }

  :deep(.t-table) td .priority-medium {
    color: #fff;
    background: #feb02c;
  }

  :deep(.t-table) td .priority-low {
    color: #fff;
    background: #3b84ff;
  }
}
</style>
