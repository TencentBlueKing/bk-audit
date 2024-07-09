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
  <div class="page-title">
    <slot name="header" />
  </div>
</template>
<script setup lang="ts">
  import { onMounted } from 'vue';

  interface Emits {
    (e: 'isMounted'): void
  }
  const emit = defineEmits<Emits>();

  onMounted(() => {
    emit('isMounted');
  });
</script>
<style scoped lang="postcss">
  .page-title {
    /* 解决投影被遮挡问题 */
    position: relative;
    z-index: 1;
    display: flex;
    height: 52px;
    padding: 0 20px;
    margin-left: 1px;
    font-size: 16px;
    line-height: 52px;
    color: #313238;
    background: #fff;
    transform: translate3d(0, 0, 0);

    /* box-shadow: 0 1px 0 0 #eaebf0; */
    box-shadow: 0 2px 4px 0 rgb(25 25 41 / 5%);
    align-items: center;
  }
</style>
