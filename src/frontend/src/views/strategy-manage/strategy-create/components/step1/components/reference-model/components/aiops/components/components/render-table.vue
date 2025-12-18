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
  <collapse-panel
    class="table-panel"
    :is-active="isActive"
    :label="label"
    style=" margin-bottom: 12px;background: #f0f1f5;">
    <multiple-render-field
      ref="fieldRef"
      :configs="configs"
      :data="data"
      :system-id="systemId"
      :trigger-error="triggerError" />
  </collapse-panel>
</template>
<script setup lang="tsx">
  import {
    ref,
  } from 'vue';

  import CollapsePanel from './collapse-panel.vue';
  import MultipleRenderField from './multiple-render-field.vue';

  interface Props {
    data: Record<string, any>[];
    label: string;
    configs: Record<string, any>[];
    systemId: string;
    triggerError?: boolean;
  }

  interface Exposes {
    getValue: () => void;
    getFields: () => void
  }

  const props = defineProps<Props>();

  const isActive = ref(true);
  const fieldRef = ref();

  defineExpose<Exposes>({
    getValue() {
      return fieldRef.value.getValue();
    },
    getFields() {
      return { [props.systemId]: fieldRef.value.getFields() };
    },
  });
</script>
<style lang="postcss">
  .table-panel {
    .collapse-panel-title {
      color: #63656e;
      background: #eaebf0;
    }
  }
</style>
