<template>
  <template v-if="item && item.length">
    <div
      v-for="(config, configIndex) in item"
      :key="configIndex"
      class="value-item">
      <template
        v-for="(value, valueKey) in config"
        :key="valueKey">
        <div
          v-if="!excludeKey.includes(valueKey)"
          class="item">
          <div v-if="typeof value === 'boolean'">
            {{ value ? t('是') : t('否') }}
          </div>
          <div v-else-if="typeof value === 'object'">
            <tooltips
              v-if="value.source_field"
              :data="value.source_field" />
            <tooltips
              v-if="value.target_value"
              :data="value.target_value" />
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

  import Tooltips from '@components/show-tooltips-text/index.vue';

  interface Props {
    item: StrategyFieldEvent['event_basic_field_configs'],
    data: StrategyModel,
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

</script>
<style lang="postcss" scoped>
  .value-item {
    display: flex;
    height: 42px;
    line-height: 42px;

    .item {
      padding-left: 12px;
      border-bottom: 1px solid #dcdee5;

      &:nth-child(1),
      &:nth-child(2) {
        width: 150px;
      }

      &:nth-child(3) {
        width: 100px;
      }

      &:nth-child(4) {
        width: 150px;
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
