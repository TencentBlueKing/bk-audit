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
    ref="rootRef"
    class="show-tooltips-text"
    :style="{ '--line-clamp': String(line) }">
    <span>
      {{ data || '--' }}
    </span>
    <div
      ref="templateRef"
      style="display: none;max-height: 90vh;overflow: auto;">
      <div style="max-height: 90vh;overflow: auto;word-break: break-all;white-space: pre-wrap;">
        {{ data }}
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import tippy, {
    type Instance,
    type Placement,
    type SingleTarget,
  } from 'tippy.js';
  import {
    nextTick,
    onBeforeUnmount,
    ref,
    watch,
  } from 'vue';

  interface Props {
    data: string | number,
    theme?: string,
    placement?: Placement,
    isShow?: boolean,
    maxWidth?: string | number,
    line?: number,  // 新增行数控制属性
  }

  const props = withDefaults(defineProps<Props>(), {
    theme: 'dark',
    placement: 'top',
    isShow: true,
    maxWidth: 'none',
    line: 1,  // 默认一行
  });

  const rootRef = ref<HTMLElement | null>(null);
  const templateRef = ref<HTMLElement | null>(null);

  let tippyIns: Instance;

  watch(() => props.data, () => {
    nextTick(() => {
      if (tippyIns) {
        tippyIns.hide();
        tippyIns.destroy();
      }
      const template = templateRef.value;
      if (handleIsShowTippy() && template && props.isShow) {
        tippyIns = tippy(rootRef.value as SingleTarget, {
          content: template.innerHTML,
          placement: props.placement as Placement || 'top',
          allowHTML: true,
          appendTo: () => document.body,
          theme: props.theme || 'dark',
          maxWidth: props.maxWidth || 'none',
          interactive: true,
          arrow: true,
          offset: [0, 8],
          zIndex: 999999,
          hideOnClick: true,
        });
      }
    });
  }, {
    deep: true,
    immediate: true,
  });
  // 当文本溢出省略号则hover显示全部内容
  const handleIsShowTippy = () => {
    if (!rootRef.value) {
      return false;
    }
    const { clientWidth, clientHeight } = rootRef.value;
    const { scrollWidth, scrollHeight } = rootRef.value;
    // 多行溢出判断：宽度或高度超出都显示tooltip
    if (scrollWidth > clientWidth || scrollHeight > clientHeight) {
      return true;
    }
    return false;
  };
  onBeforeUnmount(() => {
    if (tippyIns) {
      tippyIns.hide();
      tippyIns.unmount();
      tippyIns.destroy();
    }
  });
</script>
<style lang="postcss">
  .show-tooltips-text {
    display: -webkit-box;
    overflow: hidden;
    word-break: break-all;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: var(--line-clamp);
  }

  .text-content {
    word-break: break-all;
    white-space: pre-wrap;
  }
</style>
