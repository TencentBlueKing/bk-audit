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
  <bk-popover
    placement="bottom"
    theme="light"
    trigger="click">
    <div class="collspan-box-extend-btn">
      <audit-icon type="more" />
    </div>
    <template #content>
      <div class="collspan-box-extend-action">
        <slot />
      </div>
    </template>
  </bk-popover>
</template>
<script setup lang="ts">

</script>
<style lang="postcss">
  .collspan-box-extend-btn {
    display: flex;
    width: 24px;
    height: 24px;
    cursor: pointer;
    border-radius: 50%;
    align-items: center;
    justify-content: center;
    transition: all .15s;

    &:hover {
      background: #dcdee5;
    }
  }

  .collspan-box-extend-action {
    margin: 0 -14px;

    & > * {
      height: 32px;
      padding: 0 12px;
      line-height: 32px;
      cursor: pointer;

      &:hover {
        color: #3a84ff;
        background: #f5f6fa;
      }
    }
  }
</style>
