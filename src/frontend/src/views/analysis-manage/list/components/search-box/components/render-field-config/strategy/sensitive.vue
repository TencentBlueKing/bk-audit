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
  {{ config.label }}
  <bk-select
    filterable
    :input-search="false"
    :model-value="modelValue"
    multiple
    :placeholder="`请选择${config.label}`"
    @change="handleChange">
    <bk-option
      label="0"
      value="0" />
    <bk-option
      v-for="item in 9"
      :key="item"
      :label="`${item}`"
      :value="item" />
  </bk-select>
</template>
<script setup lang="ts">
  import { useI18n } from 'vue-i18n';

  import type { IFieldConfig } from '../config';
  import useMultiCommon from '../hooks/use-multi-common';

  interface Props {
    config: IFieldConfig,
    // eslint-disable-next-line vue/no-unused-properties
    name: string,
    // eslint-disable-next-line vue/no-unused-properties
    model: Record<string, any>
  }
  interface Emits {
    (e: 'change', name: string, value: Array<string>): void
  }
  interface Exposes {
    getValue: ()=> Promise<Record<string, any>|string>
  }
  const props = defineProps<Props>();
  defineEmits<Emits>();
  const { t } = useI18n();
  const {
    modelValue,
    handleChange,
  } = useMultiCommon(props, t('全部'));

  defineExpose<Exposes>({
    getValue() {
      if (props.config.validator && !props.config.validator(modelValue)) {
        return Promise.reject(`${props.name} error`);
      }
      return Promise.resolve({
        [props.name]: modelValue,
      });
    },
  });
</script>
