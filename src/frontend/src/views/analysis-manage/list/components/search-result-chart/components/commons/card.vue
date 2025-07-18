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
  <div class="card">
    <div class="card-title">
      {{ title }}
    </div>
    <div>
      <slot />
    </div>
  </div>
</template>
<script setup lang="ts">
  defineProps({
    title: {
      type: String,
      required: true,
    },
  });
</script>
<style scoped lang="postcss">
  .card {
    padding: 17px 24px;
    background: #fff;
    border-radius: 2px;
    box-shadow: 0 2px 4px 0 rgb(25 25 41 / 5%);

    .card-title {
      font-size: 14px;
      line-height: 22px;
      color: #313238;
    }
  }
</style>
