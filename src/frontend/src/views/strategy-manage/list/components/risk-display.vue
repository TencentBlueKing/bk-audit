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
  <div class="risk-display">
    <collapse-panel
      class="collapse-card-title"
      :label="t('风险单信息')"
      style="margin-top: 14px;">
      <render-info-block class="mt16">
        <render-info-item :label="t('风险单标题')">
          {{ data.risk_title || '--' }}
        </render-info-item>
      </render-info-block>
    </collapse-panel>
    <collapse-panel
      class="collapse-card-title"
      :label="t('事件信息')"
      style="margin-top: 24px;">
      <render-info-block class="mt16">
        <render-info-item :label="t('事件信息')">
          <div class="event-table">
            <div class="head">
              <div
                v-for="(item, index) in column"
                :key="index"
                class="item"
                :style="{
                  minWidth: (locale === 'en-US' && index === 0) ? '140px' : '80px',
                  borderRight: index === 0 ? '1px solid #dcdee5' : ''
                }">
                {{ item }}
              </div>
            </div>
            <template
              v-for="(item, key) in tableData"
              :key="key">
              <div
                v-if="!(key === 'event_evidence_field_configs' && data.strategy_type !== 'model')"
                class="body">
                <div
                  class="group"
                  :style="{minWidth: locale === 'en-US' ? '140px' : '80px'}">
                  <span> {{
                    data.strategy_type === 'model' && key === 'event_evidence_field_configs'
                      ? (groupMap as GroupMapModel).event_evidence_field_configs
                      : groupMap[key as keyof GroupMapBase]
                  }} </span>
                </div>
                <div class="value-row">
                  <value-item
                    :data="data"
                    :item="item" />
                </div>
              </div>
            </template>
          </div>
        </render-info-item>
      </render-info-block>
    </collapse-panel>
  </div>
</template>
<script setup lang="ts">
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type StrategyModel from '@model/strategy/strategy';
  import StrategyFieldEvent from '@model/strategy/strategy-field-event';

  import collapsePanel from './collapse-panel.vue';
  import RenderInfoBlock from './render-info-block.vue';
  import RenderInfoItem from './render-info-item.vue';
  import ValueItem from './valueItem.vue';

  type GroupMapBase = {
    event_basic_field_configs: string;
    event_data_field_configs: string;
  };

  type GroupMapModel = GroupMapBase & {
    event_evidence_field_configs: string;
  };

  interface Props {
    data: StrategyModel,
  }

  const props = defineProps<Props>();
  const { t, locale } = useI18n();

  const column = computed(() => {
    const initColumn = [t('事件分组'), t('字段名称'), t('字段显示名'), t('重点展示'), t('字段映射'), t('字段说明')];
    props.data.strategy_type === 'rule' ? initColumn : initColumn.splice(4, 1);
    return initColumn;
  });

  const groupMap = computed<GroupMapBase | GroupMapModel>(() => {
    const baseMap: GroupMapBase = {
      event_basic_field_configs: t('基本信息'),
      event_data_field_configs: t('事件结果'),
    };

    if (props.data.strategy_type === 'model') {
      const modelMap: GroupMapModel = {
        ...baseMap,
        event_evidence_field_configs: t('事件证据'),
      };
      return modelMap;
    }
    return baseMap;
  });

  const tableData = computed(() => {
    const data = {
      event_basic_field_configs: props.data.event_basic_field_configs,
      event_data_field_configs: props.data.event_data_field_configs,
      event_evidence_field_configs: props.data.event_evidence_field_configs,
    };
    return new StrategyFieldEvent(data);
  });
</script>
<style lang="postcss">
.risk-display {
  .event-table {
    @mixin item-styles {
      padding: 0 12px;
      border-bottom: 1px solid #dcdee5;
    }

    display: flex;
    margin-bottom: 10px;
    color: #63656e;
    border-top: 1px solid #dcdee5;
    border-right: 1px solid #dcdee5;
    border-left: 1px solid #dcdee5;
    flex-direction: column;

    .head {
      display: flex;
      height: 42px;
      line-height: 42px;
      background-color: #f5f7fa;

      .item {
        @include  item-styles;

        &:nth-child(2),
        &:nth-child(3) {
          width: 150px;
        }

        &:nth-child(4) {
          width: 100px;
        }

        &:nth-child(5) {
          width: 150px;
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
        border-right: 1px solid #dcdee5;
        align-items: center;
        justify-content: center;
      }

      .value-row {
        width: calc(100% - 80px);
      }
    }
  }
}
</style>
