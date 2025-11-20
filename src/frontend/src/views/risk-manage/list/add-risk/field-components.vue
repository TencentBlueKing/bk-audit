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
      v-if="type === 'textarea'"
      v-model="inputValue"
      :resize="false"
      style="width: 232px;height: 100%"
      type="textarea" />
    <bk-input
      v-if="type === 'number-input'"
      v-model="numberValue"
      style="width: 232px;height: 100%"
      type="number" />
    <bk-input
      v-if="type === 'input'"
      v-model="inputValue"
      style="width: 232px;height: 42px"
      type="input" />
    <audit-user-selector
      v-if="type === 'user-selector'"
      v-model="userValue"
      allow-create
      :auto-focus="false"
      class="user-selector" />
    <bk-date-picker
      v-if="type === 'date-picker'"
      v-model="timeValue"
      append-to-body
      clearable
      style="width: 232px;height: 100%"
      type="datetime" />
  </div>
</template>


<script setup lang='ts'>
  import { ref } from 'vue';

  interface Props {
    type: string;
  }
  defineProps<Props>();

  const inputValue = ref('');
  const numberValue = ref(0);
  const userValue = ref([]);
  const timeValue = ref('');
</script>

<style>
.user-selector {
  width: 232px;
}
</style>
