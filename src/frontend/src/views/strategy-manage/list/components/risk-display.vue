<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<template>
  <div class="risk-display">
    <div class="detail-info-card">
      <div class="detail-section">
        <div class="detail-section-title">
          {{ t('风险字段配置') }}
        </div>
        <div class="table-scroll-x">
          <div class="field-table">
            <div class="table-head risk-table-head">
              <div
                v-for="(column, index) in riskColumns"
                :key="column.key"
                class="header-cell"
                :style="getColumnStyle(column, index, riskColumns.length)">
                <span
                  v-bk-tooltips="{
                    disabled: !column.tips,
                    content: column.tips,
                  }"
                  :class="{ tips: column.tips }">
                  {{ column.label }}
                </span>
              </div>
            </div>
            <value-item
              :all-tools-data="allToolsData"
              :columns="riskColumns"
              fill-last-column
              :item="tableData.risk_meta_field_config" />
          </div>
        </div>
      </div>

      <div class="detail-section-divider" />

      <div class="detail-section">
        <div class="detail-section-title">
          {{ t('事件字段配置') }}
        </div>
        <div class="table-scroll-x is-fit">
          <div class="field-table event-field-table">
            <div class="table-head table-head-with-group">
              <div
                class="group-cell head-group-cell"
                :style="groupColumnStyle">
                {{ t('事件分组') }}
              </div>
              <div class="data-head-cells">
                <div
                  v-for="column in eventDataColumns"
                  :key="column.key"
                  class="header-cell"
                  :style="getEventColumnStyle(column)">
                  <span
                    v-bk-tooltips="{
                      disabled: !column.tips,
                      content: column.tips,
                    }"
                    :class="{ tips: column.tips }">
                    {{ column.label }}
                  </span>
                </div>
              </div>
            </div>
            <template
              v-for="groupKey in eventGroupKeys"
              :key="groupKey">
              <div
                v-if="getEventGroupRows(groupKey)?.length"
                class="table-body-group">
                <div
                  class="group-cell body-group-cell"
                  :style="groupColumnStyle">
                  {{ groupMap[groupKey] }}
                </div>
                <div class="data-body-rows">
                  <value-item
                    :all-tools-data="allToolsData"
                    :columns="eventDataColumns"
                    lock-column-width
                    :item="getEventGroupRows(groupKey)" />
                </div>
              </div>
            </template>
            <div
              v-if="!hasEventFieldData"
              class="table-empty">
              {{ t('暂无数据') }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed, onMounted } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ToolManageService from '@service/tool-manage';

  import type StrategyModel from '@model/strategy/strategy';
  import StrategyFieldEvent from '@model/strategy/strategy-field-event';

  import ValueItem from './valueItem.vue';

  import useRequest from '@/hooks/use-request';

  interface Props {
    data: StrategyModel,
  }

  interface TableColumn {
    key: string;
    label: string;
    width?: string;
    tips?: string;
  }

  type EventGroupKey = 'event_basic_field_configs' | 'event_data_field_configs' | 'event_evidence_field_configs';

  const props = defineProps<Props>();
  const { t, locale } = useI18n();

  const groupColumnWidth = computed(() => (locale.value === 'en-US' ? '140px' : '76px'));
  const groupColumnStyle = computed(() => ({
    width: groupColumnWidth.value,
    flex: `0 0 ${groupColumnWidth.value}`,
  }));

  const getColumnStyle = (_column?: TableColumn, _index?: number, _total?: number) => ({
    flex: '1 1 0',
    minWidth: '88px',
  });

  const getEventColumnStyle = (column: TableColumn) => {
    if (column.key === 'description') {
      return {
        flex: '1 1 auto',
        width: 'auto',
        minWidth: '0',
        maxWidth: 'none',
      };
    }
    const width = column.width || '88px';
    return {
      flex: `0 0 ${width}`,
      width,
      minWidth: width,
      maxWidth: width,
    };
  };

  const riskColumns = computed<TableColumn[]>(() => [
    { key: 'field_name', label: t('字段名称'), width: '250px' },
    { key: 'display_name', label: t('字段显示名'), width: '250px' },
    {
      key: 'is_priority',
      label: t('重点展示'),
      width: '200px',
      tips: t('设为重点展示的字段将在风险单据中直接显示，其他字段将被折叠收起'),
    },
    {
      key: 'drill_config',
      label: t('字段下钻'),
      width: '250px',
      tips: t('为字段配置下钻工具后，可以在风险单据中点击该字段，查询其关联信息'),
    },
  ]);

  const eventDataColumns = computed<TableColumn[]>(() => {
    const columns: TableColumn[] = [
      { key: 'field_name', label: t('字段名称'), width: '130px' },
      { key: 'display_name', label: t('字段显示名'), width: '130px' },
      { key: 'is_show', label: t('在单据中展示'), width: '110px' },
      {
        key: 'is_priority',
        label: t('重点展示'),
        width: '90px',
        tips: t('设为重点展示的字段将在风险单据中直接显示，其他字段将被折叠收起'),
      },
      {
        key: 'duplicate_field',
        label: t('去重字段'),
        width: '90px',
        tips: t('同一风险单据内，当所有启用的去重字段值与历史事件匹配时，使用新事件替换历史事件'),
      },
      {
        key: 'map_config',
        label: t('字段关联'),
        width: '110px',
        tips: t('将本字段与指定字段值关联'),
      },
      {
        key: 'enum_mappings',
        label: t('字段值映射'),
        width: '110px',
        tips: t('为储存值配置可读的展示文本'),
      },
      {
        key: 'drill_config',
        label: t('字段下钻'),
        width: '140px',
        tips: t('为字段配置下钻工具后，可以在风险单据中点击该字段，查询其关联信息'),
      },
      {
        key: 'description',
        label: t('字段说明'),
        tips: t('在单据页，鼠标移入label，即可显示字段说明'),
      },
    ];
    return props.data.strategy_type === 'rule'
      ? columns
      : columns.filter(item => item.key !== 'map_config');
  });

  const groupMap = computed<Record<string, string>>(() => ({
    event_basic_field_configs: t('基本信息'),
    event_data_field_configs: t('事件结果'),
    event_evidence_field_configs: t('事件证据'),
  }));

  const eventGroupKeys = computed((): EventGroupKey[] => (
    props.data.strategy_type === 'rule'
      ? ['event_basic_field_configs', 'event_data_field_configs']
      : ['event_basic_field_configs', 'event_data_field_configs', 'event_evidence_field_configs']
  ));

  const tableData = computed(() => new StrategyFieldEvent({
    event_basic_field_configs: props.data.event_basic_field_configs,
    event_data_field_configs: props.data.event_data_field_configs,
    event_evidence_field_configs: props.data.event_evidence_field_configs,
    risk_meta_field_config: props.data.risk_meta_field_config,
  }));

  const getEventGroupRows = (key: EventGroupKey) => tableData.value[key];

  const hasEventFieldData = computed(() => (
    eventGroupKeys.value.some(key => getEventGroupRows(key)?.length)
  ));

  const {
    data: allToolsData,
    run: fetchAllTools,
  } = useRequest(ToolManageService.fetchAllTools, {
    defaultValue: [],
  });

  onMounted(() => {
    fetchAllTools();
  });
</script>
<style scoped lang="postcss">
.risk-display {
  .detail-info-card {
    background: var(--audit-neutral-bg-04);
  }

  .detail-section-title {
    margin-bottom: var(--audit-space-12);
    font-size: var(--audit-font-size-base);
    font-weight: var(--audit-font-weight-bold);
    line-height: var(--audit-line-height-base);
    color: var(--audit-neutral-text-01);
  }

  .detail-section-divider {
    margin: var(--audit-space-24) 0;
    border-top: 1px solid var(--audit-neutral-bg-01);
  }

  .table-scroll-x {
    width: 100%;
    overflow-x: auto;

    &.is-fit {
      overflow-x: hidden;
    }
  }

  .field-table {
    width: 100%;
    color: var(--audit-neutral-text-02);
    border-radius: var(--audit-radius-control);

    @mixin cell-base {
      display: flex;
      min-height: 36px;
      padding: 0 var(--audit-space-12);
      font-size: var(--audit-font-size-sm);
      font-weight: var(--audit-font-weight-regular);
      line-height: var(--audit-line-height-sm);
      align-items: center;
      box-sizing: border-box;
    }

    .table-head {
      display: flex;
      width: 100%;
      background-color: #f5f7fa;

      &.risk-table-head {
        .header-cell:last-child {
          flex: 1 1 auto;
          max-width: none;
        }
      }

      &.table-head-with-group {
        .data-head-cells {
          display: flex;
          flex: 1;
          min-width: 0;

          .header-cell:last-child {
            flex: 1 1 auto;
            max-width: none;
          }
        }
      }

      .header-cell {
        @include cell-base;

        height: 36px;
        color: var(--audit-neutral-text-01);
        background-color: var(--audit-neutral-bg-03);
        border-bottom: 1px solid var(--audit-neutral-border-01);
      }
    }

    .group-cell {
      @include cell-base;

      flex-shrink: 0;
      color: var(--audit-neutral-text-01);
      background-color: var(--audit-neutral-bg-03);
      border-right: 1px solid var(--audit-neutral-border-01);
      justify-content: center;
    }

    .head-group-cell {
      height: 36px;
      background-color: var(--audit-neutral-bg-03);
      border-right: 1px solid var(--audit-neutral-border-01);
      border-bottom: 1px solid var(--audit-neutral-border-01);
    }

    .body-group-cell {
      background-color: var(--audit-neutral-bg-03);
      border-right: 1px solid var(--audit-neutral-border-01);
    }

    .table-body-group {
      display: flex;
      width: 100%;

      .body-group-cell {
        flex-shrink: 0;
        align-self: stretch;
      }

      .data-body-rows {
        flex: 1;
        min-width: 0;
      }
    }

    &.event-field-table {
      width: 100%;
      min-width: 0;

      .table-head-with-group,
      .table-body-group {
        width: 100%;
        min-width: 0;
      }

      .table-head-with-group .data-head-cells,
      .table-body-group .data-body-rows {
        flex: 1 1 auto;
        min-width: 0;
      }

      .header-cell {
        overflow: hidden;

        > span {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }

      .group-cell {
        position: sticky;
        left: 0;
        z-index: 2;
      }

      :deep(.table-row) {
        width: 100%;
        min-width: 0;
      }

      :deep(.cell) {
        overflow: hidden;
        min-width: 0;
      }

      :deep(.show-tooltips-text) {
        max-width: 100%;
      }
    }

    .table-empty {
      height: 36px;
      font-size: var(--audit-font-size-sm);
      line-height: 36px;
      color: var(--audit-neutral-text-03);
      text-align: center;
    }
  }

  :deep(.table-row) {
    display: flex;
    width: 100%;
    min-height: 36px;
    background: var(--audit-neutral-bg-04);

    .cell {
      display: flex;
      min-height: 36px;
      padding: 0 var(--audit-space-12);
      font-size: var(--audit-font-size-sm);
      font-weight: var(--audit-font-weight-regular);
      line-height: var(--audit-line-height-sm);
      color: var(--audit-neutral-text-02);
      align-items: center;
      box-sizing: border-box;
    }
  }

  .field-table > :deep(.table-row:nth-child(odd)),
  .data-body-rows :deep(.table-row:nth-child(even)) {
    background: var(--audit-neutral-bg-02);
  }
}
</style>
