<!--

  TencentBlueKing is pleased to support the open source community by making

  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.

-->

<template>
  <!--
    keep-alive 停用时 disable teleport，把 Dock 收回组件树，
    避免缓存实例留在 body 上叠出第二个「工单处理」。
  -->
  <teleport
    :disabled="!isDockActive"
    to="body">
    <div
      ref="dockRootRef"
      class="risk-handle-dock"
      :class="{
        'is-expanded': isExpanded,
        'is-resizing': isResizing,
        'is-resize-hover': showResizeBar,
        'is-editor-boosted': isEditorBoosted,
        'is-inactive': !isDockActive,
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

          :class="{ 'is-visible': showResizeBar || isResizing }" />
      </div>


      <div

        class="risk-handle-dock__header"

        @click.stop="toggleExpanded">
        <audit-icon

          class="risk-handle-dock__toggle"

          :type="isExpanded ? 'angle-fill-down' : 'angle-fill-rignt'" />

        <span class="risk-handle-dock__title">{{ t('工单处理') }}</span>

        <audit-icon
          class="risk-handle-dock__info"

          type="info-fill" />

        <div class="risk-handle-dock__stage">
          <span class="risk-handle-dock__stage-text">{{ t('当前处于') }}</span>

          <span class="risk-handle-dock__stage-tag">{{ currentStageName }}</span>

          <span class="risk-handle-dock__stage-text">{{ t('环节') }}</span>
        </div>
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
    nextTick,
    onActivated,
    onBeforeUnmount,
    onDeactivated,
    onMounted,
    provide,
    ref,
    watch,
  } from 'vue';

  import { useI18n } from 'vue-i18n';

  import stretchDragCursor from '@/images/stretch-drag-cursor.svg';


  interface Props {

    currentStageName: string;

    defaultExpanded?: boolean;

  }


  const props = withDefaults(defineProps<Props>(), {

    defaultExpanded: false,

  });


  const { t } = useI18n();

  const resizeCursor = `url("${stretchDragCursor}") 16 16, ns-resize`;


  const HEADER_HEIGHT = 52;

  const COLLAPSED_HEIGHT = 52;

  const MIN_EXPANDED_HEIGHT = 96;

  const MAX_HEIGHT_RATIO = 0.7;

  const CONTENT_HORIZONTAL_PADDING = 24;

  const TOGGLE_LOCK_MS = 250;

  const RESIZE_CLICK_THRESHOLD = 4;


  const getDefaultExpandedHeight = () => {
    const maxHeight = Math.floor(window.innerHeight * MAX_HEIGHT_RATIO);

    const preferred = Math.floor(window.innerHeight * 0.68);

    return Math.min(maxHeight, Math.max(560, preferred));
  };


  const isExpanded = ref(props.defaultExpanded);
  const isDockActive = ref(true);
  const panelHeight = ref(getDefaultExpandedHeight());
  const isResizing = ref(false);
  const showResizeBar = ref(false);
  const isEditorBoosted = ref(false);
  const panelHeightBeforeBoost = ref<number | null>(null);
  const dockLeft = ref(0);
  const dockWidth = ref(0);
  const dockRootRef = ref<HTMLElement>();
  const isToggleLocked = ref(false);
  let toggleLockTimer: ReturnType<typeof setTimeout> | null = null;

  const lockToggle = () => {
    isToggleLocked.value = true;
    if (toggleLockTimer) {
      clearTimeout(toggleLockTimer);
    }
    toggleLockTimer = setTimeout(() => {
      isToggleLocked.value = false;
      toggleLockTimer = null;
    }, TOGGLE_LOCK_MS);
  };

  const hideInactiveDocks = () => {
    document.querySelectorAll('.risk-handle-dock').forEach((el) => {
      const dockEl = el as HTMLElement;
      if (el !== dockRootRef.value) {
        dockEl.style.display = 'none';
        dockEl.style.pointerEvents = 'none';
        return;
      }
      dockEl.style.display = '';
      dockEl.style.pointerEvents = '';
    });
  };

  watch(() => props.defaultExpanded, (expanded) => {
    if (expanded) {
      isExpanded.value = true;
      if (panelHeight.value < MIN_EXPANDED_HEIGHT) {
        panelHeight.value = getDefaultExpandedHeight();
      }
    }
  });

  const getPageContentBottom = () => {
    const pageTitle = document.querySelector('.audit-navigation-main .page-title') as HTMLElement | null;
    if (pageTitle) {
      return pageTitle.getBoundingClientRect().bottom;
    }
    const mainEl = document.querySelector('.audit-navigation-main') as HTMLElement | null;
    if (mainEl) {
      return mainEl.getBoundingClientRect().top + 100;
    }
    return 100;
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

      '--dock-resize-cursor': resizeCursor,

    };

    if (!isExpanded.value) {
      return { ...baseStyle, height: `${COLLAPSED_HEIGHT}px` };
    }

    return { ...baseStyle, height: `${panelHeight.value}px` };
  });


  const toggleExpanded = () => {
    if (isToggleLocked.value || isResizing.value || !isDockActive.value) {
      return;
    }
    lockToggle();
    const wasExpanded = isExpanded.value;
    isExpanded.value = !isExpanded.value;

    if (!wasExpanded && isExpanded.value) {
      panelHeight.value = getDefaultExpandedHeight();
      return;
    }

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

    const prevBodyCursor = document.body.style.cursor;
    document.body.style.cursor = resizeCursor;

    const startY = event.clientY;

    const startHeight = panelHeight.value;

    const maxHeight = getMaxPanelHeight();
    let lastY = startY;

    const handleMouseMove = (moveEvent: MouseEvent) => {
      lastY = moveEvent.clientY;
      const nextHeight = startHeight + (startY - moveEvent.clientY);
      panelHeight.value = Math.min(Math.max(nextHeight, HEADER_HEIGHT), maxHeight);
    };


    const handleMouseUp = () => {
      isResizing.value = false;

      showResizeBar.value = false;

      document.body.style.cursor = prevBodyCursor;

      document.removeEventListener('mousemove', handleMouseMove);

      document.removeEventListener('mouseup', handleMouseUp);

      if (Math.abs(lastY - startY) <= RESIZE_CLICK_THRESHOLD) {
        toggleExpanded();
        return;
      }

      if (panelHeight.value < MIN_EXPANDED_HEIGHT) {
        isExpanded.value = false;

        panelHeight.value = getDefaultExpandedHeight();
      }
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
    isDockActive.value = true;
    updateDockPosition();
    nextTick(hideInactiveDocks);

    window.addEventListener('resize', handleResize);

    layoutObserver = new MutationObserver(handleResize);

    layoutObserver.observe(document.body, {

      subtree: true,

      childList: true,

      attributes: true,

      attributeFilter: ['class', 'style'],

    });
  });

  onActivated(() => {
    isDockActive.value = true;
    updateDockPosition();
    updateContentPadding(isExpanded.value ? panelHeight.value : COLLAPSED_HEIGHT);
    nextTick(hideInactiveDocks);
  });

  onDeactivated(() => {
    isDockActive.value = false;
    const scrollContent = getScrollContent();
    if (scrollContent) {
      scrollContent.style.paddingBottom = '';
    }
  });

  onBeforeUnmount(() => {
    isDockActive.value = false;
    if (toggleLockTimer) {
      clearTimeout(toggleLockTimer);
      toggleLockTimer = null;
    }

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
  background: var(--bk-theme-surface-default);
  border-top: 1px solid var(--bk-theme-border-default);
  box-shadow: var(--bk-theme-card-shadow);
  transition: height .2s ease, left .2s ease, width .2s ease;


  &.is-inactive {
    display: none;
    pointer-events: none;
  }


  &.is-resizing {
    transition: none;
    user-select: none;

  }


  &.is-expanded.is-resize-hover {
    border-top-color: var(--bk-theme-color-brand-4);

  }

}


.risk-handle-dock__resize-zone {
  position: absolute;
  top: -8px;
  right: 0;
  left: 0;
  z-index: 3;
  height: 8px;
  cursor: var(--dock-resize-cursor, ns-resize);

}


.risk-handle-dock__resize-line {
  position: absolute;
  top: 0;
  right: 0;
  left: 0;
  height: 2px;
  background: var(--bk-theme-color-brand-2);
  opacity: 0%;
  transition: opacity .15s;


  &.is-visible {
    opacity: 100%;

  }

}


.risk-handle-dock__resize-handle {
  position: absolute;
  top: -2px;
  left: 50%;
  width: 40px;
  height: 6px;
  background: var(--bk-theme-color-brand-2);
  border-radius: var(--bk-theme-tag-radius);
  opacity: 0%;
  transform: translateX(-50%);
  transition: opacity .15s;


  &.is-visible {
    opacity: 100%;

  }

}


.risk-handle-dock__header {
  display: flex;
  height: 52px;padding: 0 var(--dock-content-padding, var(--bk-theme-space-24));
  cursor: pointer;
  background: var(--bk-theme-surface-default);
  user-select: none;
  flex-shrink: 0;
  align-items: center;


  &:hover {
    background: var(--bk-theme-surface-subtle);

  }

}


.risk-handle-dock__toggle {
  flex-shrink: 0;
  margin-right: var(--bk-theme-space-8);
  font-size: 12px;
  color: var(--bk-theme-text-default);

}


.risk-handle-dock__title {
  margin-right: var(--bk-theme-space-16);
  font-size: 14px;
  font-weight: 700;
  line-height: 22px;
  color: var(--bk-theme-text-strong);

}


.risk-handle-dock__info {
  font-size: 14px;
  color: var(--bk-theme-text-weak);

}


.risk-handle-dock__stage {
  display: flex;
  margin-left: var(--bk-theme-space-4);
  align-items: center;
  gap: var(--bk-theme-space-2);
}


.risk-handle-dock__stage-text {
  font-size: 12px;
  line-height: 20px;
  color: var(--bk-theme-text-default);

}


.risk-handle-dock__stage-tag {
  padding: 0 var(--bk-theme-space-6);
  font-size: 12px;
  line-height: 20px;
  color: var(--bk-theme-color-brand-2);
  background: var(--bk-theme-color-brand-5);
  border-radius: var(--bk-theme-tag-radius);
}


.risk-handle-dock__body {
  flex: 1;
  min-height: 0;padding: var(--bk-theme-space-16) var(--dock-content-padding, var(--bk-theme-space-24)) var(--bk-theme-space-16);
  overflow: hidden auto;
}

.risk-handle-dock.is-editor-boosted .risk-handle-dock__body {
  overflow: hidden auto;
}

</style>


