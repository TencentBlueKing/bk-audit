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
    class="show-tooltips-text">
    <span>
      {{ data || '--' }}
    </span>
    <div
      :id="`${data}`"
      style="display: none;">
      <div style="max-width: 300px; word-break: break-all;">
        {{ data }}
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import tippy, {
    type Instance,
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
    placement?: string,
    isShow?: boolean,
  }

  const props = withDefaults(defineProps<Props>(), {
    theme: 'dark',
    placement: 'top',
    isShow: true,
  });

  const rootRef = ref();

  let tippyIns: Instance;

  watch(() => props.data, (data) => {
    nextTick(() => {
      const template = document.getElementById(`${data}`);
      if (hanldeIsShowTippy() && template && props.isShow) {
        tippyIns = tippy(rootRef.value as SingleTarget, {
          content: template.innerHTML,
          placement: props.placement || 'top',
          allowHTML: true,
          appendTo: () => document.body,
          theme: props.theme || 'dark',
          maxWidth: 'none',
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
  const hanldeIsShowTippy = () => {
    const { clientWidth } = rootRef.value;
    const { scrollWidth } = rootRef.value;
    if (scrollWidth > clientWidth) {
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
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
