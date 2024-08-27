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
  <div class="event-table">
    <div class="head">
      <div
        v-for="(item, index) in column"
        :key="index"
        class="item"
        :style="{width: (locale === 'en-US' && index === 0) ? '141px' : ''}">
        <span
          v-bk-tooltips="{
            disabled: !item.tips,
            content: item.tips
          }"
          :class="[item.tips ? 'tips' : '']">
          {{ item.label }}
        </span>
      </div>
    </div>
    <template
      v-for="(item, key, index) in tableData"
      :key="index">
      <div class="body">
        <div
          class="group"
          :style="{width: locale === 'en-US' ? '150px' : ''}">
          <span> {{ groupMap[key] }} </span>
        </div>
        <div class="value-row">
          <template v-if="item && item.length">
            <div
              v-for="(config, configIndex) in item"
              :key="configIndex"
              class="value-item">
              <template
                v-for="(value, valueKey, valueIndex) in config"
                :key="valueIndex">
                <div
                  v-if="!['example', 'prefix'].includes(valueKey)"
                  class="item">
                  <template v-if="valueKey === 'is_priority'">
                    <bk-switcher
                      v-model="config.is_priority"
                      theme="primary" />
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
        </div>
      </div>
    </template>
  </div>
</template>
<script setup lang='tsx'>
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import StrategyModel from '@model/strategy/strategy';
  import StrategyFieldEvent from '@model/strategy/strategy-field-event';

  import useRequest from '@/hooks/use-request';

  interface Exposes{
    getData: () => StrategyFieldEvent,
  }

  interface Props {
    strategyId: number,
    data: StrategyModel
  }

  const props = defineProps<Props>();

  const { t, locale } = useI18n();

  const column = [
    { label: t('事件分组') },
    { label: t('字段名称') },
    { label: t('字段显示名') },
    { label: t('重点展示'), tips: t('开启后将在单据里优先展示') },
    { label: t('字段说明'), tips: t('在单据页，鼠标移入label，即可显示字段说明') },
  ];

  const groupMap = {
    event_basic_field_configs: t('基本信息'),
    event_data_field_configs: t('事件数据'),
    event_evidence_field_configs: t('事件证据'),
  };

  const setEditData = (key: 'event_basic_field_configs' | 'event_data_field_configs' | 'event_evidence_field_configs') => {
    if (props.data[key].length && tableData.value[key].length) {
      tableData.value[key] = tableData.value[key].map((item) => {
        const editItem = props.data[key].find(edItem => edItem.field_name === item.field_name);
        if (editItem) {
          return {
            field_name: item.field_name,
            display_name: item.display_name,
            is_priority: editItem.is_priority,
            description: editItem.description,
            example: item.example,
            prefix: '',
          };
        }
        return {
          ...item,
        };
      });
    }
  };

  const {
    data: tableData,
  } = useRequest(StrategyManageService.fetchStrategyEvent, {
    defaultValue: new StrategyFieldEvent(),
    defaultParams: {
      strategy_id: props.strategyId,
    },
    onSuccess: () => {
      // 编辑填充内容（是否重点展示、字段说明）
      setEditData('event_basic_field_configs');
      setEditData('event_data_field_configs');
      setEditData('event_evidence_field_configs');
    },
    manual: true,
  });

  defineExpose<Exposes>({
    getData() {
      return tableData.value;
    },
  });
</script>
<style lang="postcss" scoped>
.event-table {
  @mixin item-styles {
    display: flex;
    padding: 12px;
    border-right: 1px solid #dcdee5;
    border-bottom: 1px solid #dcdee5;
    align-items: center;
  }

  display: flex;
  margin-bottom: 10px;
  color: #63656e;
  border-top: 1px solid #dcdee5;
  border-left: 1px solid #dcdee5;
  flex-direction: column;

  .head {
    display: flex;
    height: 42px;
    background-color: #f5f7fa;

    .item {
      @include  item-styles;

      padding-right: 0;
      background-color: #f5f7fa;

      &:first-child {
        width: 72px;
      }

      &:nth-child(2),
      &:nth-child(3) {
        width: 240px;
      }

      &:nth-child(4) {
        width: 120px;
      }

      &:last-child {
        flex: 1;
      }
    }
  }

  .body {
    display: flex;
    min-height: 42px;

    .group {
      @include  item-styles;

      display: flex;
      width: 72px;
      padding: 0;
      background-color: #f5f7fa;
      align-items: center;
      justify-content: center;
    }

    .value-row {
      width: calc(100% - 72px);

      .value-item {
        display: flex;

        .item {
          @include  item-styles;

          &:nth-child(1),
          &:nth-child(2) {
            width: 240px;
            background-color: #f5f7fa;
          }

          &:nth-child(3) {
            width: 120px;
          }

          &:last-child {
            flex: 1;
          }

          :deep(.bk-textarea) {
            border: none;
          }
        }
      }
    }
  }
}
</style>
