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
    ref="problemRef"
    class="problems-box"
    :style="{height: problemHeight+'px'}">
    <div
      class="problems-drag"
      @mousedown="handleMouseDown" />
    <div class="problem">
      <div
        v-for="(item, index) in problems"
        :key="index"
        class="problem-item">
        <audit-icon
          style="padding-top: 3px;color: #b34747;"
          type="delete-fill" />
        <span
          class="ml8"
          style="line-height: 20px;">{{ item }}</span>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import {
    onBeforeUnmount,
    onMounted,
    ref,
  } from 'vue';

  interface Props {
    problems: Array<string>,
  }
  defineProps<Props>();
  const problemHeight = ref();

  // 拖动problems事件
  const handleMouseUp = () => {
    document.removeEventListener('mousemove', handleMouseMove);
  };
  const handleMouseMove = (event: MouseEvent) => {
    problemHeight.value = document.body.clientHeight - event.clientY - 105;
  };
  const handleMouseDown = () => {
    document.addEventListener('mousemove', handleMouseMove);
  };

  onMounted(() => {
    document.addEventListener('mouseup', handleMouseUp);
  });

  onBeforeUnmount(() => {
    document.removeEventListener('mouseup', handleMouseUp);
  });
</script>
<style lang="postcss">
  .problems-box {
    position: absolute;
    bottom: 0;
    z-index: 999;
    width: 100%;
    max-height: 500px;
    padding: 6px 20px;
    overflow-y: auto;
    background: #212121;
    border-left: 4px solid #b34747;

    .problems-drag {
      position: sticky;
      left: calc(50% - 13px);
      z-index: 100;
      display: flex;
      width: 26px;
      height: 6px;
      cursor: ns-resize;
      border-radius: 3px;
      transform: translateY(-50%);
      align-items: center;
      justify-content: center;
    }

    .problems-drag:hover {
      cursor: ns-resize;
    }

    .problems-drag::after {
      position: absolute;
      left: 2px;
      width: 100%;
      height: 0;
      border-bottom: 3px dotted #63656e;
      content: ' ';
    }

    .problem {
      padding: 6px 0;

      .problem-item {
        display: flex;
        color: #fff;
      }
    }
  }
</style>
