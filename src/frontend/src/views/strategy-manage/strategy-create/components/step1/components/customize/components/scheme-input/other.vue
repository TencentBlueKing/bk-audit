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
  <div class="strategy-customize-eventlog-wrap">
    <bk-form-item
      class="no-label"
      label-width="0"
      property="configs.data_source.rt_id">
      <span>
        <bk-select
          v-model="formData.configs.data_source.rt_id"
          filterable
          :no-match-text="t('无匹配数据')"
          :placeholder="t('请选择')"
          @change="handleChangeDataSheet">
          <bk-option
            v-for="(dataSheet, dataSheetIndex) in props.tableData"
            :key="dataSheetIndex"
            :label="dataSheet.label"
            :value="dataSheet.value" />
        </bk-select>
      </span>
    </bk-form-item>
  </div>
</template>

<script setup lang='ts'>
  import {
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Expose {
    resetFormData: () => void,
  }

  interface Emits {
    (e: 'updateDataSource', value: IFormData['configs']['data_source']): void,
  }

  interface Props {
    tableData: Array<{
      label: string;
      value: string;
      children: Array<{
        label: string;
        value: string;
      }>
    }>;
  }

  interface IFormData {
    configs: {
      data_source: {
        rt_id: string,
      },
    },
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const formData = ref<IFormData>({
    configs: {
      data_source: {
        rt_id: '',
      },
    },
  });

  watch(() => props.tableData, (data) => {
    if (data) {
      formData.value.configs.data_source.rt_id = '';
      emits('updateDataSource', formData.value.configs.data_source);
    }
  }, {
    immediate: true,
  });

  // 选择数据表
  const handleChangeDataSheet = () => {
    emits('updateDataSource', formData.value.configs.data_source);
  };

  defineExpose<Expose>({
    resetFormData: () => {
      formData.value.configs.data_source.rt_id = '';
    },
  });
</script>
