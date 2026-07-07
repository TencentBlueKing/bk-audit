<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<template>
  <div
    ref="rootRef"
    class="link-event-timeline">
    <div class="timeline-tabs">
      <div class="timeline-tabs-inner">
        <div
          v-if="events.length > 1"
          ref="timelineItemsRef"
          class="timeline-items">
          <div
            class="timeline-items-line"
            :style="timelineLineStyle" />
          <div
            v-for="slot in displaySlots"
            :key="`item-${slot.eventIndex}`"
            class="timeline-item">
            <div class="timeline-item-dot">
              <span
                class="timeline-dot"
                :class="{ 'is-active': slot.eventIndex === activeIndex }" />
            </div>
            <div
              class="event-capsule"
              :class="{ 'is-active': slot.eventIndex === activeIndex }"
              @click="handleSelect(slot.eventIndex)">
              {{ events[slot.eventIndex]?.event_time || '--' }}
            </div>
          </div>

          <div
            v-if="shouldShowOverflowTrigger"
            class="timeline-item">
            <div class="timeline-item-dot">
              <span class="timeline-dot" />
            </div>
            <bk-popover
              ref="popoverRef"
              :arrow="false"
              :is-show="isOverflowOpen"
              placement="bottom-start"
              theme="light"
              trigger="manual"
              @after-hidden="handleOverflowHidden">
              <div
                ref="overflowTriggerRef"
                class="event-capsule overflow-trigger"
                @click.stop="toggleOverflow"
                @mousedown.stop>
                +{{ overflowCount }}
                <audit-icon
                  class="overflow-icon"
                  type="angle-down" />
              </div>
              <template #content>
                <div
                  ref="overflowMenuRef"
                  class="overflow-menu"
                  @click.stop
                  @mousedown.stop
                  @scroll="handleOverflowScroll">
                  <div
                    v-for="eventIndex in overflowIndices"
                    :key="eventIndex"
                    class="overflow-menu-item"
                    @click="handleOverflowSelect(eventIndex)">
                    {{ events[eventIndex]?.event_time || '--' }}
                  </div>
                </div>
              </template>
            </bk-popover>
          </div>
        </div>

        <template v-else>
          <div
            v-for="slot in displaySlots"
            :key="`tab-${slot.eventIndex}`"
            class="event-capsule"
            :class="{ 'is-active': slot.eventIndex === activeIndex }"
            @click="handleSelect(slot.eventIndex)">
            {{ events[slot.eventIndex]?.event_time || '--' }}
          </div>
        </template>

        <span
          v-if="showAdd"
          class="add-event"
          @click="emits('add')">
          <audit-icon
            class="add-icon-event"
            type="add" />
          {{ t('新建关联事件') }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import {
    computed,
    nextTick,
    onBeforeUnmount,
    onMounted,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import EventModel from '@model/event/event';

  interface Props {
    events: EventModel[];
    activeIndex: number;
    showAdd?: boolean;
    hasMore?: boolean;
    loadingMore?: boolean;
  }

  interface Emits {
    (e: 'select', index: number): void;
    (e: 'add'): void;
    (e: 'load-more'): void;
  }

  interface DisplaySlot {
    eventIndex: number;
  }

  const props = withDefaults(defineProps<Props>(), {
    showAdd: true,
    hasMore: false,
    loadingMore: false,
  });
  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const rootRef = ref<HTMLElement>();
  const timelineItemsRef = ref<HTMLElement>();
  const overflowMenuRef = ref<HTMLElement>();
  const overflowTriggerRef = ref<HTMLElement>();
  const popoverRef = ref<{ hide?:() => void }>();
  const isOverflowOpen = ref(false);
  const maxVisibleCount = ref(8);

  const CAPSULE_GAP = 12;
  const MIN_CAPSULE_WIDTH = 148;
  const OVERFLOW_WIDTH = 76;
  const ADD_BUTTON_WIDTH = 120;

  const shouldShowOverflowTrigger = computed(() => overflowCount.value > 0 || isOverflowOpen.value);

  const hasOverflow = computed(() => props.events.length > maxVisibleCount.value);

  const visibleIndices = computed(() => {
    const total = props.events.length;
    if (total === 0) {
      return [];
    }
    if (!hasOverflow.value) {
      return props.events.map((_, index) => index);
    }
    const headCount = Math.max(maxVisibleCount.value - 1, 1);
    const indices = Array.from({ length: headCount }, (_, index) => index);
    if (!indices.includes(props.activeIndex) && props.activeIndex >= headCount) {
      indices[indices.length - 1] = props.activeIndex;
      indices.sort((a, b) => a - b);
    }
    return indices;
  });

  const overflowIndices = computed(() => {
    const visibleSet = new Set(visibleIndices.value);
    return props.events.map((_, index) => index).filter(index => !visibleSet.has(index));
  });

  const overflowCount = computed(() => overflowIndices.value.length);

  const displaySlots = computed<DisplaySlot[]>(() => (
    visibleIndices.value.map(eventIndex => ({ eventIndex }))
  ));

  const timelineLineStyle = ref<Record<string, string>>({ display: 'none' });

  const updateTimelineLine = () => {
    nextTick(() => {
      const container = timelineItemsRef.value;
      if (!container) {
        timelineLineStyle.value = { display: 'none' };
        return;
      }
      const dots = container.querySelectorAll('.timeline-dot');
      if (dots.length < 2) {
        timelineLineStyle.value = { display: 'none' };
        return;
      }
      const firstDot = dots[0].getBoundingClientRect();
      const lastDot = dots[dots.length - 1].getBoundingClientRect();
      const containerRect = container.getBoundingClientRect();
      const left = firstDot.left + firstDot.width / 2 - containerRect.left;
      const right = lastDot.left + lastDot.width / 2 - containerRect.left;
      timelineLineStyle.value = {
        display: 'block',
        left: `${left}px`,
        width: `${Math.max(right - left, 0)}px`,
      };
    });
  };

  const refreshTimelineLayout = () => {
    updateMaxVisibleCount();
    updateTimelineLine();
  };

  const getMaxVisibleCount = (containerWidth: number) => {
    const reservedAddWidth = props.showAdd ? (ADD_BUTTON_WIDTH + CAPSULE_GAP) : 0;
    const availableWidth = Math.max(containerWidth - reservedAddWidth, MIN_CAPSULE_WIDTH);

    const maxWithoutOverflow = Math.floor((availableWidth + CAPSULE_GAP) / (MIN_CAPSULE_WIDTH + CAPSULE_GAP));
    if (props.events.length <= maxWithoutOverflow) {
      return Math.max(maxWithoutOverflow, 1);
    }

    const availableForCapsules = availableWidth - OVERFLOW_WIDTH - CAPSULE_GAP;
    const maxWithOverflow = Math.floor((availableForCapsules + CAPSULE_GAP) / (MIN_CAPSULE_WIDTH + CAPSULE_GAP));
    return Math.max(maxWithOverflow, 1);
  };

  const updateMaxVisibleCount = () => {
    const width = rootRef.value?.clientWidth || 0;
    if (!width) {
      return;
    }
    maxVisibleCount.value = getMaxVisibleCount(width);
  };

  const handleSelect = (index: number) => {
    emits('select', index);
  };

  const handleOverflowSelect = (index: number) => {
    emits('select', index);
    closeOverflow();
  };

  const closeOverflow = () => {
    isOverflowOpen.value = false;
    unbindDocumentMousedown();
    popoverRef.value?.hide?.();
  };

  const toggleOverflow = () => {
    isOverflowOpen.value = !isOverflowOpen.value;
    if (isOverflowOpen.value) {
      bindDocumentMousedown();
      return;
    }
    unbindDocumentMousedown();
  };

  const isInPopoverLayer = (target: Node) => {
    const el = target as HTMLElement;
    if (!el?.closest) {
      return false;
    }
    return !!el.closest('.overflow-menu, .tippy-box, .bk-popover, .bk-pop2-content');
  };

  const handleDocumentMousedown = (event: Event) => {
    if (!isOverflowOpen.value) {
      return;
    }
    const target = event.target as HTMLElement;
    if (overflowTriggerRef.value?.contains(target)) {
      return;
    }
    if (isInPopoverLayer(target)) {
      return;
    }
    closeOverflow();
  };

  const bindDocumentMousedown = () => {
    setTimeout(() => {
      document.addEventListener('mousedown', handleDocumentMousedown, true);
    });
  };

  const unbindDocumentMousedown = () => {
    document.removeEventListener('mousedown', handleDocumentMousedown, true);
  };

  const handleOverflowHidden = () => {
    isOverflowOpen.value = false;
    lastLoadMoreAt = 0;
    unbindDocumentMousedown();
  };

  let lastLoadMoreAt = 0;

  const handleOverflowScroll = (event: Event) => {
    if (!props.hasMore || props.loadingMore) {
      return;
    }
    const target = event.target as HTMLDivElement;
    const { scrollTop, clientHeight, scrollHeight } = target;
    if (scrollHeight <= clientHeight) {
      return;
    }
    if (scrollTop + clientHeight < scrollHeight - 5) {
      return;
    }
    const now = Date.now();
    if (now - lastLoadMoreAt < 300) {
      return;
    }
    lastLoadMoreAt = now;
    emits('load-more');
  };

  let resizeObserver: ResizeObserver | null = null;

  onMounted(() => {
    nextTick(() => {
      refreshTimelineLayout();
    });
    if (rootRef.value) {
      resizeObserver = new ResizeObserver(() => {
        if (isOverflowOpen.value) {
          return;
        }
        refreshTimelineLayout();
      });
      resizeObserver.observe(rootRef.value);
    }
  });

  onBeforeUnmount(() => {
    resizeObserver?.disconnect();
    resizeObserver = null;
    unbindDocumentMousedown();
  });

  watch(
    () => [
      props.events.length,
      props.showAdd,
      props.activeIndex,
      displaySlots.value.length,
      shouldShowOverflowTrigger.value,
    ],
    () => {
      if (isOverflowOpen.value) {
        return;
      }
      nextTick(() => {
        refreshTimelineLayout();
      });
    },
  );
</script>

<style lang="postcss" scoped>
.link-event-timeline {
  position: relative;
  width: 100%;
  padding: 8px 0 16px;
}

.timeline-tabs {
  display: flex;
  align-items: flex-end;
}

.timeline-tabs-inner {
  display: flex;
  flex-wrap: nowrap;
  gap: 12px;
  align-items: flex-end;
  min-width: 0;
}

.timeline-items {
  position: relative;
  display: flex;
  flex: 0 0 auto;
  gap: 12px;
  align-items: flex-end;
}

.timeline-items-line {
  position: absolute;
  top: 4px;
  z-index: 0;
  height: 1px;
  background: #dcdee5;
}

.timeline-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}

.timeline-item-dot {
  position: relative;
  z-index: 1;
  display: flex;
  width: 100%;
  height: 12px;
  align-items: center;
  justify-content: center;
}

.timeline-dot {
  position: relative;
  z-index: 1;
  display: block;
  width: 8px;
  height: 8px;
  background: #c4c6cc;
  border-radius: 50%;

  &.is-active {
    background: #3a84ff;
  }
}

.event-capsule {
  height: 32px;
  padding: 0 16px;
  font-size: 12px;
  line-height: 30px;
  color: #313238;
  white-space: nowrap;
  cursor: pointer;
  background: #fff;
  border: 1px solid #dcdee5;
  border-radius: 16px;

  &:hover {
    border-color: #3a84ff;
  }

  &.is-active {
    color: #3a84ff;
    background: #f0f5ff;
    border-color: #a3c5fd;
  }
}

.overflow-trigger {
  display: inline-flex;
  gap: 4px;
  align-items: center;
  color: #3a84ff;
  border-color: #a3c5fd;
}

.overflow-icon {
  font-size: 12px;
}

.overflow-menu {
  max-height: 240px;
  min-width: 180px;
  overflow-y: auto;
}

.overflow-menu-item {
  padding: 8px 12px;
  font-size: 12px;
  line-height: 20px;
  color: #313238;
  cursor: pointer;

  &:hover {
    color: #3a84ff;
    background: #f0f5ff;
  }
}

.add-event {
  display: inline-flex;
  flex-shrink: 0;
  gap: 4px;
  align-items: center;
  font-size: 12px;
  line-height: 32px;
  color: #3a84ff;
  white-space: nowrap;
  cursor: pointer;

  .add-icon-event {
    display: inline-flex;
    font-size: 12px;
    line-height: 1;
  }
}
</style>
