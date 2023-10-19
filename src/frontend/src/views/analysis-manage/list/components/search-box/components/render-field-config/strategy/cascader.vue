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
  <div>
    <bk-cascader
      v-model="value"
      check-any-level
      clearable
      filterable
      limit-one-line
      :list="data"
      multiple
      :show-complete-name="false"
      style="width: 100% ;" />
  </div>
</template>
<script setup lang="ts">
  import { ref } from 'vue';

  import type { IFieldConfig } from '../config';

  interface Exposes {
    getValue: ()=> Promise<Record<string, any>|string>
  }
  interface Props {
    config: IFieldConfig,
    defaultValue?: string,
    name: string,
  }
  const props = defineProps<Props>();
  const data =  [
    {
      id: 'vrmp',
      name: 'VRMP',
      children: [
        {
          id: 'contract',
          name: '合同数据',
        },
        {
          id: 'financial',
          name: '财务数据',
        },
        {
          id: 'financial_ip',
          name: '财务IP',
        },
        {
          id: 'import_ip',
          name: 'IP引入清单',
        },
        {
          id: 'ip',
          name: 'IP',
        },
        {
          id: 'ip_import_project',
          name: 'IP引入项目',
        },
        {
          id: 'ip_import_project_sensitive',
          name: 'IP引入项目-敏感',
        },
        {
          id: 'ip_product',
          name: 'IP产品',
        },
        {
          id: 'product',
          name: '产品信息',
        },
      ],
    },
    {
      id: 'oao-assessment',
      name: 'OAOCC测试',
      children: [
        {
          id: 'host',
          name: '主机',
        },
      ],
    },
    {
      id: 'bksam',
      name: '账号权限管理系统',
      children: [
        {
          id: 'biz',
          name: '业务',
        },
        {
          id: 'biz_account',
          name: '业务登录账号',
        },
        {
          id: 'host',
          name: '主机IP',
        },
        {
          id: 'module',
          name: '模块',
        },
        {
          id: 'set',
          name: '集群',
        },
      ],
    },
    {
      id: 'bk_sops',
      name: '标准运维',
      children: [
        {
          id: 'clocked_task',
          name: '计划任务',
        },
        {
          id: 'common_flow',
          name: '公共流程',
        },
        {
          id: 'flow',
          name: '流程模板',
        },
        {
          id: 'mini_app',
          name: '轻应用',
        },
        {
          id: 'periodic_task',
          name: '周期任务',
        },
        {
          id: 'project',
          name: '项目',
        },
        {
          id: 'task',
          name: '任务实例',
        },
      ],
    },
  ];
  const value = ref([]);
  defineExpose<Exposes>({
    getValue() {
      if (props.config.validator && !props.config.validator(props.defaultValue)) {
        return Promise.reject(`${props.name} error`);
      }
      return Promise.resolve({
        [props.name]: props.defaultValue,
      });
    },
  });
</script>
<style lang="postcss">
  .root {
    display: block;
  }
</style>
