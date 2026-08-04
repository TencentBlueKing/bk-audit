<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
    10|  software distributed under the License is distributed on
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
    <template v-if="initData && initData.length">
      <div class="audit-edit-tag__main">
        <bk-tag
          v-for="(item) in renderData"
          :key="item"
          class="audit-edit-tag__label"
          @click="handlerClick">
          {{ item }}
        </bk-tag>
        <bk-tag
          v-if="moreDataText"
          key="more"
          ref="moreRef"
          class="audit-edit-tag__more">
          +{{ initData.length - renderData.length }}
        </bk-tag>
      </div>
      <div class="audit-edit-tag__actions">
        <div
          v-if="showCopy"
          v-bk-tooltips="t('复制所有')"
          class="copy-btn"
          @click.stop="handleCopy">
          <audit-icon type="copy" />
        </div>
        <span
          v-if="$slots.suffix"
          class="edit-tag-suffix">
          <slot name="suffix" />
        </span>
      </div>
    </template>
    <template v-else>
      <span>--</span>
      <span
        v-if="$slots.suffix"
        class="edit-tag-suffix">
        <slot name="suffix" />
      </span>
    </template>
    <teleport to="body">
      <div
        v-if="isCalcRenderTagNum"
        style="position: absolute; word-break: keep-all; white-space: nowrap; visibility: hidden;">
        <bk-tag
          v-for="item in initData"
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
    useSlots,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import { execCopy } from '@utils/assist';

  interface Props {
    data: Array<string> | string,
    max?: number,
    showCopy?: boolean
  }
  interface Emits {
    (e: 'click'): void
  }

  const props = withDefaults(defineProps<Props>(), {
    max: 0,
    showCopy: true,
  });
  const emits = defineEmits<Emits>();
  const slots = useSlots();
  const { t } = useI18n();
  const rootRef = ref();
  const moreRef = ref();
  const tagElsRef = ref();
  const renderTagNum = ref(1);
  const isCalcRenderTagNum = ref(false);
  const initData = computed(() =>  {
    // 1. 如果是真正的数组，直接连接
    if (Array.isArray(props.data)) {
      return props.data;
    }
    return   props.data === undefined ? [] : props.data.split(',');
  });
  const renderData = computed(() =>  {
    // 1. 如果是真正的数组，直接连接
    if (Array.isArray(props.data)) {
      return props.data.slice(0, renderTagNum.value);
    }

    return  (props.data.split(',')).slice(0, renderTagNum.value);
  });

  const moreDataText = computed(() => {
    if (initData.value.length < 1
      || initData.value.length <= renderTagNum.value) {
      return '';
    }
    return  (typeof initData.value) === 'string' ? [initData.value].slice(renderTagNum.value).join(',') : initData.value.slice(renderTagNum.value).join(',');
  });

  let tippyIns: Instance | null = null;

  const calcRenderTagNum = () => {
    if (props.max && props.max > 0) {
      renderTagNum.value = props.max;
      return;
    }
    if (!rootRef.value || initData.value.length < 1) {
      return;
    }

    // 防止重复计算
    if (isCalcRenderTagNum.value) {
      return;
    }

    isCalcRenderTagNum.value = true;

    requestAnimationFrame(() => {
      nextTick(() => {
        if (rootRef.value && tagElsRef.value && tagElsRef.value.length > 0) {
          // 用父容器可用宽度计算，避免组件自身尚未撑开时把可见标签算少
          const parentWidth = rootRef.value.parentElement?.clientWidth || 0;
          const boxWidth = parentWidth > 0
            ? parentWidth
            : rootRef.value.getBoundingClientRect().width;
          const numTagWidth = 50;
          const copyBtnWidth = props.showCopy ? 20 : 0;
          let totalTagWidth = 0;
          let fitted = 0;

          // 从0开始重新计算
          for (let i = 0; i < tagElsRef.value.length; i++) {
            const currentTagWidth = tagElsRef.value[i].$el.getBoundingClientRect().width;
            totalTagWidth += currentTagWidth;

            // 检查是否还能放下当前标签和"+N"按钮
            const needNumBtn = i < tagElsRef.value.length - 1;
            const trailingWidth = copyBtnWidth + (slots.suffix ? 22 : 0);
            const requiredWidth = totalTagWidth
              + (needNumBtn ? numTagWidth : 0)
              + trailingWidth
              + (i * 6);

            if (requiredWidth <= boxWidth) {
              fitted = i + 1;
            } else {
              break;
            }
          }

          // 确保至少显示一个标签
          renderTagNum.value = fitted > 0 ? fitted : 1;
          isCalcRenderTagNum.value = false;
        } else {
          renderTagNum.value = 0;
          isCalcRenderTagNum.value = false;
        }
      });
    });
  };

  const handlerClick = () => {
    emits('click');
  };
  watch(() => initData.value, () => {
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
      tippyIns?.hide();
      tippyIns?.unmount();
      tippyIns?.destroy();
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
    execCopy(initData.value.join('\n'), t('复制成功'));
  };

  let resizeObserver: any;
  onMounted(() => {
    calcRenderTagNum();

    resizeObserver = new ResizeObserver(throttle(() => {
      // 延迟执行，确保 DOM 更新完成
      setTimeout(() => {
        renderTagNum.value = Math.max(renderTagNum.value, 1);
        calcRenderTagNum();
      });
    }, 200));
    resizeObserver.observe(rootRef.value);
    if (rootRef.value.parentElement) {
      resizeObserver.observe(rootRef.value.parentElement);
    }
  });

  onBeforeUnmount(() => {
    if (tippyIns) {
      tippyIns?.hide();
      tippyIns?.unmount();
      tippyIns?.destroy();
    }
    resizeObserver?.disconnect();
  });
</script>
<style scoped lang="postcss">
  .audit-edit-tag {
    position: relative;
    display: inline-flex;
    max-width: 100%;
    align-items: center;
    vertical-align: middle;

    .audit-edit-tag__main {
      display: inline-flex;
      flex-wrap: nowrap;
      align-items: center;
    }

    .audit-edit-tag__actions {
      display: inline-flex;
      flex-shrink: 0;
      align-items: center;
    }

    .audit-edit-tag__label {
      flex-shrink: 0;
    }

    .audit-edit-tag__more {
      flex-shrink: 0;
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
      display: inline-flex;
      align-items: center;
      padding-left: 8px;
      cursor: pointer;
      opacity: 0%;

      &:hover {
        color: #3a84ff;
      }
    }

    .edit-tag-suffix {
      display: inline-flex;
      align-items: center;
      margin-left: 4px;
      vertical-align: middle;
    }
  }

  :deep(.audit-edit-tag__label.bk-tag) {
    width: auto !important;
    max-width: none !important;
    margin-right: 0;
    overflow: visible;
    vertical-align: middle;
  }
</style>
