<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<template>
  <div
    v-if="rows.length"
    class="rule-condition-display">
    <div
      v-if="rows.length > 1"
      class="condition-equation-wrap">
      <span class="condition-equation first-equation">
        {{ groupConnector }}
      </span>
    </div>
    <div class="condition-list">
      <div
        v-for="(row, index) in rows"
        :key="index"
        class="condition-item"
        :style="{ marginTop: index ? '12px' : '0' }">
        <div
          v-if="row.showInnerConnector"
          class="condition-equation mr4 mb4">
          {{ row.innerConnector }}
        </div>
        <div
          v-if="row.fieldLabel"
          class="condition-key mr4 mb4">
          {{ row.fieldLabel }}
        </div>
        <div
          v-if="row.operatorLabel"
          class="condition-method mr4 mb4">
          {{ row.operatorLabel }}
        </div>
        <div
          v-for="(value, valIndex) in row.values"
          :key="valIndex"
          class="condition-value mr4 mb4">
          {{ value }}
        </div>
      </div>
    </div>
  </div>
  <span v-else>--</span>
</template>
<script setup lang="ts">
  import { computed } from 'vue';

  import {
    buildConditionDisplayRows,
    type RuleWhereDisplay,
  } from './use-strategy-detail-rules';

  interface Props {
    where: RuleWhereDisplay;
    operatorMap: Record<string, string>;
    aggregateList?: Array<{ label?: string; value?: unknown }>;
  }

  const props = withDefaults(defineProps<Props>(), {
    aggregateList: () => [],
  });

  const rows = computed(() => buildConditionDisplayRows(
    props.where,
    operator => props.operatorMap[operator] || operator,
    props.aggregateList,
  ));

  const groupConnector = computed(() => (
    props.where.connector || 'and'
  ).toUpperCase());
</script>
<style scoped lang="postcss">
.rule-condition-display {
  display: flex;

  .mr4 {
    margin-right: var(--bk-theme-space-4);
  }

  .mb4 {
    margin-bottom: var(--bk-theme-space-4);
  }

  .condition-equation-wrap {
    position: relative;
    flex-shrink: 0;
    width: 50px;
  }

  .condition-equation {
    padding: var(--bk-theme-space-2) var(--bk-theme-space-8);
    font-size: 12px;
    line-height: 20px;
    color: var(--bk-theme-color-brand-2);
    text-align: center;background: var(--bk-theme-fill-selected);
    border-radius: var(--bk-theme-tag-radius);
  }

  .first-equation {
    position: absolute;
    top: calc(50% - 10px);
  }

  .condition-list {
    flex: 1;
    min-width: 0;
  }

  .condition-item {
    display: flex;
    flex-wrap: wrap;
    align-items: center;

    .condition-key {
      height: 22px;
      padding: 0 var(--bk-theme-space-8);
      font-size: var(--bk-theme-font-size-sm);
      line-height: 22px;
      color: #326746;background: var(--bk-theme-status-success-bg);
      border-radius: var(--bk-theme-tag-radius);
    }

    .condition-method {
      height: 22px;
      padding: 0 var(--bk-theme-space-8);
      font-size: var(--bk-theme-font-size-sm);
      line-height: 22px;
      color: var(--bk-theme-color-warn-1);
      background: var(--bk-theme-color-warn-6);
      border-radius: var(--bk-theme-tag-radius);
    }

    .condition-value {
      height: 22px;
      padding: 0 var(--bk-theme-space-8);
      font-size: var(--bk-theme-font-size-sm);
      line-height: 22px;
      color: var(--bk-theme-text-default);
      background: var(--bk-theme-surface-muted);
      border-radius: var(--bk-theme-tag-radius);
    }
  }
}
</style>
