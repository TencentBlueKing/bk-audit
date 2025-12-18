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
  <div class="filter-condition">
    <bk-loading :loading="commonLoading">
      <render-info-block>
        <render-info-item :label="t('数据源类型')">
          <span>
            {{ dataSourceType }}
          </span>
        </render-info-item>
      </render-info-block>
      <component
        :is="comMap[renderCom]"
        :common-data="commonData"
        :data="data" />
    </bk-loading>
  </div>
</template>
<script setup lang="ts">
  import {
    computed, shallowRef,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import CommonDataModel from '@model/strategy/common-data';
  import type StrategyModel from '@model/strategy/strategy';

  import useRequest from '@hooks/use-request';

  import RenderInfoBlock from '../render-info-block.vue';
  import RenderInfoItem from '../render-info-item.vue';

  import EventLogPart from './event-log.vue';
  import ResourceDataPart from './resource-data.vue';

  interface Props {
    data: StrategyModel,
  }
  const props = defineProps<Props>();
  const commonData = shallowRef<CommonDataModel>(new CommonDataModel());

  const comMap: Record<string, any> = {
    EventLog: EventLogPart,
    BuildIn: ResourceDataPart,
    BizAsset: ResourceDataPart,
  };
  const renderCom = computed(() => props.data.configs.config_type || '');
  const dataSourceType = computed(() => commonData.value.table_type
    .find(item => item.value === props.data.configs.config_type)?.label || '--');
  const { t } = useI18n();

  const {
    loading: commonLoading,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonDataModel(),
    manual: true,
    onSuccess: (data) => {
      commonData.value = data;
    },
  });
</script>
<style lang="postcss">
.filter-condition {
  .mr4 {
    margin-right: 4px;
  }

  .mb4 {
    margin-bottom: 4px;
  }

  .condition-item {
    display: flex;
    margin-bottom: 8px;
    flex-wrap: wrap;

    .condition-equation {
      padding: 2px 8px;
      color: #3a84ff;
      text-align: center;
      background: #edf4ff;
      border-radius: 2px;
    }

    .condition-key {
      padding: 2px 8px;
      color: #788779;
      background: #dde9de;
      border-radius: 2px;
    }

    .condition-method {
      padding: 2px 8px;
      color: #fe9c00;
      background: #fff1db;
      border-radius: 2px;
    }

    .condition-value {
      padding: 2px 8px;
      color: #63656e;
      background: #f0f1f5;
      border-radius: 2px;
    }
  }

  .condition-item:last-child {
    margin-bottom: 0;
  }
}
</style>
