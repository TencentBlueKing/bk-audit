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
              v-if="requiredField.includes(config.field_name) && !config.prefix"
              ref="selectVerifyRef"
              :default-value="config.map_config.source_field"
              style="width: 100%;"
              theme="background">
              <bk-select
                v-model="config.map_config.source_field"
                @select="(value: string) => handlerSelect(value, config)">
                <bk-option
                  v-for="(selectItem, index) in localSelect"
                  :key="index"
                  :label="selectItem.display_name"
                  :value="selectItem.display_name" />
                <template #extension>
                  <div
                    v-if="!showAddCount"
                    style=" color: #63656e;text-align: center;flex: 1; cursor: pointer;"
                    @click="() => showAddCount = true">
                    <audit-icon
                      style=" margin-right: 5px;font-size: 14px;color: #979ba5;"
                      type="plus-circle" />
                    <span>{{ t('自定义常量') }}</span>
                  </div>
                  <div
                    v-else
                    style="
                      display: flex;
                      width: 100%;
                      padding: 0 5px;
                      align-items: center;
                    ">
                    <bk-input
                      v-model="countValue"
                      autofocus
                      :placeholder="t('请输入')"
                      @enter="confirmAddCount" />
                    <audit-icon
                      style=" padding: 0 5px;font-size: 15px; color: #2caf5e;cursor: pointer;"
                      type="check-line"
                      @click="confirmAddCount" />
                    <audit-icon
                      style="font-size: 15px; color: #c4c6cc; cursor: pointer;"
                      type="close"
                      @click="() => showAddCount = false" />
                  </div>
                </template>
              </bk-select>
            </select-verify>
            <!-- 选填 -->
            <bk-select
              v-else-if="optionalField.includes(config.field_name) && !config.prefix"
              v-model="config.map_config.source_field"
              style="width: 100%;"
              @select="(value: string) => handlerSelect(value, config)">
              <bk-option
                v-for="(selectItem, index) in localSelect"
                :key="index"
                :label="selectItem.display_name"
                :value="selectItem.display_name" />
              <template #extension>
                <div
                  v-if="!showAddCount"
                  style=" color: #63656e;text-align: center;flex: 1; cursor: pointer;"
                  @click="() => showAddCount = true">
                  <audit-icon
                    style=" margin-right: 5px;font-size: 14px;color: #979ba5;"
                    type="plus-circle" />
                  <span>{{ t('自定义常量') }}</span>
                </div>
                <div
                  v-else
                  style="
                      display: flex;
                      width: 100%;
                      padding: 0 5px;
                      align-items: center;
                    ">
                  <bk-input
                    v-model="countValue"
                    autofocus
                    :placeholder="t('请输入')"
                    @enter="confirmAddCount" />
                  <audit-icon
                    style=" padding: 0 5px;font-size: 15px; color: #2caf5e;cursor: pointer;"
                    type="check-line"
                    @click="confirmAddCount" />
                  <audit-icon
                    style="font-size: 15px; color: #c4c6cc; cursor: pointer;"
                    type="close"
                    @click="() => showAddCount = false" />
                </div>
              </template>
            </bk-select>
            <!-- 无需配置 -->
            <template v-else>
              <span style="padding-left: 8px;">
                {{ t('无需配置') }}
              </span>
            </template>
          </template>

          <!-- 描述 -->
          <bk-input
            v-else-if="valueKey === 'description'"
            v-model="config.description"
            behavior="simplicity"
            :maxlength="100"
            style="height: 45px;"
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
  import _ from 'lodash';
  import { computed, ref, watch } from 'vue';
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
  const showAddCount = ref(false);
  const countValue = ref('');
  const localSelect = ref<Array<DatabaseTableFieldModel>>([]);

  const requiredField = ['raw_event_id', 'event_source', 'operator'];
  const optionalField = ['event_content', 'event_type'];

  const excludeKey = computed<Array<string>>(() => {
    const initKey = ['example', 'prefix'];
    if (props.strategyType === 'model') {
      initKey.push('map_config');
    }
    return initKey;
  });

  const handlerSelect = (value: string, config: StrategyFieldEvent['event_basic_field_configs'][0]) => {
    // 如果是固定值 给target_value赋值
    const selectItem = localSelect.value.find(item => item.raw_name === value);
    if (selectItem && !selectItem.table && config.map_config) {
      // eslint-disable-next-line no-param-reassign
      config.map_config.target_value = value;
    }
  };

  const confirmAddCount = () => {
    if (_.trim(countValue.value)) {
      localSelect.value.push({
        table: '',
        raw_name: countValue.value,
        display_name: countValue.value,
        field_type: '',
        aggregate: null,
        spec_field_type: '',
        remark: '', // 备注s
      });
    }
    showAddCount.value = false;
    countValue.value = '';
  };

  watch(() => props.select, (data) => {
    localSelect.value = _.cloneDeep(data);
  }, {
    immediate: true,
  });

  watch(() => props.item, (item) => {
    // 如果有固定值没有对应select，补上
    item.forEach((config) => {
      if (config.map_config
        && config.map_config.target_value
        && !localSelect.value.some(select => select.display_name === config.map_config?.target_value)) {
        countValue.value = config.map_config.target_value;
        confirmAddCount();
      }
    });
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
