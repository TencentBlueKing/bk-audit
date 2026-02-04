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
  <audit-user-selector-tenant
    allow-create
    :model-value="defaultValue"
    :multiple="multiple"
    need-record
    :placeholder="t(`请选择${config.label}`)"
    @change="(value: any) => handleChange(value)" />
</template>
<script lang="ts">
  export default {
    inheritAttrs: true,
  };
</script>
<script setup lang="ts">
  import { useI18n } from 'vue-i18n';

  import AuditUserSelectorTenant from '@components/audit-user-selector-tenant/index.vue';

  import type { IFieldConfig } from '../config';

  interface Props {
    config: IFieldConfig,
    defaultValue?: Array<string>|string,
    name: string,
  }
  interface Emits {
    (e: 'change', name: string, value: Props['defaultValue']): void
  }
  interface Exposes {
    getValue: ()=> Promise<Record<string, any>|string>
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const multiple = true;

  const handleChange = (value: Props['defaultValue']) => {
    emits('change', props.name, value);
  };

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
