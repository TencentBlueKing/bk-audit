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
    class="audit-edit-tag">
    <template v-if="data && data.length">
      <bk-tag
        v-for="(item) in renderData"
        :key="item"
        style="width: auto;">
        <tool-tip-text :data="item " />
      </bk-tag>
      <bk-tag
        v-if="moreDataText"
        key="more"
        ref="moreRef">
        +{{ data.length - renderData.length }}
      </bk-tag>
      <div
        v-if="showCopy"
        v-bk-tooltips="t('复制所有')"
        class="copy-btn"
        @click.stop="handleCopy">
        <audit-icon type="copy" />
      </div>
    </template>
    <span v-else>--</span>
    <teleport to="body">
      <div
        v-if="isCalcRenderTagNum"
        style="position: absolute; word-break: keep-all; white-space: nowrap; visibility: hidden;">
        <bk-tag
          v-for="item in data"
          :key="item"
          ref="tagElsRef">
          {{ item }}
        </bk-tag>
      </div>
    </teleport>
  </div>
</template>
<script setup lang="ts">
  import { throttle } from 'lodash';
  import tippy, {
    type Instance,
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
  import { useI18n } from 'vue-i18n';

  import { execCopy } from '@utils/assist';

  import ToolTipText from '@/components/show-tooltips-text/index.vue';

  interface Props {
    data: Array<string>,
    max?: number,
    showCopy?: boolean
  }

  const props = withDefaults(defineProps<Props>(), {
    max: 0,
    showCopy: true,
  });

  const { t } = useI18n();
  const rootRef = ref();
  const moreRef = ref();
  const tagElsRef = ref();
  const renderTagNum = ref(1);
  const isCalcRenderTagNum = ref(false);

  const renderData = computed(() => props.data.slice(0, renderTagNum.value));

  const moreDataText = computed(() => {
    if (props.data.length < 1
      || props.data.length <= renderTagNum.value) {
      return '';
    }
    return props.data.slice(renderTagNum.value).join(',');
  });

  let tippyIns: Instance;

  const calcRenderTagNum = () => {
    if (props.max && props.max > 0) {
      renderTagNum.value = props.max;
      return;
    }
    if (!rootRef.value || props.data.length < 1) {
      return;
    }
    isCalcRenderTagNum.value = true;
    nextTick(() => {
      const {
        width: boxWidth,
      } = rootRef.value.getBoundingClientRect();

      const {
        width: tagWidth,
      } = tagElsRef.value[0].$el.getBoundingClientRect();
      let totalTagWidth = tagWidth;
      renderTagNum.value = 1;   // 最少展示一个

      const numTagWidth = 50;
      const copyBtnWidth = 20;
      for (let i = 1; i < tagElsRef.value.length; i++) {
        const {
          width: tagWidth,
        } = tagElsRef.value[i].$el.getBoundingClientRect();
        totalTagWidth += tagWidth;
        if (totalTagWidth + numTagWidth + copyBtnWidth  < boxWidth) {
          renderTagNum.value = renderTagNum.value + 1;
        } else {
          break;
        }
      }
      isCalcRenderTagNum.value = false;
    });
  };


  watch(() => props.data, () => {
    nextTick(() => {
      calcRenderTagNum();
    });
  }, {
    deep: true,
  });
  watch(moreDataText, () => {
    if (!moreDataText.value) {
      return;
    }
    if (tippyIns) {
      tippyIns.hide();
      tippyIns.unmount();
      tippyIns.destroy();
    }
    nextTick(() => {
      tippyIns = tippy(moreRef.value.$el as SingleTarget, {
        content: `<div style="max-width: 300px; word-break: break-all;">${moreDataText.value}</div>`,
        placement: 'top',
        allowHTML: true,
        appendTo: () => document.body,
        theme: 'dark',
        interactive: true,
        arrow: true,
        offset: [0, 8],
        zIndex: 999999,
        hideOnClick: true,
        trigger: 'mouseenter',
      });
    });
  }, {
    deep: true,
    immediate: true,
  });

  const handleCopy = () => {
    execCopy(props.data.join('\n'), t('复制成功'));
  };
  // 动态设置标签宽度
  const dynamicCalcWidth = () => {
    const maxWidth = rootRef.value.parentNode.clientWidth - 30;
    const gapWidth = 6;
    const copyTipWidth = 25;
    const tags:Array<HTMLElement> = rootRef.value.getElementsByClassName('bk-tag');

    let allWidth = 0;
    Array.from(tags).forEach((t: HTMLElement) => {
      allWidth = allWidth + t.clientWidth;
    });
    allWidth = allWidth + (tags.length - 1) * gapWidth + copyTipWidth;
    let averageWidth;
    if (allWidth > maxWidth) {
      averageWidth = (maxWidth - (copyTipWidth + (tags.length - 1) * gapWidth)) / tags.length;
      for (let i = 0; i < tags.length; i++) {
        if (tags[i].clientWidth > averageWidth) {
          tags[i].style.width =  `${Math.max(averageWidth, 35)}px`;
        }
      }
    }
  };
  let resizeObserver: any;
  onMounted(() => {
    calcRenderTagNum();
    setTimeout(() => {
      dynamicCalcWidth();
    });

    const resizeObserver = new ResizeObserver(throttle(() => {
      calcRenderTagNum();
    }));
    resizeObserver.observe(rootRef.value);
  });

  onBeforeUnmount(() => {
    if (tippyIns) {
      tippyIns.hide();
      tippyIns.unmount();
      tippyIns.destroy();
    }
    resizeObserver?.disconnect();
  });
</script>
<style scoped lang="postcss">
  .audit-edit-tag {
    position: relative;
    display: block;
    word-break: keep-all;
    white-space: nowrap;

    .label-text {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    &:hover {
      .copy-btn {
        opacity: 100%;
      }
    }

    .bk-tag {
      margin-right: 0;
      margin-left: 0;

      & ~ .bk-tag {
        margin-left: 6px;
      }
    }

    .copy-btn {
      display: inline-block;
      padding-left: 8px;
      cursor: pointer;
      opacity: 0%;

      &:hover {
        color: #3a84ff;
      }
    }
  }

  :deep(.bk-tag) {
    width: auto !important;
    margin-right: 0;
  }
</style>
