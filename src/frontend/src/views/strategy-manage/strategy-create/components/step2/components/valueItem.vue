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
          <!-- 是否重点展示 -->
          <bk-switcher
            v-if="valueKey === 'is_priority'"
            v-model="config.is_priority"
            theme="primary" />

          <!-- 字段映射 -->
          <template v-else-if="valueKey === 'map_config' && config.map_config">
            <!-- 必填 -->
            <select-verify
              v-if="requiredField.includes(config.field_name)"
              ref="selectVerifyRef"
              :default-value="config.map_config.source_field"
              style="width: 100%;"
              theme="background">
              <bk-select v-model="config.map_config.source_field">
                <bk-option
                  v-for="(selectItem, index) in select"
                  :key="index"
                  :label="selectItem.display_name"
                  :value="selectItem.display_name" />
              </bk-select>
            </select-verify>
            <!-- 选填 -->
            <bk-select
              v-else-if="optionalField.includes(config.field_name)"
              v-model="config.map_config.source_field"
              style="width: 100%;">
              <bk-option
                v-for="(selectItem, index) in select"
                :key="index"
                :label="selectItem.display_name"
                :value="selectItem.raw_name" />
            </bk-select>
            <!-- 无需配置 -->
            <template v-else>
              {{ t('无需配置') }}
            </template>
          </template>

          <!-- 描述 -->
          <bk-input
            v-else-if="valueKey === 'description'"
            v-model="config.description"
            autosize
            behavior="simplicity"
            :maxlength="100"
            type="textarea" />

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
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';
  import StrategyFieldEvent from '@model/strategy/strategy-field-event';

  import SelectVerify from '@views/link-data-manage/link-data-create/components/components/select-verify.vue';

  interface Exposes {
    getValue: () => Promise<any>;
  }
  interface Props {
    item: StrategyFieldEvent['event_basic_field_configs'],
    select: Array<DatabaseTableFieldModel>,
    strategyType: string
  }

  const props = defineProps<Props>();

  const { t } = useI18n();
  const selectVerifyRef = ref();

  const requiredField = ['raw_event_id', 'event_time', 'event_source', 'operator'];
  const optionalField = ['event_content', 'event_type'];

  const excludeKey = computed<Array<string>>(() => {
    const initKey = ['example', 'prefix'];
    if (props.strategyType === 'model') {
      initKey.push('map_config');
    }
    return initKey;
  });

  defineExpose<Exposes>({
    getValue() {
      if (!selectVerifyRef.value) {
        return Promise.resolve();
      }
      return Promise.all((selectVerifyRef.value as { getValue: () => any }[])?.map(item => item.getValue()));
    },
  });
</script>
<style lang="postcss" scoped>
  .value-item {
    display: flex;

    .item {
      display: flex;
      height: 58px;
      padding: 12px;
      border-right: 1px solid #dcdee5;
      border-bottom: 1px solid #dcdee5;
      align-items: center;

      &:nth-child(1) {
        width: 190px;
      }

      &:nth-child(2) {
        width: 240px;
        background-color: #f5f7fa;
      }

      &:nth-child(3) {
        width: 120px;
      }

      &:nth-child(4) {
        width: 240px;
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
