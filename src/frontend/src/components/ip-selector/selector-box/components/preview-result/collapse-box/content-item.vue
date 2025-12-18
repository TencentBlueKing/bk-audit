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
  <div class="content-item">
    <div class="content-text">
      <slot />
    </div>
    <div
      class="item-remove"
      @click="handleRemove">
      <audit-icon type="close" />
    </div>
  </div>
</template>
<script lang="ts" setup>
  const emits = defineEmits(['remove']);

  const handleRemove = () => {
    emits('remove');
  };
</script>
<style lang="postcss" scoped>
  .content-item {
    display: flex;
    height: 32px;
    padding-left: 12px;
    overflow: hidden;
    font-size: 12px;
    color: #63656e;
    background: #fff;
    border-radius: 2px;
    opacity: 100%;
    transition: all .15s;
    align-items: center;

    &:nth-child(n+2) {
      margin-top: 2px;
    }

    &:hover {
      box-shadow: 0 1px 2px 0 rgb(0 0 0 / 6%);

      .content-text {
        max-width: calc(100% - 56px);
      }

      .item-remove {
        width: 32px;
        opacity: 100%;
      }
    }

    .content-text {
      margin-right: 12px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      direction: rtl;
      flex: 0 1 auto;
      align-items: center;
    }

    .item-remove {
      display: flex;
      width: 0;
      height: 100%;
      margin-left: auto;
      overflow: hidden;
      cursor: pointer;
      opacity: 0%;
      transition: all .15s;
      align-items: center;
      justify-content: center;

      &:hover {
        color: #3a84ff;
      }
    }
  }
</style>
