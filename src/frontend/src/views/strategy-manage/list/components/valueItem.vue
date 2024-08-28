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
          v-if="!['example', 'prefix'].includes(valueKey)"
          class="item">
          <div v-if="typeof value === 'boolean'">
            {{ value ? t('是') : t('否') }}
          </div>
          <div
            v-else
            v-bk-tooltips="{
              disabled: value && value.length < 15,
              content: value
            }">
            {{ value }}
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
  import { useI18n } from 'vue-i18n';

  import StrategyFieldEvent from '@model/strategy/strategy-field-event';

  interface Props {
    item: StrategyFieldEvent['event_basic_field_configs'],
  }

  defineProps<Props>();

  const { t } = useI18n();

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
        width: 180px;
      }

      &:nth-child(3) {
        width: 100px;
      }

      &:last-child {
        flex: 1;

        div {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }
    }
  }
</style>
