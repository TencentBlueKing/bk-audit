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
  <div class="risk-manage-detail-linkevent-part">
    <div class="title">
      {{ t('关联事件') }}
    </div>
    <div class="body">
      <div class="list">
        <div>
          <div
            v-for="(_, index) in 3"
            :key="index"
            class="list-item"
            :class="[
              { active: active === index },
            ]"
            @click="() => active = index">
            {{ `2024-04-1${index} 02:00:00` }}
          </div>
        </div>
      </div>
      <div class="list-item-detail">
        <div class="important-information">
          <div class="title">
            {{ t('重点信息') }}
          </div>
          <template v-if="importantInformation.length">
            <render-info-block
              v-for="(item, index) in importantInformation"
              :key="index"
              class="flex mt16"
              style=" padding: 0 24px;margin-bottom: 12px;">
              <render-info-item
                v-for="(subItem, subIndex) in item"
                :key="subIndex"
                :description="subItem.description"
                :label="subItem.display_name"
                :label-width="labelWidth">
                {{ subItem.map_config?.target_value || t('以实际内容为准') }}
              </render-info-item>
            </render-info-block>
          </template>
          <template v-else>
            <render-info-block
              v-for="item in 2"
              :key="item"
              class="flex mt16"
              style="margin-bottom: 12px;">
              <render-info-item
                :label="t('以实际内容为准')"
                :label-width="120">
                {{ t('以实际内容为准') }}
              </render-info-item>
              <render-info-item
                :label="t('以实际内容为准')"
                :label-width="120">
                {{ t('以实际内容为准') }}
              </render-info-item>
            </render-info-block>
          </template>
        </div>
        <div
          class="title"
          style="padding-left: 12px">
          {{ t('基本信息') }}
        </div>
        <div
          class="base-info">
          <render-info-block
            class="flex mt16"
            style="margin-bottom: 12px;">
            <render-info-item
              :label="t('事件ID')"
              :label-width="labelWidth">
              {{ data.event_basic_field_configs.
                find(field => field.field_name === 'raw_event_id')?.map_config?.target_value || ('以实际内容为准') }}
            </render-info-item>
            <render-info-item
              :label="t('责任人')"
              :label-width="labelWidth">
              {{ data.event_basic_field_configs.
                find(field => field.field_name === 'operator')?.map_config?.target_value || ('以实际内容为准') }}
            </render-info-item>
          </render-info-block>
          <render-info-block
            class="flex mt16"
            style="margin-bottom: 12px;">
            <render-info-item
              :label="t('命中策略')"
              :label-width="labelWidth">
              {{ data.strategy_name }}
            </render-info-item>
            <render-info-item
              :label="t('事件描述')"
              :label-width="labelWidth">
              {{ data.event_basic_field_configs.
                find(field => field.field_name === 'event_content')?.map_config?.target_value || ('以实际内容为准') }}
            </render-info-item>
          </render-info-block>
        </div>
        <div
          class="title"
          style="padding-left: 12px">
          {{ t('事件结果') }}
        </div>
        <div
          class="data-info">
          <template v-if="eventData.length">
            <div
              v-for="(item, index) in eventData"
              :key="index"
              class="flex data-info-row">
              <div
                v-for="(subItem, subIndex) in item"
                :key="subIndex"
                class="flex data-info-item">
                <div class="data-info-item-key">
                  <tooltips :data="subItem.display_name" />
                </div>
                <div class="data-info-item-value">
                  <span>{{ t('以实际内容为准') }}</span>
                </div>
              </div>
            </div>
          </template>
          <template v-else>
            <div
              v-for="(item) in 4"
              :key="item"
              class="flex data-info-row">
              <div
                v-for="(subItem) in 2"
                :key="subItem"
                class="flex data-info-item">
                <div class="data-info-item-key">
                  <span>{{ t('以实际内容为准') }}</span>
                </div>
                <div class="data-info-item-value">
                  <span>{{ t('以实际内容为准') }}</span>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang='tsx'>
  import {
    computed,
    ref,
  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';

  import StrategyFieldEvent from '@model/strategy/strategy-field-event';

  import Tooltips from '@components/show-tooltips-text/index.vue';

  import RenderInfoBlock from '@views/strategy-manage/list/components/render-info-block.vue';

  import RenderInfoItem from './render-info-item.vue';

  interface IFormData {
    strategy_id?: number,
    strategy_name: string,
    tags: Array<string>,
    description: string,
    control_id: string,
    control_version?: number,
    configs: Record<string, any>,
    status: string,
    risk_level: string,
    risk_hazard: string,
    risk_guidance: string,
    risk_title: string,
    event_data_field_configs: StrategyFieldEvent['event_data_field_configs'],
    event_basic_field_configs: StrategyFieldEvent['event_basic_field_configs'],
    processor_groups: [],
    notice_groups: []
  }

  interface Props{
    data: IFormData
  }
  const props = defineProps<Props>();
  const { t, locale } = useI18n();
  const active = ref<number>(0);

  const labelWidth = computed(() => (locale.value === 'en-US' ? 160 : 120));

  // 转为二维数组
  const group = (array: Array<any>, subGroupLength: number = 2) => {
    let index = 0;
    const newArray = [];
    while (index < array.length) {
      newArray.push(array.slice(index, index += subGroupLength));
    }
    return newArray;
  };

  // 重点信息
  const importantInformation = computed(() => group([
    ...props.data.event_basic_field_configs.filter(item => item.is_priority),
    ...props.data.event_data_field_configs.filter(item => item.is_priority),
  ]));

  // 事件数据
  const eventData = computed(() => group(props.data.event_data_field_configs));

</script>
<style  lang="postcss">
.risk-manage-detail-linkevent-part {
  .title {
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    color: #313238;
  }

  .body {
    display: flex;
    margin-top: 14px;

    .list {
      display: inline-block;
      height: 500px;
      min-width: 164px;
      overflow: hidden;
      text-align: center;
      background: #f5f7fa;
      border-radius: 4px;

      .list-item {
        height: 32px;
        line-height: 32px;
        cursor: pointer;

        &:hover {
          background-color: #eaebf0;
        }
      }

      .active {
        color: #3a84ff !important;
        background: #e1ecff;
        border-left: 2px solid #3a84ff;

        &:hover {
          background: #e1ecff !important;
        }
      }
    }

    .list-item-detail {
      width: calc(100% - 164px);
      padding-left: 12px;

      .important-information {
        padding: 12px 0;
        margin-bottom: 24px;
        background-color: #fafbfd;

        .title {
          padding-left: 10px;
          border-left: 3px solid #3a84ff;
        }

        .render-info-item {
          width: 50%;
          align-items: flex-start;

          .info-value {
            word-break: break-all;
          }
        }
      }

      .base-info {
        padding: 0 24px;
        margin-bottom: 24px;

        .render-info-item {
          width: 50%;
          align-items: flex-start;

          .info-value {
            word-break: break-all;
          }
        }
      }

      .data-info {
        margin: 16px 0 24px;
        border: 1px solid #ecedf1;

        .data-info-row:last-child {
          .data-info-item-key,
          .data-info-item-value {
            border-bottom: 0;
          }
        }

        .data-info-item:last-child {
          .data-info-item-value {
            border-right: 0;
          }
        }

        .data-info-item {
          width: 50%;

          .data-info-item-key,
          .data-info-item-value {
            display: flex;
            align-items: center;
            padding: 6px 12px;
            border-right: 1px solid #ecedf1;
            border-bottom: 1px solid #ecedf1;
          }

          .data-info-item-key {
            width: 160px;
            background-color: #fafbfd;
            justify-self: flex-end;

            & > span {
              display: inline-block;
              width: 100%;
              text-align: right;
            }
          }

          .data-info-item-value {
            flex: 1;
            word-break: break-all;
          }
        }
      }

      .evidence-info {
        display: flex;
        max-width: 1000px;
        border-left: 1px solid #ecedf1;

        .evidence-info-value-wrap {
          display: flex;
          flex-wrap: nowrap;
          width: 100%;
        }

        .evidence-info-key,
        .evidence-info-value {
          display: inline-block;
          width: 168px;

          & > div {
            height: 32px;
            padding: 0 12px;
            line-height: 32px;
            border-right: 1px solid #ecedf1;
            border-bottom: 1px solid #ecedf1;

            .evidence-info-item-text {
              width: 100%;
              height: 100%;
              overflow: hidden;
              text-overflow: ellipsis;
              word-break: break-all;
              white-space: nowrap;
            }
          }
        }

        .evidence-info-value {
          flex: 1;
        }

        .evidence-info-key {
          min-width: 160px;
          text-align: right;
          background-color: #fafbfd;
        }
      }
    }
  }
}
</style>
