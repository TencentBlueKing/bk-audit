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
  <card-part-vue
    v-if="inputVariable.length > 0"
    :title="t('参数配置')"
    :title-description="t('BKVision仪表盘内中可供用户操作的选择器，此处配置为展示的默认值')">
    <template #content>
      <div style="display: flex;width: 100%;">
        <bk-vision-components
          v-for="comItem in inputVariable.filter((item) => item.field_category !== 'variable')"
          :key="comItem.raw_name"
          :config="comItem"
          style="width: 30%;margin-left: 20px;"
          @change="(val: any) => handleVisionChange(val, comItem.raw_name)" />
      </div>
    </template>
  </card-part-vue>
</template>
<script setup lang='tsx'>
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import CardPartVue from '../card-part.vue';

  import bkVisionComponents from './bk-vision-components.vue';

  type InputVariable = Array<{
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

  interface Exposes {
    getValue: () => Promise<any>;
    setConfigs: (configs: InputVariable) => void;
    getFields: () => InputVariable;
  }

  const { t } = useI18n();

  const inputVariable = ref<InputVariable>([]);

  // bk_vision 组件值改动
  const handleVisionChange = (value: any, rawName: string) => {
    inputVariable.value = inputVariable.value.map((item: any) => {
      const reItem = item;
      if (item.raw_name === rawName) {
        reItem.default_value = value;
      }
      return reItem;
    });
  };

  defineExpose<Exposes>({
    getValue() {
      return Promise.resolve();
    },
    setConfigs(configs: InputVariable) {
      inputVariable.value = configs;
    },
    getFields() {
      return inputVariable.value;
    },
  });
</script>
