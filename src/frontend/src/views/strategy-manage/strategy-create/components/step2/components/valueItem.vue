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
          <template v-if="valueKey === 'is_priority'">
            <bk-switcher
              v-model="config.is_priority"
              theme="primary" />
          </template>
          <template v-else-if="valueKey === 'field_mapping'">
            <bk-select v-model="config.field_mapping">
              <bk-option
                v-for="(selectItem, index) in select"
                :key="index"
                :label="selectItem.display_name"
                :value="selectItem.raw_name" />
            </bk-select>
          </template>
          <template v-else-if="valueKey === 'description'">
            <bk-input
              v-model="config.description"
              autosize
              behavior="simplicity"
              :maxlength="100"
              type="textarea" />
          </template>
          <template v-else>
            {{ value }}
          </template>
        </div>
      </template>
    </div>
  </template>
  <div
    v-else
    class="value-item"
    style="height: 100%;">
    <div
      class="item"
      style="color: #979ba5; justify-content: center;">
      {{ t('暂未获取到相关字段，请先进入下一步') }}
    </div>
  </div>
</template>

<script setup lang='ts'>
  import { useI18n } from 'vue-i18n';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';
  import StrategyFieldEvent from '@model/strategy/strategy-field-event';

  interface Props {
    item: StrategyFieldEvent['event_basic_field_configs'],
    select: Array<DatabaseTableFieldModel>
  }

  defineProps<Props>();

  const { t } = useI18n();

</script>
<style lang="postcss" scoped>
  .value-item {
    display: flex;

    .item {
      display: flex;
      padding: 12px;
      border-right: 1px solid #dcdee5;
      border-bottom: 1px solid #dcdee5;
      align-items: center;

      &:nth-child(1),
      &:nth-child(2) {
        width: 240px;
        background-color: #f5f7fa;
      }

      &:nth-child(3) {
        width: 120px;
      }

      &:nth-child(4) {
        width: 192px;
      }

      &:last-child {
        flex: 1;
      }

      :deep(.bk-textarea) {
        border: none;
      }

      :deep(.bk-input) {
        border: none;
      }
    }
  }
</style>
