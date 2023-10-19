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
  <div class="preview-result-collsapn">
    <div
      class="title"
      @click="handleToggle">
      <audit-icon
        class="arrow-flag"
        :class="{'is-show': isShow}"
        type="angle-line-down" />
      <slot name="title" />
    </div>
    <div
      v-if="isShow"
      class="content">
      <slot />
    </div>
    <div class="action">
      <slot name="action" />
    </div>
  </div>
</template>
<script setup lang="ts">
  import { ref } from 'vue';

  const isShow = ref(true);

  const handleToggle = () => {
    isShow.value = !isShow.value;
  };
</script>
<style lang="postcss" scoped>
.preview-result-collsapn {
  position: relative;
  user-select: none;

  .title {
    display: flex;
    height: 34px;
    padding: 0 24px;
    font-size: 12px;
    color: #63656e;
    cursor: pointer;
    align-items: center;

    .arrow-flag {
      margin-right: 4px;
      transform: rotateZ(-90deg);
      transition: all 0.15s;

      &.is-show {
        transform: rotateZ(0);
      }
    }
  }

  .content {
    max-height: 476px;
    padding: 0 24px;
    overflow-y: auto;
  }

  .action {
    position: absolute;
    top: 4px;
    right: 0;
    margin-left: auto;
    cursor: pointer;
  }
}
</style>
