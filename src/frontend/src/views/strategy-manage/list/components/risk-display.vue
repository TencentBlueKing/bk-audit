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
                class="item">
                {{ item }}
              </div>
            </div>
            <template
              v-for="(item, key, index) in tableData"
              :key="index">
              <div class="body">
                <div class="group">
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
                          <div v-if="typeof value === 'boolean'">
                            {{ value ? '是' : '否' }}
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

  interface Props {
    data: StrategyModel,
  }

  const props = defineProps<Props>();
  const { t } = useI18n();

  const column = [t('事件分组'), t('字段名称'), t('字段显示名'), t('重点展示'), t('字段说明')];

  const groupMap = {
    event_basic_field_configs: t('基本信息'),
    event_data_field_configs: t('事件数据'),
    event_evidence_field_configs: t('事件证据'),
  };

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
      padding-left: 12px;
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

        &:first-child {
          width: 72px;
          border-right: 1px solid #dcdee5;
        }

        &:nth-child(2),
        &:nth-child(3) {
          width: 180px;
        }

        &:nth-child(4) {
          width: 100px;
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
        border-right: 1px solid #dcdee5;
        align-items: center;
        justify-content: center;
      }

      .value-row {
        width: calc(100% - 72px);

        .value-item {
          display: flex;
          height: 42px;
          line-height: 42px;

          .item {
            @include  item-styles;

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
                width: 270px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
              }
            }
          }
        }
      }
    }
  }
}
</style>
