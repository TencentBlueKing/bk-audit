<template>
  <template v-if="item && item.length">
    <div
      v-for="(config, configIndex) in item"
      :key="configIndex"
      class="table-row"
      :class="{ 'fill-last-column': fillLastColumn }">
      <div
        v-for="(column, columnIndex) in displayColumns"
        :key="column.key"
        class="cell"
        :style="getColumnStyle(column, columnIndex, displayColumns.length)">
        <template v-if="column.key === 'map_config'">
          <tooltips :data="formatMapConfig(config.map_config)" />
        </template>
        <template v-else-if="column.key === 'drill_config'">
          <template v-if="!getDrillConfigList(config.drill_config).length">
            <span class="drill-empty">{{ t('未配置') }}</span>
          </template>
          <bk-popover
            v-else
            placement="top"
            theme="black">
            <span class="drill-configured">
              {{ t('已配置') }}
              <span class="drill-count">{{ getDrillConfigList(config.drill_config).length }}</span>
              {{ t('个工具') }}
            </span>
            <template #content>
              <div
                v-for="drill in getDrillConfigList(config.drill_config)"
                :key="drill.tool?.uid">
                {{ getToolName(drill.tool?.uid || '') || drill.drill_name || '--' }}
              </div>
            </template>
          </bk-popover>
        </template>
        <template v-else-if="column.key === 'enum_mappings'">
          {{ formatEnumMappings(config.enum_mappings) }}
        </template>
        <template v-else-if="typeof config[column.key as keyof typeof config] === 'boolean'">
          {{ config[column.key as keyof typeof config] ? t('是') : t('否') }}
        </template>
        <template v-else>
          <tooltips
            v-if="getTextValue(config, column.key)"
            :data="getTextValue(config, column.key)" />
          <span v-else>--</span>
        </template>
      </div>
    </div>
  </template>
  <div
    v-else
    class="value-item">
    <div class="item empty-text">
      {{ t('暂无数据') }}
    </div>
  </div>
</template>

<script setup lang='ts'>
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyFieldEvent from '@model/strategy/strategy-field-event';
  import type ToolDetailModel from '@model/tool/tool-detail';

  import Tooltips from '@components/show-tooltips-text/index.vue';

  interface TableColumn {
    key: string;
    label?: string;
    width?: string;
    tips?: string;
  }

  interface DrillConfigItem {
    tool?: { uid: string };
    drill_name?: string;
  }

  interface Props {
    item: StrategyFieldEvent['event_basic_field_configs'],
    allToolsData: Array<ToolDetailModel>;
    columns?: Array<TableColumn>;
    riskColumns?: Array<TableColumn>;
    fillLastColumn?: boolean;
  }

  const props = defineProps<Props>();

  const { t } = useI18n();

  const displayColumns = computed(() => {
    if (props.columns?.length) {
      return props.columns.filter(column => column.key);
    }
    if (props.riskColumns?.length) {
      return props.riskColumns.filter(column => column.key);
    }
    return [];
  });

  const getColumnStyle = (column: TableColumn, index: number, total: number) => {
    if (props.fillLastColumn && index === total - 1) {
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

  const getTextValue = (config: Record<string, any>, key: string) => {
    const value = config[key];
    if (value === undefined || value === null || value === '') {
      return '';
    }
    return String(value);
  };

  const getDrillConfigList = (value?: DrillConfigItem | DrillConfigItem[]) => {
    if (!value) return [];
    return Array.isArray(value) ? value : [value];
  };

  const formatMapConfig = (value?: { source_field?: string; target_value?: string }) => {
    if (!value) return '--';
    return value.source_field || value.target_value || '--';
  };

  const formatEnumMappings = (value?: { mappings?: Array<unknown> }) => {
    if (!value?.mappings?.length) return t('未配置');
    return t('已配置');
  };

  const getToolName = (uid: string) => {
    const tool = props.allToolsData.find(item => item.uid === uid);
    return tool ? tool.name : '';
  };
</script>
<style lang="postcss" scoped>
  .table-row {
    display: flex;
    width: max-content;
    min-height: 42px;
    line-height: 22px;

    &.fill-last-column {
      width: 100%;
    }

    .cell {
      overflow: hidden;
      min-width: 0;

      &:last-child {
        max-width: none;
      }

      :deep(.show-tooltips-text) {
        width: 100%;
      }
    }
  }

  .drill-empty {
    color: #c4c6cc;
  }

  .drill-configured {
    cursor: default;

    .drill-count {
      color: #3a84ff;
    }
  }

  .value-item {
    .empty-text {
      min-height: 42px;
      font-size: 12px;
      line-height: 42px;
      color: #979ba5;
      text-align: center;
      border-bottom: 1px solid #dcdee5;
    }
  }
</style>
