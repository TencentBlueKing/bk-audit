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
  <div class="render-field-map">
    <render-standard-field
      ref="standardFieldRef"
      v-model="localFieldMap"
      :data="data" />
    <!-- <render-alternative-field
      :data="data"
      :related-field-map="fieldMap" /> -->
  </div>
</template>
<script setup lang="ts">
  import {
    computed,
    ref,
  } from 'vue';

  import type EtlPreviewModel from '@model/collector/etl-preview';
  import type StandardField from '@model/meta/standard-field';

  // import RenderAlternativeField from './alternative-field.vue';
  import RenderStandardField from './standard-field.vue';

  type TFieldMap = Record<string, string>

  interface Props {
    data: Array<EtlPreviewModel>,
    fieldMap: TFieldMap,
  }

  interface Emits {
    (e: 'update:fieldMap', value: TFieldMap): void
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const standardFieldRef = ref();

  const localFieldMap = computed({
    get: () => props.fieldMap,
    set: (value) => {
      emit('update:fieldMap', value);
    },
  });

  defineExpose({
    getValue(): Promise<Array<StandardField>> {
      return standardFieldRef.value.getValue();
    },
    // 点击调试清空调试字段
    clearFiledDebug() {
      return standardFieldRef.value.clearFiledDebug();
    },
    getFieldHistory() {
      return standardFieldRef.value.getFieldHistory();
    },
  });
</script>
<style lang="postcss" scoped>
  .render-field-map {
    display: flex;
    width: 100%;
  }
</style>
