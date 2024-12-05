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
  <div class="diff-condition">
    <bk-form-item
      :label="t('算法')"
      label-width="160"
      property="diff"
      required>
      <bk-select
        v-model="formData.diff"
        filterable
        :placeholder="t('请选择')"
        style="width: 480px;"
        @change="handleDiff">
        <bk-option
          v-for="(condition, conditionIndex) in diffs"
          :key="conditionIndex"
          :label="`算法名称(${condition.name})`"
          :value="condition.id" />
      </bk-select>
    </bk-form-item>
    <bk-form-item
      :label="t('系统')"
      label-width="160"
      property="diff"
      required>
      <bk-select
        v-model="formData.systerm"
        filterable
        :placeholder="t('请选择')"
        style="width: 480px;"
        @change="handleDiff">
        <bk-option
          v-for="(condition, conditionIndex) in diffs"
          :key="conditionIndex"
          :label="`算法名称(${condition.name})`"
          :value="condition.id" />
      </bk-select>
    </bk-form-item>
    <bk-form-item
      :label="t('算法参数')"
      label-width="160"
      property="statistics_field"
      required>
      <auth-collapse-panel
        :is-active="isActive"
        :label="t('作业平台')"
        style="width: 800px;">
        <bk-table
          ref="resultTable"
          :border="['outer', 'col']"
          :columns="tableColumn"
          :data="diffParamsData"
          style="width: 800px;" />
      </auth-collapse-panel>
      <auth-collapse-panel
        class="mt12"
        :is-active="isActive"
        :label="t('节点管理')"
        style="width: 800px;margin-top: 12px;">
        <bk-table
          ref="resultTable"
          :border="['outer', 'col']"
          :columns="tableColumn"
          :data="diffParamsData"
          style="width: 800px;" />
      </auth-collapse-panel>
    </bk-form-item>
  </div>
</template>
<script setup lang="tsx">
  import {
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Emits {
    (e: 'updateDiff', value: string): void,
  }
  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const formData = ref({
    diff: '',
    systerm: '',
  });
  const isActive = ref(true);
  const diffs = [
    {
      id: 'name1',
      name: 'generic algorithm',
    },
    {
      id: 'name2',
      name: 'elevator (scan) algorithm',
    },
    {
      id: 'name3',
      name: 'FIFO replacement policy',
    },
  ];
  const tableColumn = [
    {
      label: () => '#',
      field: () => 'id',
      width: 40,
    },
    {
      label: () => t('参数名'),
      render: ({ data }:{data: Record<string, any>}) => (
        <span>
          <span class="params-type">string</span>
          <span style="border-bottom: 1px dashed #c4c6cc;margin-left:5px ">{data.name}(中文名1)</span>
        </span>
      ),
    },
    {
      label: () => t('参数值'),
      render: () => (
      <bk-select
          v-model={selectedValue}
          class="strategy-create-select-item"
          behavior="simplicity"
          input-search={false}
          placeholder={t('请选择')}
          search-placeholder={t('请输入关键字')}
          filterable
        >
        {
          map.map(item => (
          <bk-option
            key={item.id}
            value={item.id}
            label={item.name}
          />
          ))
        }
        </bk-select>
      ),
    },
  ];
  const map = [
    {
      id: 1,
      name: '字段一',
    },
    {
      id: 2,
      name: '字段二',
    },
    {
      id: 3,
      name: '字段三',
    },
  ];
  const diffParamsData = [
    {
      id: 1,
      name: 'parameter1',
      constraint: '<50',
      value: 2,
    },
    {
      id: 2,
      name: 'parameter2',
      constraint: '无约束',
      value: 2,
    },
    {
      id: 3,
      name: 'parameter3',
      constraint: '<20',
      value: 4344,
    },
  ];
  const selectedValue = ref();
  const handleDiff = (value: string) => {
    emits('updateDiff', value);
  };
</script>
<style lang="postcss">
.diff-condition {
  .bk-table .bk-table-head table th .cell {
    color: #313238;
  }

  .params-type {
    display: inline-block;
    padding: 0 10px;
    line-height: 21px;
    color: #3a84ff;
    background: #e1ecff;
    border-radius: 10px;
  }

  .strategy-create-select-item {
    margin: 0 -15px;
    border-bottom: 0;

    .bk-input {
      height: 41px;
      border-bottom: 0;
    }
  }
}
</style>
