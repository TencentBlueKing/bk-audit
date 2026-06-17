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
    ref="tagRef"
    class="condition-tag-item condition-tag-date-item"
    :class="{ 'is-editing': isPanelOpen }"
    @click.stop="handleTogglePanel">
    <span class="tag-label">{{ t(tag.label) }}：</span>
    <span
      v-if="!isPanelOpen"
      ref="valueWrapperRef"
      v-bk-tooltips="shortcutTooltipOptions"
      class="tag-value-wrapper tag-value-date-wrapper">
      <span class="tag-value tag-date-display-text">{{ displayText }}</span>
    </span>
    <span
      v-else
      ref="valueWrapperRef"
      class="tag-value-wrapper tag-value-date-wrapper">
      <bk-date-picker
        ref="datePickerRef"
        v-model="localValue"
        append-to-body
        class="nl-tag-date-picker"
        :clearable="false"
        format="yyyy-MM-dd HH:mm:ss"
        :open="isPanelOpen"
        :shortcut-selected-index="shortcutSelectedIndex"
        :shortcuts="shortcutsRange"
        type="datetimerange"
        use-shortcut-text
        @change="handleChange"
        @pick-success="handlePickSuccess"
        @shortcut-change="handleShortcutChange">
        <template #confirm>
          <span />
        </template>
      </bk-date-picker>
      <span class="tag-date-display-text tag-date-display-text-editing">
        {{ displayText }}
      </span>
      <span
        ref="measureRef"
        class="date-measure-span">
        {{ measureText }}
      </span>
    </span>
    <audit-icon
      v-if="props.removable"
      class="tag-remove-btn"
      type="close"
      @click.stop="$emit('remove', tag.fieldName)" />
  </div>
</template>
<script setup lang="ts">
  import dayjs from 'dayjs';
  import {
    computed,
    nextTick,
    onBeforeUnmount,
    onMounted,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type { IConditionTag } from '../../types';

  interface Props {
    tag: IConditionTag;
    searchModel: Record<string, any>;
    // eslint-disable-next-line vue/no-unused-properties
    isEditing: boolean;
    // eslint-disable-next-line vue/no-unused-properties
    removable?: boolean;
  }
  interface Emits {
    (e: 'update', fieldName: string, value: any): void;
    (e: 'remove', fieldName: string): void;
    (e: 'startEdit'): void;
    (e: 'finishEdit'): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    removable: true,
  });
  const emit = defineEmits<Emits>();
  const { t } = useI18n();

  const tagRef = ref<HTMLElement>();
  const valueWrapperRef = ref<HTMLElement>();
  const datePickerRef = ref();
  const measureRef = ref<HTMLSpanElement>();
  const isPanelOpen = ref(false);
  const measureText = ref('');
  const pendingShortcutSelectedIndex = ref<number | null>(null);
  const pendingShortcutOrigin = ref<string[] | null>(null);

  const formatRangeText = (value: any) => {
    if (!Array.isArray(value) || value.length < 2) {
      return '';
    }
    const start = value[0] instanceof Date ? dayjs(value[0]).format('YYYY-MM-DD HH:mm:ss') : String(value[0] || '');
    const end = value[1] instanceof Date ? dayjs(value[1]).format('YYYY-MM-DD HH:mm:ss') : String(value[1] || '');
    if (!start || !end) {
      return '';
    }
    return `${start} - ${end}`;
  };

  const handleTogglePanel = () => {
    const wasOpen = isPanelOpen.value;
    isPanelOpen.value = !isPanelOpen.value;
    // 面板从关闭变为打开时，通知上层记录快照
    if (!wasOpen && isPanelOpen.value) {
      emit('startEdit');
    }
    // 面板从打开变为关闭时，通知上层触发搜索
    if (wasOpen && !isPanelOpen.value) {
      emit('finishEdit');
    }
  };

  // 点击外部区域关闭面板
  const handleDocumentClick = (e: MouseEvent) => {
    if (!isPanelOpen.value) return;
    const target = e.target as HTMLElement;
    // 点击在标签自身内部 -> 不关闭（由 handleTogglePanel 控制）
    if (tagRef.value?.contains(target)) return;
    // 点击在日期面板弹出层内部 -> 不关闭
    const pickerDropdowns = document.querySelectorAll('.bk-date-picker-dropdown');
    for (const dropdown of Array.from(pickerDropdowns)) {
      if (dropdown.contains(target)) return;
    }
    // 其他区域 -> 关闭面板，并通知上层触发搜索
    isPanelOpen.value = false;
    emit('finishEdit');
  };


  const shortcutConfigs = [
    { label: '近1天',  days: 1,   origin: 'now-1d' },
    { label: '近3天',  days: 3,   origin: 'now-3d' },
    { label: '近7天',  days: 7,   origin: 'now-7d' },
    { label: '近14天', days: 14,  origin: 'now-14d' },
    { label: '近1月',  days: 30,  origin: 'now-1M' },
    { label: '近3月',  days: 90,  origin: 'now-3M' },
    { label: '近6月',  days: 182, origin: 'now-6M' },
    { label: '近12月', days: 365, origin: 'now-12M' },
  ];

  const shortcutsRange = shortcutConfigs.map(({ label, days }) => ({
    text: t(label),
    value() {
      const end = new Date();
      const start = new Date();
      start.setTime(start.getTime() - 3600 * 1000 * 24 * days);
      return [start, end];
    },
  }));

  const shortcutOriginMap: Record<string, number> = {};
  shortcutConfigs.forEach((item, idx) => {
    shortcutOriginMap[item.origin] = idx;
  });

  const resolvedShortcutSelectedIndex = computed(() => {
    const origin = props.searchModel.datetime_origin;
    if (Array.isArray(origin) && origin.length > 0) {
      const idx = shortcutOriginMap[origin[0]];
      if (idx !== undefined) return idx;
    }
    return -1;
  });

  const shortcutSelectedIndex = computed(() => (
    pendingShortcutSelectedIndex.value
    ?? (resolvedShortcutSelectedIndex.value >= 0 ? resolvedShortcutSelectedIndex.value : null)
    ?? inferredShortcutSelectedIndex.value
  ));

  const parseDateValue = (val: any) => {
    if (!val || !Array.isArray(val) || val.length < 2) return [];
    return val.map((item: any) => {
      if (item instanceof Date) return item;
      if (typeof item === 'string' || typeof item === 'number') {
        const d = new Date(item);
        return isNaN(d.getTime()) ? item : d;
      }
      return item;
    });
  };

  const localValue = ref<any>(parseDateValue(props.tag.value));

  const inferredShortcutSelectedIndex = computed(() => {
    if (!Array.isArray(localValue.value) || localValue.value.length < 2) {
      return -1;
    }
    const start = dayjs(localValue.value[0]);
    const end = dayjs(localValue.value[1]);
    if (!start.isValid() || !end.isValid()) {
      return -1;
    }
    const now = dayjs();
    const endDiffMinutes = Math.abs(end.diff(now, 'minute'));
    if (endDiffMinutes > 5) {
      return -1;
    }
    const diffMinutes = end.diff(start, 'minute');
    return shortcutConfigs.findIndex(item => Math.abs(diffMinutes - (item.days * 24 * 60)) <= 2);
  });

  const handleChange = (value: any) => {
    if (!value || !Array.isArray(value) || value.length < 2) return;
    const formatted = value.map((item: any) => (
      typeof item === 'number' || item instanceof Date
        ? dayjs(item).format('YYYY-MM-DD HH:mm:ss')
        : item
    ));
    localValue.value = formatted;
    emit('update', props.tag.fieldName, formatted);
    if (pendingShortcutOrigin.value) {
      emit('update', 'datetime_origin', pendingShortcutOrigin.value);
      return;
    }
    pendingShortcutSelectedIndex.value = null;
    emit('update', 'datetime_origin', formatted);
  };

  const handleShortcutChange = (
    shortcut: { text: string; value: () => [Date, Date] },
    index: number,
  ) => {
    const shortcutConfig = shortcutConfigs[index];
    if (!shortcutConfig || typeof shortcut?.value !== 'function') {
      return;
    }
    pendingShortcutSelectedIndex.value = index;
    pendingShortcutOrigin.value = [shortcutConfig.origin, 'now'];
    localValue.value = shortcut.value();
    updateEditorWidth();
  };

  const handlePickSuccess = () => {
    isPanelOpen.value = false;
    emit('finishEdit');
  };

  watch(() => props.tag.value, (val) => {
    if (val) {
      localValue.value = parseDateValue(val);
    }
  }, { deep: true });

  watch(() => props.searchModel.datetime, (val) => {
    if (val && Array.isArray(val) && val.length >= 2) {
      localValue.value = parseDateValue(val);
    }
  }, { deep: true });

  watch(() => props.searchModel.datetime_origin, (val) => {
    const origin = Array.isArray(val) ? val : [];
    const pendingOrigin = pendingShortcutOrigin.value;
    if (pendingOrigin && pendingOrigin.join(',') === origin.join(',')) {
      pendingShortcutOrigin.value = null;
      pendingShortcutSelectedIndex.value = null;
      return;
    }
    if (pendingOrigin) {
      return;
    }
    if (!origin.length || typeof origin[0] !== 'string' || shortcutOriginMap[origin[0]] === undefined) {
      pendingShortcutOrigin.value = null;
      pendingShortcutSelectedIndex.value = null;
    }
  }, { deep: true });

  const getDisplayTextForInput = () => {
    if (shortcutSelectedIndex.value >= 0) {
      return t(shortcutConfigs[shortcutSelectedIndex.value].label);
    }
    return formatRangeText(localValue.value);
  };

  const displayText = computed(() => getDisplayTextForInput());

  const shortcutTooltipContent = computed(() => {
    if (shortcutSelectedIndex.value < 0) {
      return '';
    }
    return formatRangeText(localValue.value);
  });

  const shortcutTooltipOptions = computed(() => ({
    content: shortcutTooltipContent.value,
    disabled: !shortcutTooltipContent.value,
    extCls: 'nl-tag-tooltip-wrap',
  }));

  let updateWidthTimer: ReturnType<typeof setTimeout> | null = null;
  const updateEditorWidth = async () => {
    await nextTick();
    if (updateWidthTimer) {
      clearTimeout(updateWidthTimer);
    }
    updateWidthTimer = setTimeout(() => {
      const pickerEl = datePickerRef.value?.$el || datePickerRef.value;
      const editorInput = pickerEl?.querySelector('.bk-date-picker-editor') as HTMLInputElement | null;
      const valueWrapperEl = valueWrapperRef.value;
      if (pickerEl && editorInput) {
        const currentDisplayText = displayText.value;
        measureText.value = currentDisplayText || editorInput.value || '';
        nextTick(() => {
          if (measureRef.value) {
            const textWidth = measureRef.value.scrollWidth + 16; // 加上内边距余量
            const finalWidth = `${Math.max(40, textWidth)}px`;
            if (valueWrapperEl) {
              valueWrapperEl.style.width = finalWidth;
              valueWrapperEl.style.minWidth = finalWidth;
              valueWrapperEl.style.flex = '0 0 auto';
            }
            pickerEl.style.width = finalWidth;
            pickerEl.style.minWidth = finalWidth;
            pickerEl.style.flex = '0 0 auto';
            editorInput.style.width = finalWidth;
            editorInput.style.minWidth = finalWidth;
            const relEl = pickerEl.querySelector('.bk-date-picker-rel') as HTMLElement;
            if (relEl) {
              relEl.style.width = finalWidth;
              relEl.style.minWidth = finalWidth;
              relEl.style.flex = '0 0 auto';
            }
          }
        });
      }
    }, 0);
  };

  watch(localValue, () => {
    updateEditorWidth();
  }, { deep: true });

  watch(shortcutSelectedIndex, () => {
    updateEditorWidth();
  });

  watch(displayText, () => {
    updateEditorWidth();
  });

  watch(isPanelOpen, () => {
    updateEditorWidth();
  });

  onMounted(() => {
    document.addEventListener('click', handleDocumentClick, true);
    updateEditorWidth();
  });
  onBeforeUnmount(() => {
    document.removeEventListener('click', handleDocumentClick, true);
    if (updateWidthTimer) {
      clearTimeout(updateWidthTimer);
      updateWidthTimer = null;
    }
  });
</script>
<style lang="postcss" scoped>
  .condition-tag-date-item {
    .tag-value-date-wrapper {
      position: relative;
      display: inline-flex;
      align-items: center;
      width: auto;
      max-width: fit-content;
      padding: 4px;
      white-space: nowrap;
      cursor: pointer;
      border-radius: 2px;
      transition: background .15s;

      .tag-date-display-text {
        max-width: none;
      }

      .tag-date-display-text-editing {
        position: absolute;
        top: 50%;
        left: 8px;
        z-index: 1;
        max-width: calc(100% - 16px);
        overflow: hidden;
        font-size: 12px;
        font-weight: 700;
        line-height: 22px;
        color: #4d4f56;
        white-space: nowrap;
        pointer-events: none;
        transform: translateY(-50%);
      }

      :deep(.nl-tag-date-picker),
      :deep(.bk-date-picker) {
        display: inline-flex;
        width: auto !important;
        max-width: fit-content;
        min-width: auto !important;
        background: transparent;
        border: none;
        flex: 0 0 auto;

        .bk-date-picker-rel {
          display: inline-flex;
          width: auto !important;
          max-width: fit-content;
          min-width: auto !important;
          flex: 0 0 auto;

          /* 隐藏日历图标容器 */
          .icon-wrapper {
            display: none;
          }

          /* 去掉为图标预留的左侧空间，调整尺寸，宽度根据内容自适应 */
          .bk-date-picker-editor {
            display: inline-block;
            width: auto !important;
            height: 22px;
            min-width: 40px;
            padding: 4px;
            font-size: 12px;
            font-weight: 700;
            line-height: 22px;
            color: transparent;
            text-overflow: clip;
            white-space: nowrap;
            cursor: pointer;
            background: transparent;
            border: none;
            box-shadow: none;
            user-select: none;
            caret-color: transparent;

            &:focus {
              border: none;
              box-shadow: none;
            }
          }

          /* 隐藏清除按钮 */
          .clear-action {
            display: none;
          }
        }
      }

    }

    /* 面板打开时（is-editing 状态）value 区域蓝色高亮 */
    &.is-editing {
      .tag-value-date-wrapper {
        background: #e1ecff;
        border-radius: 2px;

        :deep(.bk-date-picker) {
          .bk-date-picker-rel {
            .bk-date-picker-editor {
              color: transparent;
            }
          }
        }

        .tag-date-display-text-editing {
          color: #1768ef;
        }
      }
    }

    /* 隐藏的测量 span，与 input 保持相同字体样式，用于计算文本宽度 */
    .date-measure-span {
      position: absolute;
      top: 0;
      left: 0;
      height: 0;
      padding: 0 4px;
      overflow: hidden;
      font-family: inherit;
      font-size: 12px;
      font-weight: 700;
      line-height: 22px;
      white-space: pre;
      pointer-events: none;
      visibility: hidden;
    }
  }
</style>
