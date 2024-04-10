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
  <component
    :is="renderComponent"
    :data="modelValue"
    @change="handleChange" />
</template>
<script setup lang="ts">
  import { computed } from 'vue';

  import RenderMatch from './components/render-match.vue';
  import RenderNone from './components/render-none.vue';
  import RenderSeparator from './components/render-separator.vue';

  interface Props {
    modelValue: {
      type: string,
      match_type: string,
      match_content: string,
      separator: string,
      separator_filters: Array<Record<'logic_op'|'fieldindex'|'word', string>>
    }
  }
  interface Emits {
    (e: 'change', value:  Props['modelValue']):void;
    (e: 'update:modelValue', value:  Props['modelValue']): void,
  }

  const props = defineProps<Props>();

  const emits = defineEmits<Emits>();
  const comMap = {
    match: RenderMatch,
    separator: RenderSeparator,
    none: RenderNone,
  };

  const renderComponent = computed(() => comMap[props.modelValue.type as keyof typeof comMap]);

  const handleChange = (value: Props['modelValue']) => {
    emits('change', value);
    emits('update:modelValue', value);
  };
</script>
