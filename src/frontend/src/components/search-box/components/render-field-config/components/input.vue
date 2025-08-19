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
    <bk-input
      :model-value="defaultValue"
      :placeholder="t(`请输入${config.label}`)"
      @blur="handleValidator"
      @input="(value: any) => handleChange(value as string)" />
    <p
      v-if="!isErrorMessage"
      style="position: absolute;color: red;">
      {{ t(config.message as string) }}
    </p>
  </div>
</template>
<script lang="ts">
  export default {
    inheritAttrs: true,
  };
</script>
<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type { IFieldConfig } from '../config';

  interface Props {
    config: IFieldConfig,
    defaultValue?: string,
    name: string,
  }
  interface Emits {
    (e: 'change', name: string, value: string): void
  }
  interface Exposes {
    getValue: (fieldValue?: string)=> Promise<Record<string, any>|string>
  }
  const props = defineProps<Props>();

  const emits = defineEmits<Emits>();

  const { t } = useI18n();

  const isErrorMessage = ref(true);

  const handleChange = (value: string) => {
    emits('change', props.name, value);
  };
  const handleValidator = function () {
    if (props.config.validator) {
      isErrorMessage.value = props.config.validator(props.defaultValue);
    }
  };
  defineExpose<Exposes>({
    getValue(fieldValue?: string)  {
      const value = fieldValue || props.defaultValue;
      isErrorMessage.value = props.config.validator ? props.config.validator(value) : true;
      if (props.config.validator && !props.config.validator(value)) {
        return Promise.reject(`${props.name} error`);
      }
      return Promise.resolve({
        [props.name]: value,
      });
    },
  });
</script>
