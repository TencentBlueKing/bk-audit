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
  }

  const props = defineProps<Props>();

  const rows = computed(() => buildConditionDisplayRows(
    props.where,
    operator => props.operatorMap[operator] || operator,
  ));

  const groupConnector = computed(() => (
    props.where.connector || 'and'
  ).toUpperCase());
</script>
<style scoped lang="postcss">
.rule-condition-display {
  display: flex;

  .mr4 {
    margin-right: 4px;
  }

  .mb4 {
    margin-bottom: 4px;
  }

  .condition-equation-wrap {
    position: relative;
    flex-shrink: 0;
    width: 50px;
  }

  .condition-equation {
    padding: 2px 8px;
    font-size: 12px;
    line-height: 20px;
    color: #3a84ff;
    text-align: center;
    background: #edf4ff;
    border-radius: 2px;
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
      padding: 2px 8px;
      font-size: 12px;
      line-height: 20px;
      color: #788779;
      background: #dde9de;
      border-radius: 2px;
    }

    .condition-method {
      padding: 2px 8px;
      font-size: 12px;
      line-height: 20px;
      color: #fe9c00;
      background: #fff1db;
      border-radius: 2px;
    }

    .condition-value {
      padding: 2px 8px;
      font-size: 12px;
      line-height: 20px;
      color: #63656e;
      background: #f0f1f5;
      border-radius: 2px;
    }
  }
}
</style>
