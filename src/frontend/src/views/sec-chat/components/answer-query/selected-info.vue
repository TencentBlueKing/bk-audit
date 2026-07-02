<template>
  <div class="selected-info-section">
    <div class="selected-header">
      <span
        v-if="reportType === 'behavior'"
        class="check-icon">
        <audit-icon type="success" />
      </span>
      <audit-icon
        v-else
        class="check-icon"
        type="angle-line-down" />
      <!-- 回答二：主机行为分析 -->
      <span
        v-if="reportType === 'behavior'"
        class="title-text">
        已选择 {{ hosts.length }} 台主机进行分析（{{ timeRangeText }}）
      </span>
      <!-- 回答三：风险告警解读 -->
      <span
        v-else
        class="title-text">
        本次解读共涉及 {{ risks.length }} 条风险告警，影响 {{ hostCount }} 台主机
      </span>
    </div>
    <!-- 回答二：主机列表 -->
    <div
      v-if="reportType === 'behavior'"
      class="selected-hosts">
      <div
        v-for="host in hosts"
        :key="host.ip"
        class="host-item">
        <span class="host-dot" />
        <span class="host-ip">{{ host.ip }}：</span>
        <span class="host-detail">{{ host.cloudArea }}（ {{ host.topo }}）</span>
      </div>
    </div>
    <!-- 回答三：风险列表 -->
    <div
      v-else
      class="selected-risks">
      <div
        v-for="risk in risks"
        :key="risk.id"
        class="risk-item">
        <span class="risk-dot" />
        <span
          class="risk-level"
          :class="getRiskLevelClass(risk.level)">{{ risk.levelText }}</span>
        <span class="risk-name">{{ risk.name }}</span>
        <span class="risk-asset">影响资产：{{ risk.affectedAssets }}</span>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>

  withDefaults(defineProps<{
    reportType: 'behavior' | 'risk';
    hosts?: any[];
    risks?: any[];
    timeRangeText?: string;
    hostCount?: number;
  }>(), {
    hosts: () => [],
    risks: () => [],
    timeRangeText: '',
    hostCount: 0,
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
</script>

<style lang="postcss" scoped>
.selected-info-section {
  margin-top: 16px;
  margin-bottom: 16px;
  background: #fff;

  .selected-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;

    .check-icon {
      font-size: 14px;
      color: #3a84ff;
    }

    .title-text {
      font-size: 13px;
      font-weight: 600;
      color: #313238;
    }
  }

  .selected-hosts {
    padding-left: 24px;

    .host-item {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 6px;
      font-size: 12px;

      &:last-child {
        margin-bottom: 0;
      }

      .host-dot {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 12px;
        height: 12px;
        background: #e5f5eb;
        border-radius: 50%;

        &::before {
          width: 6px;
          height: 6px;
          background: #2dcb56;
          border-radius: 50%;
          content: '';
        }
      }

      .host-ip {
        color: #313238;
      }

      .host-detail {
        color: #979ba5;
      }
    }
  }

  .selected-risks {
    padding-left: 24px;

    .risk-item {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 6px;
      font-size: 12px;

      &:last-child {
        margin-bottom: 0;
      }

      .risk-dot {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 12px;
        height: 12px;
        background: #fce6e6;
        border-radius: 50%;

        &::before {
          width: 6px;
          height: 6px;
          background: #ea3636;
          border-radius: 50%;
          content: '';
        }
      }

      .risk-level {
        padding: 0 6px;
        font-size: 10px;
        font-weight: 500;
        border-radius: 2px;
      }

      .risk-level-serious {
        color: #ea3636;
        background: #fff0f0;
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

      .risk-name {
        color: #313238;
      }

      .risk-asset {
        color: #979ba5;
      }
    }
  }
}
</style>
