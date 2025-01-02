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
  <div class="strategy-aiops-eventlog-wrap">
    <span
      class="label-is-required"
      style="color: #63656e;">
      {{ t('系统') }}
    </span>
    <bk-form-item
      class="no-label"
      label-width="0"
      property="configs.data_source.system_id"
      style="margin-bottom: 12px;">
      <span>
        <bk-select
          v-model="formData.configs.data_source.system_id"
          filterable
          :loading="isSystemListLoading"
          multiple
          multiple-mode="tag"
          :no-match-text="t('无匹配数据')"
          :placeholder="t('请选择')"
          @change="handleChangeSystem">
          <bk-option
            v-for="(system, systemIndex) in statusSystems"
            :key="systemIndex"
            :disabled="system.status == 'unset'"
            :label="system.name"
            :value="system.id">
            <span
              v-bk-tooltips="{
                disabled: system.status != 'unset',
                content: t('该系统暂未接入审计中心')
              }"
              style=" display: inline-block;width: 100%;">
              {{ system.name }}
            </span>
          </bk-option>
        </bk-select>
      </span>
    </bk-form-item>
    <bk-loading :loading="loading">
      <span
        v-if="formData.configs.data_source.fields && Object.keys(formData.configs.data_source.fields).length"
        class="label-is-required"
        style="color: #63656e;">
        {{ t('输入字段映射') }}
      </span>
      <table-component
        v-for="systemId in Object.keys(formData.configs.data_source.fields)"
        :key="systemId"
        ref="tableRefs"
        :configs="inputFields"
        :data="formData.configs.data_source.fields[systemId]"
        :label="systemList.find(item=> item.id === systemId)?.name || ''"
        :system-id="systemId"
        :trigger-error="triggerError" />
    </bk-loading>
  </div>
</template>

<script setup lang='ts'>
  import {
    // nextTick,
    ref,
    // computed,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
  } from 'vue-router';

  import CollectorManageService from '@service/collector-manage';
  import MetaManageService from '@service/meta-manage';

  import type AiopPlanModel from '@model/strategy/aiops-plan';

  import useRequest from '@hooks/use-request';

  import TableComponent from '../components/render-table.vue';

  interface Props{
    loading: boolean;
    tableData: Array<{
      label: string;
      value: string;
      children: Array<{
        label: string;
        value: string;
      }>
    }>;
    inputFields: ValueOf<AiopPlanModel['input_fields']>;
    triggerError?:boolean,
  }
  interface Emits {
    (e: 'updateDataSource', value: IFormData['configs']['data_source']): void,
  }
  interface Exposes {
    getValue: () => Promise<any>;
    getFields: () => Record<string, Record<string, string>>;
    setConfigs: (data: IFormData['configs']) => void;
    clearData: () => void;
  }


  interface IFormData {
    configs: {
      data_source: {
        fields: Record<string, any>, // 字段映射
        system_id: string[],
        filter_config:[],
        result_table_id: string, // 结果表ID
      },
    },
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const route = useRoute();
  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';
  const isUpgradeMode = route.name === 'strategyUpgrade';
  let isInit = false;
  let isInitFields = false;
  const { t } = useI18n();
  const tableRefs = ref();
  const formData = ref<IFormData>({
    configs: {
      data_source: {
        fields: {}, // 字段映射
        system_id: [],
        filter_config: [],
        result_table_id: '', // 结果表ID
      },
    },
  });
  const statusSystems = ref<Array<Record<string, any>>>([]);

  if (!isEditMode && !isCloneMode && !isUpgradeMode) {
    isInit = true;
  }


  // 获取系统
  const {
    loading: isSystemListLoading,
    data: systemList,
  } = useRequest(MetaManageService.fetchSystemWithAction, {
    defaultValue: [],
    manual: true,
    onSuccess(data) {
      const ids = data.map(item => item.id).join(',');
      fetchBatchSystemCollectorStatusList({
        system_ids: ids,
      });
    },
  });

  // 批量获取系统状态
  const {
    run: fetchBatchSystemCollectorStatusList,
  } = useRequest(CollectorManageService.fetchBatchSystemCollectorStatusList, {
    defaultValue: null,
    onSuccess: (result) => {
      if (!result) {
        return;
      }
      statusSystems.value = systemList.value.map(item => ({
        id: item.id,
        name: item.name,
        status: result[item.id].status,
      }));
      statusSystems.value.sort((a, b) => {
        if (a.status !== 'unset') return -1;
        if (b.status !== 'unset') return 1;
        return 0;
      });
    },
  });
  const systemFieldsMap: Record<string, Array<Record<string, any>> | null> = {};
  // 选择系统
  const handleChangeSystem = (systemIdList: string[], needUpdate = true) => {
    isInitFields = true;
    Object.keys(systemFieldsMap).forEach((id) => {
      if (!systemIdList.includes(id)) {
        systemFieldsMap[id] = null;
      }
    });
    formData.value.configs.data_source.fields = systemIdList.reduce((result, systemId) => {
      if (formData.value.configs.data_source.fields[systemId]) {
        if (!systemFieldsMap[systemId]) {
          systemFieldsMap[systemId] = props.inputFields.map((item) => {
            const fItem = formData.value.configs.data_source.fields[systemId]
              .find(({ field_name: fieldName }: { field_name: string }) => fieldName === item.field_name);
            if (fItem) {
              return {
                ...item,
                mapping_type: fItem.mapping_type || fItem.source_field[0].mapping_type,
                source_field: fItem.source_field,
              };
            }
            return {
              ...item,
              source_field: [[]],
            };
          });
        }

        return {
          ...result,
          [systemId]: systemFieldsMap[systemId],
        };
      }
      return {
        ...result,
        [systemId]: props.inputFields.map(item => ({
          ...item,
          source_field: [[]],
        })),
      };
    }, {} as Record<string, any>);
    if (needUpdate) {
      handleUpdateConfigs();
    }
  };

  const handleUpdateConfigs = () => {
    if (!isInit) return;
    emits('updateDataSource', formData.value.configs.data_source);
  };

  watch(() => props.tableData, (data) => {
    if (data) {
      formData.value.configs.data_source.result_table_id = data[0]?.value;
      handleUpdateConfigs();
    }
  }, {
    immediate: true,
  });

  watch(() => props.inputFields, (data) => {
    if (data && data.length && !isInitFields && isInit) {
      handleChangeSystem(formData.value.configs.data_source.system_id);
    }
  }, {
    immediate: true,
  });
  defineExpose<Exposes>({
    getValue() {
      return Promise.all(tableRefs.value?.map((item: { getValue: () => Promise<any> }) => item.getValue()));
    },
    setConfigs(configs: IFormData['configs']) {
      formData.value.configs.data_source.fields = configs.data_source.fields;
      formData.value.configs.data_source.system_id = configs.data_source.system_id;
      if (props.inputFields && props.inputFields.length && !isInitFields) {
        handleChangeSystem(formData.value.configs.data_source.system_id);
      }
      isInit = true;
    },
    getFields() {
      const fields = (tableRefs.value as { getFields: () => Record<string, Record<string, string>> }[])
        .reduce((
          result,
          item,
        ) => {
          const list = item.getFields();
          return {
            ...result,
            ...list,
          };
        }, {} as Record<string, Record<string, string>>);
      return fields;
    },
    clearData() {
      if (formData.value.configs.data_source.system_id && formData.value.configs.data_source.system_id.length) {
        formData.value.configs.data_source.system_id = [];
        handleChangeSystem([]);
      }
    },
  });
</script>
<!-- <style lang="postcss">
</style> -->

