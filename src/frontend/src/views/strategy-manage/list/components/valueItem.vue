<template>
  <template v-if="item && item.length">
    <div
      v-for="(config, configIndex) in item"
      :key="configIndex"
      class="table-row">
      <template
        v-for="(value, valueKey) in config"
        :key="valueKey">
        <div
          v-if="!excludeKey.includes(valueKey)"
          class="cell"
          :class="getCellClass(valueKey)">
          <div v-if="typeof value === 'boolean'">
            {{ value ? t('是') : t('否') }}
          </div>
          <div
            v-else-if="typeof value === 'object' &&
              value !== null &&
              'source_field' in value &&
              'target_value' in value">
            <tooltips
              v-if="value.source_field"
              :data="value.source_field" />
            <tooltips
              v-if="value.target_value"
              :data="value.target_value" />
          </div>
          <div
            v-else-if="typeof value === 'object' &&
              value !== null &&
              'tool' in value &&
              'config' in value">
            <tooltips
              :data="getToolName(value.tool.uid)" />
          </div>
          <div v-else>
            <tooltips
              v-if="value"
              :data="value" />
          </div>
        </div>
      </template>
    </div>
  </template>
  <div
    v-else
    class="value-item">
    <div
      class="item"
      style="color: #979ba5; text-align: center;">
      {{ t('暂无数据') }}
    </div>
  </div>
</template>

<script setup lang='ts'>
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type StrategyModel from '@model/strategy/strategy';
  import StrategyFieldEvent from '@model/strategy/strategy-field-event';
  import type ToolDetailModel from '@model/tool/tool-detail';

  import Tooltips from '@components/show-tooltips-text/index.vue';

  interface Props {
    item: StrategyFieldEvent['event_basic_field_configs'],
    data: StrategyModel,
    allToolsData: Array<ToolDetailModel>;
  }

  const props = defineProps<Props>();

  const { t } = useI18n();

  const excludeKey = computed<Array<string>>(() => {
    const initKey = ['example', 'prefix'];
    if (props.data.strategy_type === 'model') {
      initKey.push('map_config');
    }
    return initKey;
  });

  const getToolName = (uid: string) => {
    const tool = props.allToolsData.find(item => item.uid === uid);
    return tool ? tool.name : '';
  };

  const getCellClass = (valueKey: string) => ({
    'field-name': valueKey === 'field_name',
    'display-name': valueKey === 'display_name',
    'is-priority': valueKey === 'is_priority' || valueKey === 'is_show',
    'map-config': valueKey === 'map_config',
    'drill-config': valueKey === 'drill_config',
    description: valueKey === 'description',
  });
</script>
<style lang="postcss" scoped>
  .table-row {
    display: flex;
    height: 42px;
    line-height: 42px;

    .cell {
      padding-left: 12px;
      border-bottom: 1px solid #dcdee5;

      &.field-name {
        width: 110px;
      }

      &.display-name {
        width: 110px;
      }

      &.is-priority {
        width: 80px;
      }

      &.map-config {
        width: 120px;
      }

      &.drill-config {
        width: 120px;
      }

      &:last-child {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }
  }
</style>
