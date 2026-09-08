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
        <div class="audit-edit-tag__labels">
          <bk-tag
            v-for="(item) in renderData"
            :key="item"
            v-bk-tooltips="{
              content: item,
              disabled: item.length < 12,
            }"
            class="audit-edit-tag__label"
            @click="handlerClick">
            {{ item }}
          </bk-tag>
        </div>
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
        class="audit-edit-tag-measure"
        style="position: absolute; top: -9999px; left: -9999px;
          word-break: keep-all; white-space: nowrap; visibility: hidden;">
        <bk-tag
          v-for="item in initData"
          :key="item"
          ref="tagElsRef"
          class="audit-edit-tag__label">
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
  let pendingCalc = false;
  let calcRetryCount = 0;
  const MAX_CALC_RETRY = 5;
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

  const getTagElWidth = (tagIns: { $el?: HTMLElement } | HTMLElement) => {
    const el = (tagIns as { $el?: HTMLElement })?.$el || (tagIns as HTMLElement);
    return el?.getBoundingClientRect?.().width || 0;
  };

  const finishCalc = (options?: { retry?: boolean }) => {
    isCalcRenderTagNum.value = false;
    if (options?.retry && calcRetryCount < MAX_CALC_RETRY) {
      calcRetryCount += 1;
      window.setTimeout(() => {
        calcRenderTagNum();
      }, 50);
      return;
    }
    if (pendingCalc) {
      pendingCalc = false;
      calcRetryCount = 0;
      nextTick(() => {
        calcRenderTagNum();
      });
      return;
    }
    calcRetryCount = 0;
  };

  const calcRenderTagNum = () => {
    if (props.max && props.max > 0) {
      renderTagNum.value = props.max;
      return;
    }
    if (!rootRef.value || initData.value.length < 1) {
      return;
    }

    // 计算中收到新请求时排队，避免场景名异步加载后不再重算
    if (isCalcRenderTagNum.value) {
      pendingCalc = true;
      return;
    }

    isCalcRenderTagNum.value = true;

    requestAnimationFrame(() => {
      nextTick(() => {
        if (rootRef.value && tagElsRef.value && tagElsRef.value.length > 0) {
          // 用父容器可用宽度计算，避免组件自身尚未撑开时把可见标签算少
          const parentEl = rootRef.value.parentElement as HTMLElement | null;
          const parentStyle = parentEl ? window.getComputedStyle(parentEl) : null;
          const parentPadding = parentStyle
            ? (Number.parseFloat(parentStyle.paddingLeft) || 0)
              + (Number.parseFloat(parentStyle.paddingRight) || 0)
            : 0;
          const parentWidth = parentEl?.clientWidth || 0;
          const boxWidth = Math.max(
            0,
            (parentWidth > 0
              ? parentWidth - parentPadding
              : rootRef.value.getBoundingClientRect().width),
          );
          const numTagWidth = 42;
          const copyBtnWidth = props.showCopy ? 20 : 0;
          let totalTagWidth = 0;
          let fitted = 0;
          const tagList = Array.isArray(tagElsRef.value)
            ? tagElsRef.value
            : [tagElsRef.value];

          // 测量节点尚未布局完成时延后重算
          const hasInvalidWidth = tagList.some(tag => !getTagElWidth(tag));
          if (hasInvalidWidth || boxWidth <= 0) {
            finishCalc({ retry: true });
            return;
          }

          // 从0开始重新计算；预留 +N / 复制按钮空间，保证溢出时 +N 可展示
          for (let i = 0; i < tagList.length; i++) {
            const currentTagWidth = getTagElWidth(tagList[i]);
            const needNumBtn = i < tagList.length - 1;
            const trailingWidth = copyBtnWidth + (slots.suffix ? 22 : 0);
            const gapWidth = i * 6;
            const nextTotal = totalTagWidth + currentTagWidth;
            const requiredWidth = nextTotal
              + (needNumBtn ? numTagWidth : 0)
              + trailingWidth
              + gapWidth;

            if (requiredWidth <= boxWidth) {
              totalTagWidth = nextTotal;
              fitted = i + 1;
            } else {
              // 第一个都放不下时仍展示 1 个完整标签，其余用 +N
              break;
            }
          }

          // 至少显示一个标签；放不下的用 +N
          renderTagNum.value = fitted > 0 ? fitted : 1;
          finishCalc();
        } else {
          renderTagNum.value = Math.min(1, initData.value.length || 1);
          finishCalc({ retry: true });
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
    overflow: hidden;
    align-items: center;
    vertical-align: middle;

    .audit-edit-tag__main {
      display: inline-flex;
      flex-wrap: nowrap;
      align-items: center;
      min-width: 0;
      max-width: 100%;
      overflow: hidden;
    }

    .audit-edit-tag__labels {
      display: inline-flex;
      flex: 1 1 auto;
      flex-wrap: nowrap;
      align-items: center;
      min-width: 0;
      overflow: hidden;
    }

    .audit-edit-tag__actions {
      display: inline-flex;
      flex-shrink: 0;
      align-items: center;
    }

    .audit-edit-tag__label {
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

    /* +N 与左侧标签保持空隙（需写在 .bk-tag 之后，避免被 margin-left:0 覆盖） */
    .audit-edit-tag__more.bk-tag {
      flex-shrink: 0;
      margin-left: 6px;
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

<style lang="postcss">
  /* 测量节点与展示标签同宽，避免默认 bk-tag max-width 导致可放数量算多 */
  .audit-edit-tag-measure {
    .audit-edit-tag__label.bk-tag {
      width: auto !important;
      max-width: none !important;
      margin-right: 0;
      margin-left: 0;
      overflow: visible;

      & ~ .bk-tag {
        margin-left: 6px;
      }
    }
  }
</style>
