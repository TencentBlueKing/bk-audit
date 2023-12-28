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
  <div v-if="data">
    <render-info-block>
      <bk-loading :loading="tableLoading">
        <render-info-item :label="tableTitleName">
          <span>
            {{ tableNameList.join(' / ') }}
          </span>
        </render-info-item>
      </bk-loading>
    </render-info-block>


    <render-info-block>
      <render-info-item :label="t('输入字段映射')">
        <render-field
          :configs="inputFields"
          :data="fieldData"
          :rt-fields-map="rtFieldsMap" />
      </render-info-item>
    </render-info-block>


    <filter-condition
      :data="data"
      :loading="tableRtFieldsLoading"
      :rt-fields-map="rtFieldsMap" />

    <render-info-block>
      <render-info-item :label="t('方案参数')">
        <render-parameter
          :data="data.configs.variable_config" />
      </render-info-item>
    </render-info-block>

    <render-info-block>
      <render-info-item :label="t('调度周期')">
        <template v-if="data.configs.aiops_config">
          <span>
            {{ data?.configs.aiops_config.count_freq }}
          </span>
          <span>
            {{ commonData.offset_unit
              .find((item) =>
                item.value === data.configs.aiops_config.schedule_period)?.label }}
          </span>
        </template>
        <span v-else>
          --
        </span>
      </render-info-item>
    </render-info-block>
  </div>
</template>

<script setup lang='ts'>
  import {
    computed,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ControlManageService from '@service/control-manage';
  import StrategyManageService from '@service/strategy-manage';

  import ControlModel from '@model/control/control';
  import type CommonData from '@model/strategy/common-data';
  import type StrategyModel from '@model/strategy/strategy';

  import useRequest from '@hooks/use-request';

  import RenderInfoBlock from '../render-info-block.vue';
  import RenderInfoItem from '../render-info-item.vue';

  import FilterCondition from './filter-condition.vue';
  import RenderField from './render-field.vue';
  import RenderParameter from './render-parameter.vue';

  interface Props{
    data: StrategyModel,
    commonData: CommonData
  }


  const props = defineProps<Props>();
  const { t } = useI18n();
  const tableNameList = ref<Array<string>>([]);
  const tableTitleName = computed(() => (props.data.configs.config_type === 'BuildIn'
    ? t('资产') : t('所属业务')));
  const inputFields = computed(() => {
    if (controlDetail.value.input_config && controlDetail.value.input_config.length) {
      return  controlDetail.value.input_config[0].require_fields || [];
    }
    return [];
  });
  const rtFieldsMap = ref<Record<string, string>>({});
  const fieldData = ref<Array<Record<string, any>>>([]);

  // 获取tableid
  const {
    run: fetchTable,
    loading: tableLoading,
  } = useRequest(StrategyManageService.fetchTable, {
    defaultValue: [],
    onSuccess(data) {
      const tableId = props.data.configs.data_source?.result_table_id;
      data.forEach((item) => {
        if (item.children && item.children.length) {
          item.children.forEach((cItem) => {
            if (cItem.value === tableId) {
              tableNameList.value =  [item.label, cItem.label];
            }
          });
        }
      });
    },
  });
  // 获取方案详情
  const {
    run: fetchControlDetail,
    data: controlDetail,
  } = useRequest(ControlManageService.fetchControlDetail, {
    defaultValue: new ControlModel(),
    onSuccess() {
      if (props.data.configs.data_source) {
        const { fields } = props.data.configs.data_source;
        fieldData.value = (fields as unknown as Array<{
          field_name: string;
          source_field: string;
        }>).map((item) => {
          const ret = inputFields.value
            .find((configItem: { field_name: string }) => item.field_name === configItem.field_name);
          return {
            ...ret,
            source_field: item.source_field,
          };
        });
      }
    },
  });
  // 获取rt字段
  const {
    run: fetchTableRtFields,
    loading: tableRtFieldsLoading,
  } = useRequest(StrategyManageService.fetchTableRtFields, {
    defaultValue: null,
    onSuccess(data) {
      if (data) {
        data.forEach((item) => {
          rtFieldsMap.value[item.value] = item.label;
        });
      }
    },
  });

  watch(() => props.data, (data) => {
    if (data) {
      fetchTable({
        table_type: data.configs.config_type,
      });
      fetchTableRtFields({
        table_id: data.configs.data_source?.result_table_id,
      });
      fetchControlDetail({
        control_id: data.control_id,
        control_version: data.control_version,
      });
    }
  }, {
    immediate: true,
  });
</script>
<!-- <style scoped>

</style> -->
