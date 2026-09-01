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
    :class="{ 'single-line': line === 1 }"
    :style="line !== 1 ? {
      '-webkit-line-clamp': line,
      'line-clamp': line,
    } : {}">
    <span>
      {{ data || '--' }}
    </span>
    <div
      ref="templateRef"
      style="display: none;">
      <div
        class="show-tooltips-text-template"
        :class="tooltipContentClass"
        :style="tooltipContentStyle">
        {{ props.tip || data }}
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
    computed,
    nextTick,
    onBeforeUnmount,
    onMounted,
    ref,
    watch,
  } from 'vue';

  interface Props {
    data: string | number,
    theme?: string,
    placement?: Placement,
    isShow?: boolean,
    maxWidth?: string | number,
    /** tooltip 内容区最大高度，超出滚动 */
    tooltipMaxHeight?: string,
    /** tooltip 内容区额外 class，用于定制滚动条等样式 */
    tooltipContentClass?: string,
    line?: number,  // 行数控制属性
    tip?: string,   // 自定义 tooltip 提示内容（有值时 tooltip 显示此内容，不影响文本溢出判断）
  }

  const props = withDefaults(defineProps<Props>(), {
    theme: 'dark',
    placement: 'top',
    isShow: true,
    maxWidth: 'none',
    tooltipMaxHeight: '90vh',
    tooltipContentClass: '',
    line: 1,
    tip: '',
  });

  const tooltipContentStyle = computed(() => ({
    maxHeight: props.tooltipMaxHeight,
    overflow: 'auto',
    wordBreak: 'break-all',
    whiteSpace: 'pre-wrap',
  }));

  const rootRef = ref();
  const templateRef = ref<HTMLElement | null>(null);

  let tippyIns: Instance;
  let resizeObserver: ResizeObserver | null = null;

  const initTippy = () => {
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
  };

  watch(() => [props.data, props.maxWidth, props.tooltipMaxHeight, props.tooltipContentClass], () => {
    initTippy();
  }, {
    deep: true,
    immediate: true,
  });
  onMounted(() => {
    if (rootRef.value && typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(() => {
        initTippy();
      });
      resizeObserver.observe(rootRef.value);
    }
  });
  // 当文本溢出省略号或有自定义 tip 时 hover 显示提示
  const handleIsShowTippy = () => {
    // 有自定义 tip 时始终显示
    if (props.tip) {
      return true;
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
    if (resizeObserver && rootRef.value) {
      resizeObserver.unobserve(rootRef.value);
      resizeObserver.disconnect();
    }
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

    &.single-line {
      display: block;
      text-overflow: ellipsis;
      word-break: normal;
      white-space: nowrap;
    }
  }

  .text-content {
    word-break: break-all;
    white-space: pre-wrap;
  }

  /* tooltip 弹出层：窄滚动条 + 透明轨道（tippy append 到 body，需全局样式） */
  .show-tooltips-text-popup {
    scrollbar-width: thin;
    scrollbar-color: rgb(255 255 255 / 35%) transparent;

    &::-webkit-scrollbar {
      width: 4px;
      height: 4px;
    }

    &::-webkit-scrollbar-track {
      background: transparent;
    }

    &::-webkit-scrollbar-thumb {
      background: rgb(255 255 255 / 35%);
      border-radius: 4px;
    }

    &::-webkit-scrollbar-thumb:hover {
      background: rgb(255 255 255 / 55%);
    }
  }
</style>
