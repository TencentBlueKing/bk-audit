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
  <div
    class="detail-base-info"
    :style="borderStyle">
    <div class="title">
      {{ data.risk_title }}
    </div>
    <base-info-form
      v-if="priorityFieldNames.length"
      :data="data"
      :risk-status-common="riskStatusCommon"
      :show-field-names="priorityFieldNames"
      style="background-color: #f5f7fa;" />
    <template v-if="(normalFieldNames.length && isShowMore) || !priorityFieldNames.length">
      <base-info-form
        :data="data"
        :risk-status-common="riskStatusCommon"
        :show-field-names="normalFieldNames" />
    </template>
    <div
      v-if="priorityFieldNames.length || normalFieldNames.length"
      class="show-more-condition-btn">
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
</template>

<script setup lang='ts'>
  import {
    computed,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';

  import StrategyFieldEvent from '@model/strategy/strategy-field-event';

  import useRequest from '@hooks/use-request';

  import BaseInfoForm from './base-info-form.vue';

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
    event_evidence_field_configs: StrategyFieldEvent['event_evidence_field_configs'],
    risk_meta_field_config: StrategyFieldEvent['risk_meta_field_config'],
    processor_groups: [],
    notice_groups: []
  }

  interface Props{
    data: IFormData,
    riskStatusCommon: Array<{
      id: string,
      name: string,
    }>,
  }
  const props = defineProps<Props>();

  const riskLevelMap: Record<string, {
    label: string,
    color: string,
  }> =  {
    HIGH: {
      label: '高',
      color: '#ea3636',
    },
    MIDDLE: {
      label: '中',
      color: '#ff9c01',
    },
    LOW: {
      label: '低',
      color: '#979ba5',
    },
  };
  const { t } = useI18n();

  const isShowMore = ref(false);
  const strategyTagMap = ref<Record<string, string>>({});

  const borderStyle = computed(() => ({
    'border-top': `6px solid ${riskLevelMap[props.data.risk_level].color}`,
  }));

  // 重点展示字段的 field_name 数组
  const priorityFieldNames = computed(() => props.data.risk_meta_field_config
    .filter(item => item.is_priority));

  // 非重点展示字段的 field_name 数组
  const normalFieldNames = computed(() => props.data.risk_meta_field_config
    .filter(item => !item.is_priority));

  // 获取标签列表
  useRequest(MetaManageService.fetchTags, {
    defaultParams: {
      page: 1,
      page_size: 1,
    },
    defaultValue: [],
    manual: true,
    onSuccess: (data) => {
      data.forEach((item) => {
        strategyTagMap.value[item.tag_id] = item.tag_name;
      });
    },
  });
</script>
<style lang="postcss" scoped>
.detail-base-info {
  position: relative;
  padding: 10px 16px;
  background: #fff;
  border-radius: 2px;
  box-shadow: 0 2px 4px 0 #1919290d;

  .title {
    margin-bottom: 10px;
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    color: #313238;
  }

  .render-info-item {
    min-width: 50%;
    align-items: flex-start;
  }

  .show-more-condition-btn {
    position: absolute;
    right: calc(50% - 52px);
    bottom: -11px;
    box-shadow: 0 2px 4px 0 #1919290d;

    .show-more-btn {
      width: 120px;
      height: 22px;
      color: #fff;
      background: #c4c6cc;;
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
</style>
