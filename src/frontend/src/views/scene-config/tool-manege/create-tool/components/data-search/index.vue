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
  <card-part-vue :title="t('工具配置页面')">
    <template #content>
      <component
        :is="modelComMap[dataSearchConfigType]"
        ref="comRef"
        :name="name"
        :uid="uid" />
    </template>
  </card-part-vue>
</template>
<script setup lang='tsx'>
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import CardPartVue from '../card-part.vue';

  import SimpleModel from './simple-model/index.vue';
  import SqlModel from './sql-model/index.vue';

  interface Props {
    dataSearchConfigType: string,
    name: string,
    uid: string
  }

  interface Config {
    referenced_tables: Array<{
      table_name: string | null;
      alias: string | null;
      permission: {
        result: boolean;
      };
    }>;
    input_variable: Array<{
      raw_name: string;
      display_name: string;
      description: string;
      required: boolean;
      field_category: string;
      default_value: string | Array<string>;
      choices: Array<{
        key: string,
        name: string
      }>
    }>
    output_fields: Array<{
      raw_name: string;
      display_name: string;
      description: string;
      drill_config: Array<{
        tool: {
          uid: string;
          version: number;
        };
        drill_name: string;
        config: Array<{
          source_field: string;
          target_value_type: string;
          target_value: string;
        }>
      }>;
      enum_mappings: {
        collection_id: string;
        mappings: Array<{
          key: string;
          name: string;
        }>;
      };
    }>
    sql: string;
    uid: string;
  }

  interface Exposes {
    getValue: () => Promise<any>;
    setConfigs: (data: Config) => void;
    getFields: () => Config;
  }

  defineProps<Props>();
  const { t } = useI18n();

  const comRef = ref();

  const modelComMap: Record<string, any> = {
    simple: SimpleModel,
    sql: SqlModel,
  };

  defineExpose<Exposes>({
    getValue() {
      return comRef.value.getValue();
    },
    setConfigs(configs: Config) {
      comRef.value.setConfigs(configs);
    },
    getFields() {
      return comRef.value.getFields();
    },
  });
</script>
