<template>
  <div class="risk-card">
    <!-- 头部：风险等级 + ID + 标题 -->
    <div class="risk-card-header">
      <span
        class="risk-level-tag"
        :class="getRiskLevelClass(risk.levelText)">{{ risk.levelText }}</span>
      <span class="risk-id">{{ risk.id }}</span>
      <span class="risk-divider">—</span>
      <span class="risk-title">{{ risk.title }}</span>
    </div>

    <!-- 元信息：发现时间 | 影响资产 | 操作人 -->
    <div class="risk-meta">
      <span class="meta-item">
        <span class="meta-label">发现时间：</span>
        <span class="meta-value">{{ risk.findTime }}</span>
      </span>
      <span class="meta-divider">|</span>
      <span class="meta-item">
        <span class="meta-label">影响资产：</span>
        <span class="meta-value">{{ risk.affectedAssets }}</span>
      </span>
      <span class="meta-divider">|</span>
      <span class="meta-item">
        <span class="meta-label">操作人：</span>
        <span class="meta-value">{{ risk.operator }}</span>
      </span>
    </div>

    <!-- 风险概述 -->
    <div class="risk-section">
      <span class="section-label">风险概述：</span>
      <span class="section-content">{{ risk.description }}</span>
    </div>

    <!-- 取证详情 -->
    <div class="risk-section">
      <span class="section-label">取证详情：</span>
      <span class="section-content">{{ risk.evidence }}</span>
    </div>

    <!-- 影响分析 -->
    <div class="risk-section">
      <span class="section-label">影响分析：</span>
      <span class="section-content">{{ risk.impact }}</span>
    </div>

    <!-- 处置建议 -->
    <div class="risk-section">
      <span class="section-label">处置建议：</span>
      <div class="section-content suggestion-content">
        <div
          v-for="(suggestion, index) in risk.suggestions"
          :key="index"
          class="suggestion-item">
          {{ index + 1 }}. {{ suggestion }}
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
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

  defineProps<{
    risk: Risk;
  }>();

  const getRiskLevelClass = (levelText: string) => {
    const map: Record<string, string> = {
      严重: 'risk-level-serious',
      高危: 'risk-level-high',
      中危: 'risk-level-medium',
      低危: 'risk-level-low',
    };
    return map[levelText] || '';
  };
</script>

<style lang="postcss" scoped>
.risk-card {
  padding: 16px 20px;
  margin-bottom: 16px;
  background: #fff;
  border-radius: 4px;

  &:last-child {
    margin-bottom: 0;
  }

  /* 头部 */
  .risk-card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;

    .risk-level-tag {
      padding: 2px 10px;
      font-size: 12px;
      font-weight: 500;
    }

    .risk-level-serious {
      color: #fff;
      background: #ea3636;
    }

    .risk-level-high {
      color: #fff;
      background: #ff9b29;
    }

    .risk-level-medium {
      color: #fff;
      background: #feb02c;
    }

    .risk-level-low {
      color: #fff;
      background: #3b84ff;
    }

    .risk-id {
      font-size: 14px;
      font-weight: 600;
      color: #313238;
    }

    .risk-divider {
      font-size: 14px;
      color: #c4c6cc;
    }

    .risk-title {
      font-size: 14px;
      font-weight: 600;
      color: #313238;
    }
  }

  /* 元信息 */
  .risk-meta {
    display: flex;
    align-items: center;
    gap: 24px;
    margin-bottom: 12px;

    .meta-item {
      display: flex;
      align-items: center;
      font-size: 13px;

      .meta-label {
        color: #313238;
      }

      .meta-value {
        color: #63656e;
      }
    }

    .meta-divider {
      font-size: 12px;
      color: #dcdee5;
    }
  }

  /* 各区块 */
  .risk-section {
    display: flex;
    align-items: flex-start;
    margin-bottom: 8px;
    font-size: 13px;
    line-height: 1.6;

    &:last-child {
      margin-bottom: 0;
    }

    .section-label {
      width: 70px;
      font-weight: 600;
      color: #313238;
      flex-shrink: 0;
    }

    .section-content {
      flex: 1;
      color: #63656e;
    }

    .suggestion-content {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .suggestion-item {
      color: #63656e;
    }
  }
}
</style>
