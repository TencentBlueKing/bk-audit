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
        <div class="table-scroll-x">
          <div class="field-table event-field-table">
            <div class="table-head table-head-with-group">
              <div
                class="group-cell head-group-cell"
                :style="{ width: groupColumnWidth }">
                {{ t('事件分组') }}
              </div>
              <div class="data-head-cells">
                <div
                  v-for="(column, index) in eventDataColumns"
                  :key="column.key"
                  class="header-cell"
                  :style="getColumnStyle(column, index, eventDataColumns.length)">
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
                v-if="tableData[groupKey]?.length"
                class="table-body-group">
                <div
                  class="group-cell body-group-cell"
                  :style="{ width: groupColumnWidth }">
                  {{ groupMap[groupKey] }}
                </div>
                <div class="data-body-rows">
                  <value-item
                    :all-tools-data="allToolsData"
                    :columns="eventDataColumns"
                    fill-last-column
                    :item="tableData[groupKey]" />
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

  const props = defineProps<Props>();
  const { t, locale } = useI18n();

  const groupColumnWidth = computed(() => (locale.value === 'en-US' ? '140px' : '100px'));

  const getColumnStyle = (column: TableColumn, index?: number, total?: number) => {
    if (index !== undefined && total !== undefined && index === total - 1) {
      return {
        flex: '1 1 auto',
        minWidth: column.width || '200px',
      };
    }
    const width = column.width || '100px';
    return {
      flex: `0 0 ${width}`,
      width,
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
        width: '240px',
        tips: t('在单据页，鼠标移入label，即可显示字段说明'),
      },
    ];
    return props.data.strategy_type === 'rule'
      ? columns
      : columns.filter(item => item.key !== 'map_config');
  });

  const groupMap = computed<Record<string, string>>(() => (
    props.data.strategy_type === 'rule'
      ? {
        event_basic_field_configs: t('基本信息'),
        event_data_field_configs: t('事件结果'),
      }
      : {
        event_basic_field_configs: t('基本信息'),
        event_data_field_configs: t('事件结果'),
        event_evidence_field_configs: t('事件证据'),
      }
  ));

  const eventGroupKeys = computed(() => (
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

  const hasEventFieldData = computed(() => (
    eventGroupKeys.value.some(key => (
      tableData.value[key as keyof StrategyFieldEvent]?.length
    ))
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
    padding-top: 24px;
    padding-bottom: 24px;
    background: #fff;
  }

  .detail-section-title {
    margin-bottom: 16px;
    font-size: 14px;
    font-weight: 600;
    line-height: 22px;
    color: #313238;
  }

  .detail-section-divider {
    margin: 24px 0;
    border-top: 1px solid #f0f1f5;
  }

  .table-scroll-x {
    width: 100%;
    overflow-x: auto;
  }

  .field-table {
    width: 100%;
    color: #63656e;
    border: 1px solid #dcdee5;
    border-radius: 2px;

    @mixin cell-base {
      display: flex;
      min-height: 42px;
      padding: 0 12px;
      font-size: 12px;
      border-right: 1px solid #dcdee5;
      border-bottom: 1px solid #dcdee5;
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

        font-weight: 500;
        color: #313238;
        background-color: #f5f7fa;

        &:last-child {
          border-right: none;
        }
      }
    }

    .group-cell {
      @include cell-base;

      flex-shrink: 0;
      color: #313238;
      background-color: #f5f7fa;
      justify-content: center;
    }

    .head-group-cell {
      border-right: 1px solid #dcdee5;
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

    .table-empty {
      min-height: 42px;
      font-size: 12px;
      line-height: 42px;
      color: #979ba5;
      text-align: center;
      border-bottom: 1px solid #dcdee5;
    }
  }

  :deep(.table-row) {
    display: flex;
    width: 100%;
    min-height: 42px;

    .cell {
      display: flex;
      min-height: 42px;
      padding: 0 12px;
      font-size: 12px;
      border-right: 1px solid #dcdee5;
      border-bottom: 1px solid #dcdee5;
      align-items: center;
      box-sizing: border-box;

      &:last-child {
        border-right: none;
      }
    }
  }
}
</style>
