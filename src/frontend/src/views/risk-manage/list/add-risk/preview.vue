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
    <div
      class="base-info"
      :style="borderStyle">
      <div class="info-title">
        {{ title }}
      </div>
      <div>
        <base-info-form
          :data="editData.selectedRiskValue"
          :edit-data="editData"
          is-add-risk
          :processor-groups="processorGroups"
          :risk-status-common="riskStatusCommon"
          :show-field-names="priorityFieldNames"
          :strategy-list="strategyList" />
        <base-info-form
          v-if="isShowMore"
          :data="editData.selectedRiskValue"
          :edit-data="editData"
          :event-content-comfig="eventContentComfig"
          :event-type-comfig="eventTypeComfig"
          is-add-risk
          :notice-groups="noticeGroups"
          :operators-comfig="operatorsComfig"
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
        <div class="event-list-right">
          <div class="right-info">
            <div class="right-info-title">
              {{ t('基本信息') }}
            </div>
            <div class="right-info-item">
              <span
                v-if="eventTimeIshow"
                class="info-item">
                <span class="info-item-left">{{ t('事件发生时间 ') }}</span>:
                <span class="info-item-value">{{ editData.formData.event_time }}</span>
              </span>
              <span
                v-if="operatorIshow"
                class="info-item">
                <span class="info-item-left">{{ t('责任人') }}</span>:
                <span class="info-item-value">
                  <edit-tag
                    v-if="operatorsComfig[0]?.typeValue === 'user-selector'"
                    :data="operatorsComfig[0].valueText || ''"
                    style="display: inline-block;" />
                  <span v-else> {{ operatorsComfig[0]?.valueText ||'--' }} </span>
                </span>
              </span>
              <span
                v-if="eventSourceIshow"
                class="info-item">
                <span class="info-item-left">{{ t('事件来源') }} {{ eventSourceComfig[0]?.is_show }}</span>:
                <span class="info-item-value">
                  <edit-tag
                    v-if="eventSourceComfig[0]?.typeValue === 'user-selector'"
                    :data="eventSourceComfig[0].value || ''"
                    style="display: inline-block;" />
                  <span v-else> {{ eventSourceComfig[0]?.value === '' ? '--' : eventSourceComfig[0]?.value }} </span>
                </span>
              </span>
              <span
                v-if="eventTypeIshow"
                class="info-item">
                <span class="info-item-left">{{ t('事件类型') }}</span>:
                <span class="info-item-value">
                  <edit-tag
                    v-if="eventTypeComfig[0]?.typeValue === 'user-selector'"
                    :data="eventTypeComfig[0].value || ''"
                    style="display: inline-block;" />
                  <span v-else> {{ eventTypeComfig[0]?.value ||'--' }} </span>

                </span>
              </span>
              <div
                v-if="eventContentIshow"
                class="info-item-line">
                <span class="line-item">
                  <span class="info-item-left">{{ t('事件描述') }}</span>:
                  <span class="line-value">
                    <edit-tag
                      v-if="eventContentComfig[0]?.typeValue === 'user-selector'"
                      :data="eventContentComfig[0].value || []"
                      style="display: inline-block;" />
                    <span v-else> {{ eventContentComfig[0]?.value ||'--' }} </span>
                  </span>
                </span>
              </div>
            </div>
          </div>
          <div class="right-info">
            <div class="right-info-title">
              {{ t('事件数据') }}
            </div>
            <div class="edit-data">
              <div
                v-for="eventItem in editData.eventData"
                :key="eventItem.field_name"
                class="edit-data-item">
                <span
                  v-bk-tooltips="{
                    content: eventItem.description,
                    disabled: eventItem.description === '',
                    placement: 'top'
                  }"
                  :class="eventItem.description !== '' ?
                    'dashed-underline edit-data-ite-lable' : 'edit-data-ite-lable' ">
                  {{ eventItem.display_name }}</span>
                <span class="lable-icon">：</span>
                <span
                  v-if="eventItem.typeValue === 'user-selector'"
                  class="info-item-value">
                  <edit-tag
                    :data="eventItem.value || []"
                    style="display: inline-block;" />
                </span>
                <span
                  v-else
                  class="info-item-value">{{ eventItem.value === '' ? '--' : eventItem.value }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { computed, onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import NoticeManageService from '@service/notice-group';
  import RiskManageService from '@service/risk-manage';
  import StrategyManageService from '@service/strategy-manage';

  import type RiskManageModel from '@model/risk/risk';
  import type StrategyInfo from '@model/risk/strategy-info';

  import useRequest from '@hooks/use-request';

  import EditTag from '@components/edit-box/tag.vue';

  import BaseInfoForm from '../../../risk-manage/detail/components/base-info-form.vue';

  interface Props {
    editData: {
      formData: Record<string, any>,
      eventData: Array<Record<string, any>>,
      selectedRiskValue: RiskManageModel & StrategyInfo,
      is_show: boolean,
    }
  }
  interface Exposes{
    initData(data: Record<string, any>): void,
  }
  const props = defineProps<Props>();
  const { t } = useI18n();
  const isShowMore = ref(false);
  const eventData = ref<Record<string, any>>({});
  const title = ref();
  const noticeGroups = ref<string[]>([]); // 关注人
  const processorGroups = ref<string[]>([]); // 处理人
  const operatorsComfig = ref<Array<Record<string, any>>>([]); // 责任人
  const eventSourceComfig = ref<Array<Record<string, any>>>([]); // 事件来源
  const eventTypeComfig = ref<Array<Record<string, any>>>([]); // 事件类型
  const eventContentComfig = ref<Array<Record<string, any>>>([]); // 事件描述
  const rawEventIdComfig = ref<Array<Record<string, any>>>([]); // 原始事件id
  const eventTimeComfig = ref<Array<Record<string, any>>>([]); // 事件时间
  const strategyIdComfig = ref<Array<Record<string, any>>>([]); // 策略id
  const eventEndTimeComfig = ref<Array<Record<string, any>>>([]); // 事件结束时间
  const eventDataComfig = ref<Array<Record<string, any>>>([]); // 事件结束时间

  const operatorIshow  = computed(() => props.editData.selectedRiskValue.event_basic_field_configs.filter(item => item.field_name === 'operator')[0]?.is_show);

  const eventTimeIshow  = computed(() => props.editData.selectedRiskValue.event_basic_field_configs.filter(item => item.field_name === 'event_time')[0]?.is_show);

  const eventSourceIshow  =  computed(() => props.editData.selectedRiskValue.event_basic_field_configs.filter(item => item.field_name === 'event_source')[0]?.is_show);

  const eventContentIshow = computed(() => props.editData.selectedRiskValue.event_basic_field_configs.filter(item => item.field_name === 'event_content')[0]?.is_show);
  const eventTypeIshow  = computed(() => props.editData.selectedRiskValue.event_basic_field_configs.filter(item => item.field_name === 'event_type')[0]?.is_show);

  const riskLevelMap: Record<string, {
    label: string,
    color: string,
  }> =  {
    HIGH: {
      label: t('高'),
      color: '#ea3636',
    },
    MIDDLE: {
      label: t('中'),
      color: '#ff9c01',
    },
    LOW: {
      label: t('低'),
      color: '#979ba5',
    },
  };
  const borderStyle = computed(() => ({
    'border-top': `6px solid ${riskLevelMap[props.editData.selectedRiskValue.risk_level]?.color}`,
  }));

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

  // 重点展示字段的 field_name 数组
  const priorityFieldNames = ref([]);


  // 非重点展示字段的 field_name 数组
  const normalFieldNames = ref([]);

  // 获取通知组
  const {
    data: groupList,
  } = useRequest(NoticeManageService.fetchGroupList, {
    defaultValue: {
      page: 1,
      num_pages: 9999,
      results: [],
      total: 0,
    },
    manual: true,
    onSuccess: () => {
      const { notice_groups, processor_groups, event_basic_field_configs } = props.editData.selectedRiskValue;
      // eslint-disable-next-line max-len, camelcase
      const noticeGroupsArr =  groupList.value.results.filter((item: Record<string, any>) => notice_groups.includes(item.group_id));
      noticeGroups.value = [...new Set(noticeGroupsArr.flatMap((item: Record<string, any>) => item.group_member))];
      // eslint-disable-next-line max-len, camelcase
      const processorGroupsArr =  groupList.value.results.filter((item: Record<string, any>) => processor_groups.includes(item.group_id));
      // eslint-disable-next-line max-len
      processorGroups.value = [...new Set(processorGroupsArr.flatMap((item: Record<string, any>) => item.group_member))];
      // 事件配置处理
      const eventConfigs = [
        { fieldName: 'operator', configRef: operatorsComfig, label: '责任人' },
        { fieldName: 'event_source', configRef: eventSourceComfig, label: '事件来源' },
        { fieldName: 'event_type', configRef: eventTypeComfig, label: '事件类型' },
        { fieldName: 'event_content', configRef: eventContentComfig, label: '事件描述' },
        { fieldName: 'raw_event_id', configRef: rawEventIdComfig, label: '原始事件ID' },
        { fieldName: 'strategy_id', configRef: strategyIdComfig, label: '策略ID' },
        { fieldName: 'event_time', configRef: eventTimeComfig, label: '事件时间' },
        { fieldName: 'event_end_time', configRef: eventEndTimeComfig, label: '事件结束时间' },
        { fieldName: 'event_data', configRef: eventDataComfig, label: '事件' },
      ];

      eventConfigs.forEach(({ fieldName, configRef }) => {
        // eslint-disable-next-line camelcase
        const initData = fieldName === 'event_data' ?  props.editData.selectedRiskValue : event_basic_field_configs;
        // eslint-disable-next-line camelcase
        const mapping = Array.isArray(initData)
          ? initData.find((item: Record<string, any>) => item.field_name === fieldName)
          : null;
        // 安全检查：确保mapping和map_config存在
        if (!mapping?.map_config?.source_field) {
          // eslint-disable-next-line no-param-reassign
          configRef.value = [];
        } else {
          // eslint-disable-next-line no-param-reassign
          configRef.value = props.editData?.eventData.filter((item: Record<string, any>) =>
            // eslint-disable-next-line implicit-arrow-linebreak
            item.field_name === mapping.map_config.source_field);
        }
      });
      const { variables, textWithoutVariables } =  handleTextTitle(props.editData.selectedRiskValue.risk_title);
      // eslint-disable-next-line max-len
      const titleArr = eventConfigs.find((item: Record<string, any>) => item.fieldName === variables)?.configRef.value || [];
      const titleText = Array.isArray(titleArr[0]?.value) ? titleArr[0]?.value.join(',') : titleArr[0]?.value || '--';
      title.value = `${titleText} ${textWithoutVariables}`;
    },
  });
  const handleTextTitle = (title: string) => {
    // 使用正则表达式匹配 {{ }} 中的内容
    const regex = /\{\{\s*(.*?)\s*\}\}/g;
    const matches = [];
    let match;
    while ((match = regex.exec(title)) !== null) {
      matches.push(match[1]); // 获取 {{ }} 中的内容
    }

    // 返回完整信息对象
    return {
      original: title, // 原始字符串
      variables: matches[0], // 所有匹配的变量
      textWithoutVariables: title.replace(regex, '').trim(), // 去除变量后的文本
    };
  };
  onMounted(() => {
  });

  defineExpose<Exposes>({
    initData(data: Record<string, any>) {
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

      /* width: 96%; */
      padding-bottom: 10px;
      margin-top: 20px;
      margin-left: 2%;
      background: #fff;

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
            width: 700px;
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

  .info-item-left {
    display: inline-block;
    max-width: 25%;
    min-width: 120px;
    text-align: right;
  }

  .info-item-value {
    display: inline-block;
    width: 55%;
    padding-left: 5px;
    text-align: left;
    white-space: pre-line;
    vertical-align: middle;
  }

  .dashed-underline {
    padding-bottom: 2px;
    cursor: pointer;
    border-bottom: 1px dashed #c4c6cc;
  }

  .edit-data {
    display: flex;

    /* background-color: #4d4f56; */
    width: 720px;
    flex-wrap: wrap;

    .edit-data-item {
      width: 50%;
      padding-bottom: 20px;

      .edit-data-ite-lable {
        display: inline-block;
        width: 130px;
        text-align: right;
        word-break: break-all;
        word-wrap: break-word;
        vertical-align: middle;
      }

      .lable-icon {
        margin-left: 3px;
        vertical-align: middle;
      }
    }
  }
}
</style>
