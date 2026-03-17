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
      class="tag-value-wrapper tag-value-date-wrapper">
      <bk-date-picker
        ref="datePickerRef"
        v-model="localValue"
        append-to-body
        :clearable="false"
        format="yyyy-MM-dd"
        :open="isPanelOpen"
        :shortcut-selected-index="shortcutSelectedIndex"
        :shortcuts="shortcutsRange"
        type="daterange"
        use-shortcut-text
        @change="handleChange" />
      <!-- 隐藏的测量元素，用于动态计算日期文本宽度 -->
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
  }

  const props = withDefaults(defineProps<Props>(), {
    removable: true,
  });
  const emit = defineEmits<Emits>();
  const { t } = useI18n();

  const tagRef = ref<HTMLElement>();
  const datePickerRef = ref();
  const measureRef = ref<HTMLSpanElement>();
  const isPanelOpen = ref(false);
  const measureText = ref('');

  const handleTogglePanel = () => {
    isPanelOpen.value = !isPanelOpen.value;
  };

  // 点击外部区域关闭面板
  const handleDocumentClick = (e: MouseEvent) => {
    if (!isPanelOpen.value) return;
    const target = e.target as HTMLElement;
    // 点击在标签自身内部 → 不关闭（由 handleTogglePanel 控制）
    if (tagRef.value?.contains(target)) return;
    // 点击在日期面板弹出层内部 → 不关闭
    const pickerDropdowns = document.querySelectorAll('.bk-date-picker-dropdown');
    for (const dropdown of Array.from(pickerDropdowns)) {
      if (dropdown.contains(target)) return;
    }
    // 其他区域 → 关闭面板
    isPanelOpen.value = false;
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

  const shortcutSelectedIndex = computed(() => {
    const origin = props.searchModel.datetime_origin;
    if (Array.isArray(origin) && origin.length > 0) {
      const idx = shortcutOriginMap[origin[0]];
      if (idx !== undefined) return idx;
    }
    return -1;
  });

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

  const handleChange = (value: any) => {
    if (!value || !Array.isArray(value) || value.length < 2) return;
    const formatted = value.map((item: any) => (
      typeof item === 'number' || item instanceof Date
        ? dayjs(item).format('YYYY-MM-DD')
        : item
    ));
    localValue.value = formatted;
    emit('update', props.tag.fieldName, formatted);
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

  const getDisplayTextForInput = () => {
    if (shortcutSelectedIndex.value >= 0) {
      return '';
    }
    const val = localValue.value;
    if (!val || !Array.isArray(val) || val.length < 2) return '';
    const start = val[0] instanceof Date ? dayjs(val[0]).format('YYYY-MM-DD') : val[0];
    const end = val[1] instanceof Date ? dayjs(val[1]).format('YYYY-MM-DD') : val[1];
    if (!start || !end) return '';
    return `${start} - ${end}`;
  };

  let updateWidthTimer: ReturnType<typeof setTimeout> | null = null;
  const updateEditorWidth = async () => {
    await nextTick();
    if (updateWidthTimer) {
      clearTimeout(updateWidthTimer);
    }
    updateWidthTimer = setTimeout(() => {
      const pickerEl = datePickerRef.value?.$el || datePickerRef.value;
      const editorInput = pickerEl?.querySelector('.bk-date-picker-editor') as HTMLInputElement | null;
      if (pickerEl && editorInput) {
        const manualText = getDisplayTextForInput();
        if (manualText) {
          editorInput.value = manualText;
        }

        const displayText = editorInput.value || '';
        measureText.value = displayText;
        nextTick(() => {
          if (measureRef.value) {
            const textWidth = measureRef.value.scrollWidth + 16; // 加上内边距余量
            const finalWidth = `${Math.max(40, textWidth)}px`;
            editorInput.style.width = finalWidth;
            const relEl = pickerEl.querySelector('.bk-date-picker-rel') as HTMLElement;
            if (relEl) {
              relEl.style.width = finalWidth;
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
      padding: 4px;
      cursor: pointer;
      border-radius: 2px;
      transition: background .15s;

      :deep(.bk-date-picker) {
        display: inline-flex;
        width: auto;
        background: transparent;
        border: none;

        .bk-date-picker-rel {
          display: inline-flex;
          width: auto;

          /* 隐藏日历图标容器 */
          .icon-wrapper {
            display: none;
          }

          /* 去掉为图标预留的左侧空间，调整尺寸，宽度根据内容自适应 */
          .bk-date-picker-editor {
            width: auto;
            height: 22px;
            min-width: 40px;
            padding: 4px;
            font-size: 12px;
            font-weight: 700;
            line-height: 22px;
            color: #4d4f56;
            cursor: pointer;
            background: transparent;
            border: none;
            box-shadow: none;

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
              color: #1768ef;
            }
          }
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

<!-- 全局样式：隐藏日期选择器弹出面板中的确定/清除按钮区域 -->
<style lang="postcss">
  .bk-picker-confirm {
    display: none !important;
  }
</style>
