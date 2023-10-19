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
  .analysis-row-popover {
    font-size: 12px;

    .hover-table {
      padding: 11px 2px;

      .hover-table-content {
        width: 100%;
      }

      .hover-table-title {
        color: #979ba5;
        text-align: center;
        background-color: #fafbfd;
      }

      .hover-table-value {
        position: relative;
        padding: 5px 12px;
        color: #63656e;
        word-break: break-all;

        .max-line-clamp{
          display: -webkit-box;
          overflow: hidden;
          -webkit-box-orient: vertical;
          -webkit-line-clamp: 6; /* 将行数设置为6行 */
        }

        .copy-btn {
          position: absolute;
          right: 12px;
          bottom:5px;
          cursor: pointer;

          &:hover {
            color: #3a84ff;
          }
        }
      }

      .hover-table-content tr td {
        height: 36px;
        border-top: 1px solid #dcdee5;
        border-right: 1px solid #dcdee5;
        border-left: 1px solid #dcdee5;
      }

      .hover-table-content tr .border-left-none {
        border-left: none;
      }

      .hover-table-content tr .border-bottom {
        border-bottom: 1px solid #dcdee5;
      }

      .hover-table-content tr:last-child td {
        border-bottom: 1px solid #dcdee5;
      }
    }
  }
</style>
