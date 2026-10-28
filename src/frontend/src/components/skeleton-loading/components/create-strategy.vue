<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed on an
  "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
  either express or implied. See the License for the
  specific language governing permissions and limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
-->
<template>
  <div>
    <content-loader
      :height="layout.height"
      :width="maxWidth"
      v-bind="attrs">
      <rect
        v-for="(block, index) in layout.blocks"
        :key="index"
        :height="block.height"
        rx="2"
        :width="block.width"
        :x="block.x"
        :y="block.y" />
    </content-loader>
  </div>
</template>
<script lang="ts">
  export default {
    inheritAttrs: true,
  };
</script>
<script setup lang="ts">
  import { computed, useAttrs } from 'vue';
  import { ContentLoader } from 'vue-content-loader';

  import { attrsOnlyProp } from '@utils/assist';

  interface Props {
    maxWidth: number;
  }
  interface Block {
    x: number;
    y: number;
    width: number;
    height: number;
  }

  const props = defineProps<Props>();
  const attrs = attrsOnlyProp(useAttrs());

  // 对齐基础信息步：基础信息（名称+标签、描述）和方案（两个配置方式、数据源占位）
  const layout = computed(() => {
    const full = Math.max(props.maxWidth, 360);
    const gap = 16;
    const columnWidth = (full - gap) / 2;
    const fieldWidth = Math.min(624, full);
    const blocks: Block[] = [];
    let y = 16;

    const push = (x: number, height: number, width: number) => {
      blocks.push({
        x,
        y,
        width,
        height,
      });
    };

    push(0, 16, 72);
    y += 32;
    push(0, 14, 64);
    push(columnWidth + gap, 14, 32);
    y += 22;
    push(0, 32, columnWidth);
    push(columnWidth + gap, 32, columnWidth);
    y += 56;
    push(0, 14, 32);
    y += 22;
    push(0, 64, fieldWidth);
    y += 96;

    push(0, 16, 40);
    y += 32;
    push(0, 14, 64);
    y += 22;
    push(0, 48, 200);
    push(216, 48, 200);
    y += 72;
    push(0, 14, 48);
    y += 22;
    push(0, 32, fieldWidth);
    y += 56;
    push(0, 14, 64);
    y += 22;
    push(0, 96, fieldWidth);

    return {
      height: y + 120,
      blocks,
    };
  });
</script>
