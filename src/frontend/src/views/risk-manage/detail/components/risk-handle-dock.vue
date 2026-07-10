<!--

  TencentBlueKing is pleased to support the open source community by making

  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.

-->

<template>
  <teleport to="body">
    <div

      class="risk-handle-dock"

      :class="{
        'is-expanded': isExpanded,
        'is-resizing': isResizing,
        'is-resize-hover': showResizeBar,
        'is-editor-boosted': isEditorBoosted,
      }"

      :style="dockStyle">
      <div

        v-if="isExpanded"

        class="risk-handle-dock__resize-zone"

        @mousedown.prevent.stop="handleResizeStart"

        @mouseenter="showResizeBar = true"

        @mouseleave="showResizeBar = false">
        <div

          class="risk-handle-dock__resize-line"

          :class="{ 'is-visible': showResizeBar || isResizing }" />

        <div

          class="risk-handle-dock__resize-handle"

          :class="{ 'is-visible': showResizeBar || isResizing }">
          <audit-icon

            class="risk-handle-dock__resize-icon"

            type="angle-double-up" />

          <audit-icon

            class="risk-handle-dock__resize-icon"

            type="angle-double-down" />
        </div>
      </div>


      <div

        class="risk-handle-dock__header"

        @click="toggleExpanded">
        <audit-icon

          class="risk-handle-dock__toggle"

          :type="isExpanded ? 'angle-fill-down' : 'angle-fill-rignt'" />

        <span class="risk-handle-dock__title">{{ t('工单处理') }}</span>

        <audit-icon

          v-bk-tooltips="t('展示风险单处理流程与当前可操作环节')"

          class="risk-handle-dock__info"

          type="info" />

        <span class="risk-handle-dock__stage-text">{{ t('当前处于') }}</span>

        <span class="risk-handle-dock__stage-tag">{{ currentStageName }}</span>

        <span class="risk-handle-dock__stage-text">{{ t('环节') }}</span>
      </div>


      <div

        v-show="isExpanded"

        class="risk-handle-dock__body">
        <slot />
      </div>
    </div>
  </teleport>
</template>


<script setup lang="ts">

  import _ from 'lodash';

  import {
    computed,
    onBeforeUnmount,
    onMounted,
    provide,
    ref,
    watch,
  } from 'vue';

  import { useI18n } from 'vue-i18n';


  interface Props {

    currentStageName: string;

    defaultExpanded?: boolean;

  }


  const props = withDefaults(defineProps<Props>(), {

    defaultExpanded: false,

  });


  const { t } = useI18n();


  const HEADER_HEIGHT = 48;

  const COLLAPSED_HEIGHT = 48;

  const MIN_EXPANDED_HEIGHT = 96;

  const MAX_HEIGHT_RATIO = 0.7;

  const CONTENT_HORIZONTAL_PADDING = 24;


  const getDefaultExpandedHeight = () => {
    const maxHeight = Math.floor(window.innerHeight * MAX_HEIGHT_RATIO);

    const preferred = Math.floor(window.innerHeight * 0.5);

    return Math.min(maxHeight, Math.max(440, preferred));
  };


  const isExpanded = ref(props.defaultExpanded);
  const panelHeight = ref(getDefaultExpandedHeight());
  const isResizing = ref(false);
  const showResizeBar = ref(false);
  const isEditorBoosted = ref(false);
  const panelHeightBeforeBoost = ref<number | null>(null);
  const dockLeft = ref(0);
  const dockWidth = ref(0);

  const getPageContentBottom = () => {
    const pageTitle = document.querySelector('.audit-navigation-main .page-title') as HTMLElement | null;
    if (pageTitle) {
      return pageTitle.getBoundingClientRect().bottom;
    }
    const mainEl = document.querySelector('.audit-navigation-main') as HTMLElement | null;
    if (mainEl) {
      return mainEl.getBoundingClientRect().top + 52;
    }
    return 104;
  };

  const getMaxPanelHeight = () => {
    const maxHeight = window.innerHeight - getPageContentBottom();
    return Math.max(MIN_EXPANDED_HEIGHT, maxHeight);
  };

  const handleEditorExpandChange = (expanded: boolean) => {
    if (expanded) {
      if (!isExpanded.value) {
        isExpanded.value = true;
        panelHeight.value = getDefaultExpandedHeight();
      }
      if (panelHeightBeforeBoost.value === null) {
        panelHeightBeforeBoost.value = panelHeight.value;
      }
      panelHeight.value = getMaxPanelHeight();
      isEditorBoosted.value = true;
      return;
    }
    isEditorBoosted.value = false;
    if (panelHeightBeforeBoost.value !== null) {
      panelHeight.value = panelHeightBeforeBoost.value;
      panelHeightBeforeBoost.value = null;
    }
  };

  const collapseDock = () => {
    isExpanded.value = false;
    isEditorBoosted.value = false;
    panelHeightBeforeBoost.value = null;
  };

  provide('dockEditorExpand', handleEditorExpandChange);
  provide('dockBoostState', {
    isEditorBoosted,
    panelHeight,
  });
  provide('dockCollapse', collapseDock);


  const getScrollContent = () => document.querySelector('#auditNavigationContent .scroll-faker-content') as HTMLElement | null;


  const updateDockPosition = () => {
    const mainEl = document.querySelector('.audit-navigation-main') as HTMLElement | null;

    if (!mainEl) {
      dockLeft.value = 0;

      dockWidth.value = 0;

      return;
    }

    const rect = mainEl.getBoundingClientRect();

    dockLeft.value = rect.left;

    dockWidth.value = rect.width;
  };


  const updateContentPadding = (height: number) => {
    const scrollContent = getScrollContent();

    if (!scrollContent) {
      return;
    }

    const applyPadding = () => {
      const { scrollHeight, clientHeight } = scrollContent;
      // 内容未溢出时不增加底部内边距，避免页面初始出现多余滚动条
      scrollContent.style.paddingBottom = scrollHeight > clientHeight ? `${height}px` : '';
    };

    applyPadding();
    requestAnimationFrame(applyPadding);
  };


  const dockStyle = computed(() => {
    const baseStyle = {

      left: `${dockLeft.value}px`,

      width: dockWidth.value ? `${dockWidth.value}px` : 'auto',

      '--dock-content-padding': `${CONTENT_HORIZONTAL_PADDING}px`,

    };

    if (!isExpanded.value) {
      return { ...baseStyle, height: `${COLLAPSED_HEIGHT}px` };
    }

    return { ...baseStyle, height: `${panelHeight.value}px` };
  });


  const toggleExpanded = () => {
    isExpanded.value = !isExpanded.value;

    if (isExpanded.value && panelHeight.value < MIN_EXPANDED_HEIGHT) {
      panelHeight.value = getDefaultExpandedHeight();
    }
  };


  const handleResizeStart = (event: MouseEvent) => {
    if (!isExpanded.value) {
      return;
    }

    isResizing.value = true;

    showResizeBar.value = true;

    const startY = event.clientY;

    const startHeight = panelHeight.value;

    const maxHeight = getMaxPanelHeight();

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const nextHeight = startHeight + (startY - moveEvent.clientY);
      panelHeight.value = Math.min(Math.max(nextHeight, HEADER_HEIGHT), maxHeight);
    };


    const handleMouseUp = () => {
      isResizing.value = false;

      showResizeBar.value = false;

      if (panelHeight.value < MIN_EXPANDED_HEIGHT) {
        isExpanded.value = false;

        panelHeight.value = getDefaultExpandedHeight();
      }

      document.removeEventListener('mousemove', handleMouseMove);

      document.removeEventListener('mouseup', handleMouseUp);
    };


    document.addEventListener('mousemove', handleMouseMove);

    document.addEventListener('mouseup', handleMouseUp);
  };


  watch(isExpanded, (expanded) => {
    updateContentPadding(expanded ? panelHeight.value : COLLAPSED_HEIGHT);
  }, { immediate: true });


  watch(panelHeight, (height) => {
    if (isExpanded.value) {
      updateContentPadding(height);
    }
  });


  let layoutObserver: MutationObserver | null = null;

  const handleResize = _.debounce(() => {
    updateDockPosition();
    if (isExpanded.value) {
      const maxHeight = getMaxPanelHeight();
      if (panelHeight.value > maxHeight) {
        panelHeight.value = maxHeight;
      }
      if (isEditorBoosted.value) {
        panelHeight.value = maxHeight;
      }
    }
    updateContentPadding(isExpanded.value ? panelHeight.value : COLLAPSED_HEIGHT);
  }, 50);


  onMounted(() => {
    updateDockPosition();

    window.addEventListener('resize', handleResize);

    layoutObserver = new MutationObserver(handleResize);

    layoutObserver.observe(document.body, {

      subtree: true,

      childList: true,

      attributes: true,

      attributeFilter: ['class', 'style'],

    });
  });


  onBeforeUnmount(() => {
    window.removeEventListener('resize', handleResize);

    layoutObserver?.disconnect();

    layoutObserver = null;

    const scrollContent = getScrollContent();

    if (scrollContent) {
      scrollContent.style.paddingBottom = '';
    }
  });


  defineExpose({
    isExpanded,
    expand: () => {
      isExpanded.value = true;
      if (panelHeight.value < MIN_EXPANDED_HEIGHT) {
        panelHeight.value = getDefaultExpandedHeight();
      }
    },
    collapse: collapseDock,
    handleEditorExpandChange,
  });

</script>


<style lang="postcss" scoped>

.risk-handle-dock {
  position: fixed;
  bottom: 0;
  z-index: 1998;
  display: flex;
  overflow: hidden;
  flex-direction: column;
  background: #fff;
  border-top: 1px solid #dcdee5;
  box-shadow: 0 -2px 8px 0 rgb(0 0 0 / 8%);
  transition: height .2s ease, left .2s ease, width .2s ease;


  &.is-resizing {
    transition: none;
    user-select: none;

  }


  &.is-expanded.is-resize-hover {
    border-top-color: #a3c5fd;

  }

}


.risk-handle-dock__resize-zone {
  position: absolute;
  top: 0;
  right: 0;
  left: 0;
  z-index: 3;
  height: 14px;
  cursor: ns-resize;

}


.risk-handle-dock__resize-line {
  position: absolute;
  top: 0;
  right: 0;
  left: 0;
  height: 2px;
  background: #3a84ff;
  opacity: 0%;
  transition: opacity .15s;


  &.is-visible {
    opacity: 100%;

  }

}


.risk-handle-dock__resize-handle {
  position: absolute;
  top: 0;
  left: 50%;
  display: flex;
  width: 48px;
  height: 10px;
  line-height: 1;
  color: #3a84ff;
  background: #fff;
  border: 1px solid #a3c5fd;
  border-radius: 2px;
  opacity: 0%;
  transform: translateX(-50%);
  transition: opacity .15s;
  align-items: center;
  justify-content: center;
  flex-direction: column;


  &.is-visible {
    opacity: 100%;

  }

}


.risk-handle-dock__resize-icon {
  font-size: 8px;
  line-height: 1;

}


.risk-handle-dock__header {
  display: flex;
  height: 48px;
  padding: 0 var(--dock-content-padding, 24px);
  cursor: pointer;
  background: #fff;
  user-select: none;
  flex-shrink: 0;
  align-items: center;


  &:hover {
    background: #f5f7fa;

  }

}


.risk-handle-dock__toggle {
  flex-shrink: 0;
  margin-right: 8px;
  font-size: 12px;
  color: #4d4f56;

}


.risk-handle-dock__title {
  margin-right: 8px;
  font-size: 14px;
  font-weight: 700;
  line-height: 22px;
  color: #313238;

}


.risk-handle-dock__info {
  margin-right: 16px;
  font-size: 14px;
  color: #979ba5;

}


.risk-handle-dock__stage-text {
  font-size: 12px;
  line-height: 20px;
  color: #979ba5;

}


.risk-handle-dock__stage-tag {
  padding: 0 8px;
  margin: 0 4px;
  font-size: 12px;
  line-height: 20px;
  color: #3a84ff;
  background: #f0f5ff;
  border-radius: 2px;

}


.risk-handle-dock__body {
  flex: 1;
  min-height: 0;
  padding: 16px var(--dock-content-padding, 24px) 16px;
  overflow: hidden auto;
}

.risk-handle-dock.is-editor-boosted .risk-handle-dock__body {
  overflow: hidden auto;
}

</style>


