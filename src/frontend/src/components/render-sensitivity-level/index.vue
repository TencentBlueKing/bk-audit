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
  <div
    class="render-sensitivity-level"
    :style="styles">
    {{ value }}
  </div>
</template>
<script setup lang="ts">
  import { computed } from 'vue';

  interface Props{
    value: number
  }
  const props = defineProps<Props>();

  const styles = computed(() => {
    if (props.value >= 7) {
      return {
        background: '#EA3636',
      };
    }
    if (props.value >= 3) {
      return {
        background: '#FF9C01',
      };
    }
    return {
      background: '#DCDEE5',
    };
  });
</script>
<style lang="postcss">
  .render-sensitivity-level {
    display: inline-block;
    width: 20px;
    height: 16px;
    font-weight: bold;
    line-height: 16px;
    color: #fff;
    text-align: center;
    border-radius: 2px;
  }
</style>
