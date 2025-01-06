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
  <div class="customize-resource-data-wrap">
    <bk-form-item
      class="no-label"
      label-width="0"
      property="configs.data_source.result_table_id">
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

  interface Expose {
    resetFormData: () => void,
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
    sourceType: string;
  }
  interface Emits {
    (e: 'updateDataSource', value: FormData['data_source']): void,
  }


  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const route = useRoute();
  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';
  const isUpgradeMode = route.name === 'strategyUpgrade';
  const formData = ref({
    configs: {
      data_source: {
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

  const handleUpdateDataSource = () => {
    emits('updateDataSource', formData.value.configs.data_source);
  };
  const handleTableIdChange = () => {
    handleUpdateDataSource();
  };

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

  defineExpose<Expose>({
    resetFormData: () => {
      formData.value.configs.data_source.result_table_id = [];
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
