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
    v-if="mode === 'text'"
    v-bk-tooltips="textScopeTip"
    class="match-scope-text"
    :class="{ 'is-inline': inline }"
    @mouseenter="syncTextOverflow">
    <template v-if="textLines.length">
      <div
        v-for="(line, index) in textLines"
        :key="index"
        class="match-scope-text__line">
        <span
          v-if="line.op"
          class="match-scope-text__op">{{ line.op }}</span>
        <span class="match-scope-text__content">{{ line.text }}</span>
      </div>
    </template>
    <span v-else>--</span>
  </div>
  <div
    v-else
    class="match-scope-tag"
    :class="{ 'is-multi': showRail }">
    <div
      v-if="showRail"
      class="match-scope-tag__rail">
      <span class="match-scope-tag__group-op">{{ groupLabel }}</span>
    </div>
    <div class="match-scope-tag__rows">
      <div
        v-for="(row, index) in visibleRows"
        :key="index"
        class="match-scope-tag__row">
        <span
          v-if="row.showAnd"
          class="match-scope-tag__op">and</span>
        <span
          v-bk-tooltips="buildChipTip(row.field, `${index}-field`)"
          class="match-scope-tag__chip is-field"
          @mouseenter="(e) => syncChipOverflow(`${index}-field`, e)">{{ row.field }}</span>
        <span class="match-scope-tag__op-chip">{{ row.operator }}</span>
        <span
          v-bk-tooltips="buildChipTip(row.value, `${index}-value`)"
          class="match-scope-tag__chip is-value"
          @mouseenter="(e) => syncChipOverflow(`${index}-value`, e)">{{ row.value }}</span>
        <button
          v-if="row.showToggle"
          class="match-scope-tag__toggle"
          type="button"
          @click.stop="expanded = !expanded">
          {{ expanded ? t('收起') : t('展开') }}
          <audit-icon :type="expanded ? 'angle-line-up' : 'angle-line-down'" />
        </button>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type { CompareOperator, MatchGroup } from '@model/risk-whitelist/whitelist';

  import { FALLBACK_CONDITION_FIELDS } from './constants';

  interface Props {
    scope?: Record<string, any> | null;
    mode?: 'tag' | 'text';
    inline?: boolean;
    maxRows?: number;
  }

  interface TagRow {
    field: string;
    operator: string;
    value: string;
    showAnd: boolean;
    showToggle: boolean;
  }

  const props = withDefaults(defineProps<Props>(), {
    scope: null,
    mode: 'text',
    inline: false,
    maxRows: 2,
  });

  const { t } = useI18n();
  const expanded = ref(false);
  const textOverflowed = ref(false);
  const overflowedChipKeys = ref<Record<string, boolean>>({});

  const groups = computed<MatchGroup[]>(() => {
    const input = props.scope || {};
    const rawGroups = Array.isArray(input.groups) ? input.groups : [];
    const groupLogic = input.groupLogic || input.group_logic || 'and';
    return rawGroups.map((group: Record<string, any>, groupIndex: number) => {
      const rows = group.conditions || group.rows || [];
      const rowLogic = group.logic || 'and';
      return {
        connector: group.connector || (groupIndex === 0 ? 'and' : groupLogic),
        conditions: rows.map((row: Record<string, any>) => {
          const operator = row.operator === 'ne' ? 'neq' : (row.operator || 'eq');
          const field = row.field || '';
          const meta = FALLBACK_CONDITION_FIELDS.find(item => item.field === field);
          return {
            field,
            field_name: row.field_name || meta?.name || field,
            field_label: row.field_label || row.field_name || meta?.label || field,
            operator,
            value: row.value || '',
            value_display: row.value_display || row.value_label || row.value || '',
            connector: row.connector || rowLogic,
          };
        }),
      };
    });
  });
  const flatCount = computed(() => groups.value.reduce((count, group) => count + group.conditions.length, 0));
  const multipleGroups = computed(() => groups.value.length > 1);
  const canToggle = computed(() => multipleGroups.value && flatCount.value > props.maxRows);
  const showRail = computed(() => multipleGroups.value && (!canToggle.value || expanded.value));
  const groupLabel = computed(() => (groups.value[1]?.connector || 'and').toUpperCase());

  const operatorText = (operator: CompareOperator) => (operator === 'neq' ? '不等于' : '等于');

  const isEllipsisOverflow = (el: HTMLElement) => el.scrollWidth > el.clientWidth + 1;

  const syncChipOverflow = (key: string, event: MouseEvent) => {
    const el = event.currentTarget as HTMLElement;
    const overflowed = isEllipsisOverflow(el);
    if (overflowedChipKeys.value[key] === overflowed) return;
    overflowedChipKeys.value = {
      ...overflowedChipKeys.value,
      [key]: overflowed,
    };
  };

  const buildChipTip = (text: string, key: string) => ({
    content: text,
    disabled: !overflowedChipKeys.value[key],
    delay: 80,
    placement: 'top',
  });

  const clipGroups = (input: MatchGroup[], maxRows: number) => {
    let left = maxRows;
    const next: MatchGroup[] = [];
    input.forEach((group) => {
      if (left <= 0) return;
      const conditions = group.conditions.slice(0, left);
      next.push({
        ...group,
        conditions,
      });
      left -= conditions.length;
    });
    return next;
  };

  const visibleRows = computed<TagRow[]>(() => {
    const source = (!canToggle.value || expanded.value)
      ? groups.value
      : clipGroups(groups.value, props.maxRows);
    const rows: TagRow[] = [];
    source.forEach((group, groupIndex) => {
      group.conditions.forEach((condition, conditionIndex) => {
        rows.push({
          field: condition.field_label || condition.field,
          operator: operatorText(condition.operator),
          value: condition.value_display || condition.value || '--',
          showAnd: conditionIndex > 0,
          showToggle: false,
        });
      });
      if (groupIndex > 0 && showRail.value && rows.length) {
        const firstOfGroup = rows.length - group.conditions.length;
        if (firstOfGroup >= 0) rows[firstOfGroup].showAnd = false;
      }
    });
    if (canToggle.value && rows.length) rows[rows.length - 1].showToggle = true;
    return rows;
  });

  const textLines = computed(() => {
    const lines: Array<{ op: string; text: string }> = [];
    groups.value.forEach((group, groupIndex) => {
      group.conditions.forEach((condition, conditionIndex) => {
        const op = groupIndex === 0 && conditionIndex === 0
          ? ''
          : (conditionIndex === 0 ? group.connector : condition.connector || 'and').toUpperCase();
        const symbol = condition.operator === 'neq' ? '!=' : '=';
        const shown = condition.value_display || condition.value;
        const text = condition.field === 'strategy_id'
          ? `命中策略(ID) ${symbol} ${shown}`
          : `${condition.field_label || condition.field}${symbol}${shown}`;
        lines.push({ op, text });
      });
    });
    return lines;
  });

  const fullTextContent = computed(() => textLines.value
    .map(line => (line.op ? `${line.op} ${line.text}` : line.text))
    .join('\n'));

  const textScopeTip = computed(() => ({
    content: fullTextContent.value,
    disabled: props.inline || !textOverflowed.value || !fullTextContent.value,
    delay: 80,
    placement: 'top',
    extCls: 'match-scope-text-tip',
  }));

  const syncTextOverflow = (event: MouseEvent) => {
    if (props.inline) {
      textOverflowed.value = false;
      return;
    }
    const root = event.currentTarget as HTMLElement;
    const contents = root.querySelectorAll('.match-scope-text__content');
    textOverflowed.value = Array.from(contents).some(node => isEllipsisOverflow(node as HTMLElement));
  };
</script>
<style lang="postcss" scoped>
.match-scope-text {
  flex: 1;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  font-size: var(--bk-theme-font-size-sm);
  line-height: var(--bk-theme-line-height-sm);
  color: var(--bk-theme-text-strong);
}

.match-scope-text:not(.is-inline) .match-scope-text__line {
  display: flex;
  align-items: center;
  min-width: 0;
  overflow: hidden;
  line-height: 20px;
}

.match-scope-text.is-inline {
  display: flex;
  flex-wrap: wrap;
  gap: 0 var(--bk-theme-space-4);
  align-items: center;
}

.match-scope-text.is-inline .match-scope-text__line {
  display: inline;
}

.match-scope-text__op {
  flex-shrink: 0;
  margin-right: var(--bk-theme-space-4);
  font-weight: var(--bk-theme-font-weight-bold);
  color: var(--bk-theme-color-warn-2);
}

.match-scope-text:not(.is-inline) .match-scope-text__content {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.match-scope-tag {
  display: flex;
  gap: var(--bk-theme-space-8);
  align-items: stretch;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  overflow: visible;
}

.match-scope-tag.is-multi {
  /* 为 group-op 半宽压边留白，避免被父级裁切 */
  padding-left: calc(var(--bk-theme-space-16) + var(--bk-theme-space-4));
}

.match-scope-tag__rail {
  position: relative;
  flex-shrink: 0;
  width: 16px;
  border: 1px dashed var(--bk-theme-border-default);
  border-right: 0;
  border-radius: var(--bk-theme-tag-radius) 0 0 var(--bk-theme-tag-radius);
}

.match-scope-tag__group-op {
  position: absolute;
  top: 50%;
  left: 0;
  z-index: 1;
  padding: 0 var(--bk-theme-space-4);
  color: var(--bk-theme-color-warn-2);
  background: var(--bk-theme-surface-default);
  border: 1px solid var(--bk-theme-color-warn-2);
  border-radius: var(--bk-theme-control-radius);
  transform: translate(-50%, -50%);
}

.match-scope-tag__rows {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--bk-theme-space-4);
  min-width: 0;
  overflow: hidden;
}

.match-scope-tag__row {
  display: flex;
  flex-wrap: nowrap;
  gap: var(--bk-theme-space-4);
  align-items: center;
  min-width: 0;
  overflow: hidden;
}

.match-scope-tag__chip,
.match-scope-tag__op-chip,
.match-scope-tag__op,
.match-scope-tag__group-op {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  height: 22px;
  padding: 0 var(--bk-theme-space-4);
  font-size: var(--bk-theme-font-size-sm);
  line-height: var(--bk-theme-line-height-sm);
  border-radius: var(--bk-theme-control-radius);
}

.match-scope-tag__chip.is-field,
.match-scope-tag__chip.is-value {
  display: block;
  box-sizing: border-box;
  flex: 0 1 auto;
  max-width: 156px;
  min-width: 0;
  overflow: hidden;
  line-height: 22px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.match-scope-tag__chip.is-field {
  color: var(--bk-theme-color-success-2);
  background: var(--bk-theme-color-success-6);
}

.match-scope-tag__chip.is-value {
  color: var(--bk-theme-text-default);
  background: var(--bk-theme-surface-muted);
}

.match-scope-tag__op-chip {
  color: var(--bk-theme-color-warn-2);
  background: var(--bk-theme-color-warn-6);
}

.match-scope-tag__op {
  color: var(--bk-theme-color-warn-2);
  background: var(--bk-theme-surface-default);
  border: 1px solid var(--bk-theme-color-warn-2);
}

.match-scope-tag__toggle {
  display: inline-flex;
  flex-shrink: 0;
  gap: var(--bk-theme-space-2);
  align-items: center;
  height: 22px;
  padding: 0;
  font-size: var(--bk-theme-font-size-sm);
  color: var(--bk-theme-color-brand-2);
  cursor: pointer;
  background: transparent;
  border: 0;
}
</style>
<style lang="postcss">
/* tip 挂到 body，需非 scoped */
.match-scope-text-tip {
  max-width: 360px;
  line-height: 20px;
  word-break: break-all;
  white-space: pre-wrap;
}
</style>
