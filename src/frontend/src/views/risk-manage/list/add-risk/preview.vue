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
  <div class="preview">
    <div class="base-info">
      <div class="info-title">
        {{ editData.selectedRiskValue?.risk_title }}
      </div>
      <div>
        <base-info-form
          :data="editData.selectedRiskValue"
          :risk-status-common="riskStatusCommon"
          :show-field-names="priorityFieldNames"
          :strategy-list="strategyList" />
        <base-info-form
          v-if="isShowMore"
          :data="editData.selectedRiskValue"
          :risk-status-common="riskStatusCommon"
          :show-field-names="normalFieldNames"
          :strategy-list="strategyList" />
      </div>
      <div class="show-more-condition-btn">
        <bk-button
          class="show-more-btn"
          text
          @click="() => isShowMore = !isShowMore">
          <audit-icon
            :class="{ active: isShowMore }"
            style=" margin-right: 5px;"
            type="angle-double-down" />
          {{ isShowMore ? t('收起字段') : t('展开更多字段') }}
        </bk-button>
      </div>
    </div>

    <div class="event-info">
      <div class="event-title">
        {{ t('关联事件') }}
      </div>
      <div class="event-list">
        <div class="event-list-left">
          <div
            class="active-event event-time">
            {{ editData.formData.event_time }}
          </div>
        </div>
        <div class="event-list-right">
          <div class="right-info">
            <div class="right-info-title">
              {{ t('基本信息') }}
            </div>
            <div class="right-info-item">
              <span class="info-item">
                <span>{{ t('事件发生时间 ') }}</span>:
                <span class="info-item-value">{{ editData.formData.event_time }}</span>
              </span>
              <span class="info-item">
                <span>{{ t('责任人') }}</span>:
                <span class="info-item-value">
                  <bk-tag
                    v-for="value in editData.formData.operator"
                    :key="value"
                    style="margin-left: 5px;"> {{ value }}</bk-tag>
                </span>
              </span>
              <span class="info-item">
                <span>{{ t('事件来源') }}</span>:
                <span class="info-item-value"> {{ editData.formData.event_source }}</span>
              </span>
              <span class="info-item">
                <span>{{ t('事件类型') }}</span>:
                <span class="info-item-value">{{ editData.formData.event_type }}</span>
              </span>
              <div class="info-item-line">
                <span class="line-item">
                  <span>{{ t('事件描述') }}</span>:
                  <span class="line-value">{{ editData.formData.event_content }}</span>
                </span>
              </div>
            </div>
          </div>
          <div class="right-info">
            <div class="right-info-title">
              {{ t('事件数据') }}
            </div>
            <div class="right-info-item">
              <span
                v-for="eventItem in editData.eventData"
                :key="eventItem.field_name"
                class="info-item">
                <span
                  v-bk-tooltips="{
                    content: eventItem.description,
                    disabled: eventItem.description === '',
                    placement: 'top'
                  }"
                  :class="eventItem.description !== '' ? 'dashed-underline' : '' ">
                  {{ eventItem.display_name }}</span>:
                <span
                  v-if="eventItem.typeValue === 'user-selector'"
                  class="info-item-value">
                  <bk-tag
                    v-for="valueItem in eventItem.value"
                    :key="valueItem"
                    style="margin-left: 5px;"> {{ valueItem }}</bk-tag>
                </span>
                <span
                  v-else
                  class="info-item-value">{{ eventItem.value || '--' }}</span>
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskManageService from '@service/risk-manage';
  import StrategyManageService from '@service/strategy-manage';

  import type RiskManageModel from '@model/risk/risk';
  import type StrategyInfo from '@model/risk/strategy-info';

  import useRequest from '@hooks/use-request';

  import BaseInfoForm from '../../../risk-manage/detail/components/base-info-form.vue';

  interface Props {
    editData: {
      formData: Record<string, any>,
      eventData: Array<Record<string, any>>,
      selectedRiskValue: RiskManageModel & StrategyInfo,
    }
  }
  interface Exposes{
    initData(data: Record<string, any>): void,
  }
  defineProps<Props>();
  const { t } = useI18n();
  const isShowMore = ref(false);
  const eventData = ref<Record<string, any>>({});
  const {
    data: strategyList,
  } = useRequest(StrategyManageService.fetchAllStrategyList, {
    manual: true,
    defaultValue: [],
  });
  const {
    data: riskStatusCommon,
    run: fetchRiskStatusCommon,
  } = useRequest(RiskManageService.fetchRiskStatusCommon, {
    defaultValue: [],
  });
  console.log('eventData', eventData.value);

  // 重点展示字段的 field_name 数组
  const priorityFieldNames = ref([]);


  // 非重点展示字段的 field_name 数组
  const normalFieldNames = ref([]);


  defineExpose<Exposes>({
    initData(data: Record<string, any>) {
      console.log('data>>>>>>>>>>>>', data);
      eventData.value = data.selectedRiskValue;
      priorityFieldNames.value = data.selectedRiskValue?.risk_meta_field_config
        .filter((item: Record<string, any>) => item.is_priority);
      normalFieldNames.value = data.selectedRiskValue?.risk_meta_field_config
        .filter((item: Record<string, any>) => !item.is_priority);
      fetchRiskStatusCommon();
    },
  });
</script>

<style lang="postcss" scoped>
.preview {
  .base-info {
    position: relative;
    width: 96%;
    margin-top: 20px;
    margin-left: 2%;
    background: #fff;
    border-top: 6px solid red;
    border-radius: 2px;
    box-shadow: 0 2px 4px 0 #1919290d;

    .info-title {
      margin-top: 5px;
      margin-left: 16px;
      font-size: 14px;
      font-weight: 700;
      line-height: 22px;
      letter-spacing: 0;
      color: #313238;
    }

    .show-more-condition-btn {
      position: absolute;
      right: calc(50% - 52px);
      bottom: -10px;
      box-shadow: 0 2px 4px 0 #1919290d;

      .show-more-btn {
        width: 120px;
        height: 22px;
        color: #fff;
        background: #c4c6cc;
        ;
        border-radius: 12px;

        &:hover {
          background-color: #3a84ff;
        }
      }

      .active {
        transform: rotateZ(-180deg);
        transition: all .15s;
      }
    }
  }

  .event-info {
    position: relative;
    width: 96%;
    margin-top: 20px;
    margin-left: 2%;
    background: #fff;
    border-radius: 2px;
    box-shadow: 0 2px 4px 0 #1919290d;

    .event-title {
      padding-top: 10px;
      padding-bottom: 10px;
      margin-left: 16px;
      font-size: 14px;
      font-weight: 700;
      line-height: 22px;
      letter-spacing: 0;
      color: #313238;

      .event-count {
        display: inline-block;
        height: 16px;
        padding-right: 3px;
        padding-left: 3px;
        font-size: 12px;
        line-height: 16px;
        letter-spacing: 0;
        color: #979ba5;
        text-align: center;
        background-color: #f0f1f5;
        border-radius: 2px;
      }
    }

    .event-list {
      display: flex;
      width: 96%;
      padding-bottom: 10px;
      margin-top: 20px;
      margin-left: 2%;
      background: #fff;

      .event-list-left {
        width: 144px;
        margin-left: 10px;
        background: #f5f7fa;
        border-radius: 4px;

        .event-time {
          width: 100%;
          height: 32px;
          font-size: 12px;
          line-height: 32px;
          color: #4d4f56;
          text-align: center;
          cursor: pointer;
        }

        .active-event {
          background: #e1ecff;
          border-left: 3px solid #3a84ff;
        }
      }

      .event-list-right {
        width: calc(100% - 154px);
        margin-left: 10px;

        .right-info {
          .right-info-title {
            font-size: 14px;
            font-weight: 700;
            line-height: 22px;
            letter-spacing: 0;
            color: #313238;
          }

          .right-info-item {
            margin-top: 10px;
            margin-bottom: 10px;

            .info-item {
              display: inline-block;
              width: 50%;
              padding-right: 5px;
              padding-bottom: 10px;
              font-size: 12px;
              line-height: 32px;
              letter-spacing: 0;
              color: #4d4f56;
              vertical-align: top;
            }
          }

          .info-item-line {
            width: 100%;
            padding-bottom: 10px;

            .line-item {
              width: 100%
            }

          }
        }
      }
    }
  }

  .info-item-value {
    padding-left: 5px;
  }

  .dashed-underline {
    padding-bottom: 2px;
    cursor: pointer;
    border-bottom: 1px dashed #c4c6cc;
  }
}
</style>
