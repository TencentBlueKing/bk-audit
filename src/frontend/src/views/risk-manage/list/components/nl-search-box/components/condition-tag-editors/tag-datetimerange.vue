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
        :open="panelOpenState"
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
    // eslint-disable-next-line vue/no-unused-properties
    searchModel: Record<string, any>;
    // eslint-disable-next-line vue/no-unused-properties
    isEditing: boolean;
    // eslint-disable-next-line vue/no-unused-properties
    removable?: boolean;
  }
  interface Emits {
    (e: 'startEdit', fieldName: string): void;
    (e: 'update', fieldName: string, value: any): void;
    (e: 'remove', fieldName: string): void;
    (e: 'finishEdit'): void;
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

  // bk-date-picker 的 open prop：
  // - null: 由组件自身管理显隐（默认行为）
  // - true/false: 由外部完全接管显隐
  // 我们使用 null 作为初始值，点击时设为 true 打开面板，
  // 之后保持 true（选择日期不关闭），只在点击外部时设为 false
  // panelOpenState 控制 bk-date-picker 面板显隐：
  // - true: 强制面板保持打开（选择日期后也不关闭）
  // - false: 强制面板关闭
  // 不再使用 null，完全由外部接管控制，避免组件内部自动关闭
  const panelOpenState = computed(() => isPanelOpen.value);

  // 点击 value 区域打开面板
  const handleTogglePanel = () => {
    isPanelOpen.value = !isPanelOpen.value;
  };

  // 快捷选项 text 到 origin 值的映射
  const shortcutTextToOriginMap: Record<string, string> = {};

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


  // 快捷选项统一数据源：label（国际化文本）、days（往前推的天数）、origin（后端 origin 标识）
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

  // 生成 bk-date-picker 所需的 shortcuts 配置
  const shortcutsRange = shortcutConfigs.map(({ label, days }) => ({
    text: t(label),
    value() {
      const end = new Date();
      const start = new Date();
      start.setTime(start.getTime() - 3600 * 1000 * 24 * days);
      return [start, end];
    },
  }));

  // 快捷选项 origin 值到索引的映射
  const shortcutOriginMap: Record<string, number> = {};
  shortcutConfigs.forEach((item, idx) => {
    shortcutOriginMap[item.origin] = idx;
  });

  // 初始化 快捷选项 text → origin 值 的映射
  shortcutsRange.forEach((item, idx) => {
    shortcutTextToOriginMap[item.text] = shortcutConfigs[idx].origin;
  });

  // 根据 datetime_origin 确定默认选中的快捷索引
  const shortcutSelectedIndex = computed(() => {
    const origin = props.searchModel.datetime_origin;
    if (Array.isArray(origin) && origin.length > 0) {
      const idx = shortcutOriginMap[origin[0]];
      if (idx !== undefined) return idx;
    }
    // 当 datetime_origin 不匹配任何快捷选项时（如后端返回的具体日期），返回 -1 表示无选中
    return -1;
  });

  // 将字符串日期转成 Date 对象，确保 bk-date-picker 能正确回显
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

  // 本地值（日期范围数组）
  const localValue = ref<any>(parseDateValue(props.tag.value));

  // 日期变更
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

  // 同步外部值变化
  watch(() => props.tag.value, (val) => {
    if (val) {
      localValue.value = parseDateValue(val);
    }
  }, { deep: true });

  // 同步 searchModel.datetime 变化（后端返回具体日期时触发）
  watch(() => props.searchModel.datetime, (val) => {
    if (val && Array.isArray(val) && val.length >= 2) {
      localValue.value = parseDateValue(val);
    }
  }, { deep: true });

  // 当 shortcutSelectedIndex 为 -1（后端返回具体日期，不匹配任何快捷选项）时，
  // use-shortcut-text 模式下输入框不会自动显示日期文本，需要手动设置
  const getDisplayTextForInput = () => {
    if (shortcutSelectedIndex.value >= 0) {
      // 匹配快捷选项，use-shortcut-text 会自动处理显示
      return '';
    }
    // 不匹配快捷选项，需要手动构建日期显示文本
    const val = localValue.value;
    if (!val || !Array.isArray(val) || val.length < 2) return '';
    const start = val[0] instanceof Date ? dayjs(val[0]).format('YYYY-MM-DD') : val[0];
    const end = val[1] instanceof Date ? dayjs(val[1]).format('YYYY-MM-DD') : val[1];
    if (!start || !end) return '';
    return `${start} - ${end}`;
  };

  // 动态调整 input 宽度以匹配显示文本，同时收缩外层容器消除空白
  let updateWidthTimer: ReturnType<typeof setTimeout> | null = null;
  const updateEditorWidth = async () => {
    await nextTick();
    // 清理上一次的定时器，避免重复执行
    if (updateWidthTimer) {
      clearTimeout(updateWidthTimer);
    }
    // 等待 DOM 更新后再获取 input 显示的文本
    updateWidthTimer = setTimeout(() => {
      const pickerEl = datePickerRef.value?.$el || datePickerRef.value;
      const editorInput = pickerEl?.querySelector('.bk-date-picker-editor') as HTMLInputElement | null;
      if (pickerEl && editorInput) {
        // 当不匹配快捷选项时，手动将具体日期写入输入框
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
            // 同时收缩外层 .bk-date-picker-rel 容器，消除多余空白
            const relEl = pickerEl.querySelector('.bk-date-picker-rel') as HTMLElement;
            if (relEl) {
              relEl.style.width = finalWidth;
            }
          }
        });
      }
    }, 0);
  };

  // 值变化时重新计算宽度
  watch(localValue, () => {
    updateEditorWidth();
  }, { deep: true });

  // 快捷选项选中变化时重新计算宽度
  watch(shortcutSelectedIndex, () => {
    updateEditorWidth();
  });

  // 组件挂载后首次计算宽度
  onMounted(() => {
    document.addEventListener('click', handleDocumentClick, true);
    updateEditorWidth();
  });
  onBeforeUnmount(() => {
    document.removeEventListener('click', handleDocumentClick, true);
    // 清理 updateEditorWidth 中的定时器
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
