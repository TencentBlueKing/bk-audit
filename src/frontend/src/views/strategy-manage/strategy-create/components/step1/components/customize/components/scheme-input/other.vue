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
      <bk-cascader
        v-slot="{node}"
        v-model="formData.configs.data_source.rt_id"
        filterable
        id-key="value"
        :list="filterTableData"
        name-key="label"
        trigger="hover"
        @change="handleChangeDataSheet">
        <p>
          {{ node.name }}
        </p>
      </bk-cascader>
    </bk-form-item>
  </div>
</template>

<script setup lang='ts'>
  import {
    computed,
    ref,
    watch,
  } from 'vue';
  import { useRoute } from 'vue-router';

  interface Expose {
    resetFormData: () => void,
    setConfigs: (config: IFormData['configs']) => void;
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
        rt_id: Array<string>,
      },
    },
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const route = useRoute();
  let isInit = false;
  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';
  const isUpgradeMode = route.name === 'strategyUpgrade';
  const formData = ref<IFormData>({
    configs: {
      data_source: {
        rt_id: [],
      },
    },
  });
  if (!isEditMode && !isCloneMode && !isUpgradeMode)   {
    isInit = true;
  }

  const filterTableData = computed(() => props.tableData.map(item => ({
    ...item,
    leaf: true,
    disabled: !(item.children && item.children.length),
  })));

  const handleUpdateDataSource = () => {
    if (!isInit) return;
    emits('updateDataSource', formData.value.configs.data_source);
  };

  // 选择数据表
  const handleChangeDataSheet = () => {
    handleUpdateDataSource();
  };

  watch(() => props.tableData, (data) => {
    if (data) {
      formData.value.configs.data_source.rt_id = [];
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

  defineExpose<Expose>({
    resetFormData: () => {
      formData.value.configs.data_source.rt_id = [];
    },
    setConfigs(config: Record<string, any>) {
      if (Array.isArray(config.data_source.rt_id)) {
        formData.value.configs.data_source.rt_id = config.data_source.rt_id;
      }
      // 对tableid转换
      props.tableData.forEach((item) => {
        if (item.children && item.children.length) {
          item.children.forEach((cItem) => {
            if (cItem.value === config.data_source.rt_id) {
              formData.value.configs.data_source.rt_id = [item.value, config.data_source.rt_id];
            }
          });
        }
      });
      isInit = true;
    },
  });
</script>
