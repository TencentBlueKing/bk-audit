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
  <span ref="rootRef">
    <slot />
  </span>
  <div style="display: none;">
    <div
      ref="popRef"
      class="analysis-row-popover"
      :style="{ width: `${width}px` }">
      <slot name="content" />
    </div>
  </div>
</template>
<script setup lang="ts">
  import tippy, {
    type Instance,
    type SingleTarget,
  } from 'tippy.js';
  import {
    onBeforeUnmount,
    onMounted,
    ref,
  } from 'vue';

  interface Props {
    width: number,
  }
  interface Emits {
    (e: 'afterShow'): void;
  }
  interface Exposes{
    hide:()=>void
  }
  defineProps<Props>();
  const emits = defineEmits<Emits>();

  let tippyIns: Instance;

  const rootRef = ref();
  const popRef = ref();


  onMounted(() => {
    const tippyTarget = rootRef.value;
    if (tippyTarget) {
      tippyIns = tippy(tippyTarget as SingleTarget, {
        content: popRef.value,
        placement: 'right',
        appendTo: () => document.body,
        theme: 'light',
        maxWidth: 'none',
        trigger: 'mouseenter',
        interactive: true,
        delay: 300,
        arrow: true,
        offset: [0, 8],
        zIndex: 99999,
        hideOnClick: false,
        onCreate(instance) {
          instance.popper.classList.add('analysis-desc-popper');
        },
        onShow() {
          emits('afterShow');
        },
      });
    }
  });

  onBeforeUnmount(() => {
    tippyIns.hide();
    tippyIns.unmount();
    tippyIns.destroy();
  });
  defineExpose<Exposes>({
    hide() {
      tippyIns.hide();
    },
  });
</script>
<style lang="postcss">
  .analysis-desc-popper .tippy-box[data-theme~='light'] {
    color: var(--bk-theme-text-strong);
    background-color: var(--bk-theme-surface-default);
    border-radius: var(--bk-theme-overlay-radius);
    box-shadow: var(--bk-theme-card-shadow);
  }

  .analysis-desc-popper .tippy-box[data-theme~='light'] > .tippy-arrow::before {
    border-right-color: var(--bk-theme-surface-default);
    border-left-color: var(--bk-theme-surface-default);
  }

  .analysis-desc-popper .tippy-content {
    padding: 0;
  }

  .analysis-row-popover {
    padding: var(--bk-theme-space-12) var(--bk-theme-space-16);
    font-size: var(--bk-theme-font-size-sm);
    line-height: var(--bk-theme-line-height-sm);

    .hover-table {
      padding: 0;

      .hover-table-content {
        width: 100%;
      }

      .hover-table-title {
        width: 84px;
        padding: var(--bk-theme-space-4) 0;
        color: var(--bk-theme-text-weak);
        text-align: right;
        vertical-align: top;
        background-color: transparent;
      }

      .hover-table-value {
        position: relative;
        padding: var(--bk-theme-space-4) 0 var(--bk-theme-space-4) var(--bk-theme-space-8);
        color: var(--bk-theme-text-strong);
        word-break: break-all;

        a {
          color: var(--bk-theme-color-brand-2);
        }

        .max-line-clamp {
          display: -webkit-box;
          overflow: hidden;
          -webkit-box-orient: vertical;
          -webkit-line-clamp: 6; /* 将行数设置为6行 */
        }

        .copy-btn {
          position: absolute;
          right: 0;
          bottom: var(--bk-theme-space-4);
          cursor: pointer;

          &:hover {
            color: var(--bk-theme-color-brand-2);
          }
        }
      }

      .hover-table-content tr td {
        height: auto;
        border: none;
      }
    }
  }
</style>
