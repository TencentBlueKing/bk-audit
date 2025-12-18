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
  <div class="strategy-aiops-resource-data-wrap">
    <bk-loading :loading="loading">
      <bk-form-item
        :label="sourceType === 'BuildIn' ? t('资产') : t('所属业务')"
        property="configs.data_source.result_table_id"
        style="margin-bottom: 12px;">
        <bk-cascader
          v-slot="{node,data}"
          v-model="formData.configs.data_source.result_table_id"
          :disabled="isEditMode || isCloneMode || isUpgradeMode"
          filterable
          id-key="value"
          :list="filterTableData"
          name-key="label"
          trigger="hover"
          @change="handleTableIdChange">
          <p
            v-bk-tooltips="{
              disabled: (node.children && node.children.length) || !data.leaf,
              content: sourceType === 'BuildIn'
                ? t('该系统暂未上报资源数据')
                : t('审计中心暂未获得该业务数据的使用授权，请联系系统管理员到BKBASE上申请权限'),
              delay: 400,
            }">
            {{ node.name }}
          </p>
        </bk-cascader>
      </bk-form-item>
      <span
        class="label-is-required"
        style="color: #63656e;">
        {{ t('输入字段映射') }}
      </span>
      <render-field
        ref="fieldRef"
        :configs="inputFields"
        :data="formData.configs.data_source.fields"
        :rt-fields="rtFields"
        :trigger-error="triggerError" />

      <div style="margin-top: 12px;">
        <span style="color: #63656e;">
          {{ t('筛选输入数据') }}
        </span>
        <filter-condition
          ref="filterRef"
          :data="formData.configs.data_source"
          :loading="tableRtFieldsLoading"
          :rt-fields="rtFields"
          :trigger-error="triggerError"
          @update-filter-config="handleUpdateFilterConfig" />
      </div>
    </bk-loading>
  </div>
</template>

<script setup lang='ts'>
  import {
    computed,
    ref,
    watch,
  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';
  import {
    useRoute,
  } from 'vue-router';

  import StrategyManageService from '@service/strategy-manage';

  import type AiopPlanModel from '@model/strategy/aiops-plan';

  import useRequest from '@hooks/use-request';

  import FilterCondition,  { type ConditionData } from '../components/filter-condition.vue';
  import RenderField from '../components/render-field.vue';

  interface Props {
    loading: boolean;
    tableData: Array<{
      label: string;
      value: string;
      children: Array<{
        label: string;
        value: string;
      }>
    }>;
    sourceType: string;
    inputFields: ValueOf<AiopPlanModel['input_fields']>;
    triggerError?: boolean,
  }
  interface Emits {
    (e: 'updateDataSource', value: FormData['data_source']): void,
  }
  interface Exposes{
    getValue: () => Promise<any>;
    getFields: () => Record<string, any>;
    setConfigs: (config: FormData) => void;
  }


  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const route = useRoute();
  let isInit = false;
  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';
  const isUpgradeMode = route.name === 'strategyUpgrade';
  // const outputFields = computed(() => props.controlDetail?.output_config[0]?.fields);
  const fieldRef = ref();
  const filterRef = ref();
  const formData = ref({
    configs: {
      data_source: {
        fields: [] as ValueOf<AiopPlanModel['input_fields']>,
        filter_config: [] as ConditionData,
        result_table_id: [] as Array<string>,
      },
    },
  });
  const filterTableData = computed(() => props.tableData.map(item => ({
    ...item,
    leaf: true,
    disabled: !(item.children && item.children.length),
  })));
  type FormData = typeof formData.value['configs'];
  if (!isEditMode && !isCloneMode && !isUpgradeMode)   {
    isInit = true;
  }


  const {
    run: fetchTableRtFields,
    data: rtFields,
    loading: tableRtFieldsLoading,
  } = useRequest(StrategyManageService.fetchTableRtFields);


  const handleUpdateFilterConfig = (filterConfig: ConditionData) => {
    formData.value.configs.data_source.filter_config = filterConfig;
    handleUpdateDataSource();
  };
  const handleUpdateDataSource = () => {
    if (!isInit) return;
    emits('updateDataSource', formData.value.configs.data_source);
  };
  const handleTableIdChange = () => {
    fieldRef.value.clearFields();
    rtFields.value = [];
    const tableIdList = formData.value.configs.data_source.result_table_id;
    if (tableIdList.length) {
      fetchTableRtFields({
        table_id: tableIdList[tableIdList.length - 1],
      });
    }
    handleUpdateDataSource();
  };

  watch(() => props.inputFields, (data) => {
    if (data && (!isEditMode && !isCloneMode && !isUpgradeMode)) {
      formData.value.configs.data_source.fields = props.inputFields.map(item => item);
    }
  }, {
    immediate: true,
  });
  watch(() => props.tableData, (data) => {
    if (data) {
      formData.value.configs.data_source.result_table_id = [];
      handleUpdateDataSource();
      data.sort((a, b) => {
        if (a.children && a.children.length) return -1;
        if (b.children && b.children.length) return 1;
        return 0;
      });
    }
  }, {
    immediate: true,
  });
  defineExpose<Exposes>({
    getValue() {
      return Promise.all([fieldRef.value.getValue(), filterRef.value.getValue()]);
    },
    getFields() {
      return fieldRef.value.getFields();
    },
    setConfigs(config: Record<string, any>) {
      formData.value.configs.data_source.filter_config = config.data_source.filter_config;
      // 转换fields
      formData.value.configs.data_source.fields = props.inputFields.map((item) => {
        const sourceField = config.data_source.fields
          .find((field: {
            field_name: string;
            source_field: string
          }) => field.field_name === item.field_name)?.source_field || '';
        return { ...item, source_field: sourceField };
      });

      // 对tableid转换
      props.tableData.forEach((item) => {
        if (item.children && item.children.length) {
          item.children.forEach((cItem) => {
            if (cItem.value === config.data_source.result_table_id) {
              formData.value.configs.data_source.result_table_id = [item.value, config.data_source.result_table_id];
            }
          });
        }
      });
      isInit = true;
      filterRef.value.handleValueDicts(formData.value.configs.data_source.filter_config);
    },
  });
</script>


<style  lang="postcss" scoped>
.strategy-aiops-resource-data-wrap {
  .flex-center {
    display: flex;
    align-items: center;
  }
}
</style>
