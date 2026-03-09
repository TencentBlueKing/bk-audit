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
        @change="handleChange"
        @shortcut-change="handleShortcutChange" />
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
  const isPanelOpen = ref(false);

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

  // 快捷选项变更时，仅更新值不关闭面板
  const handleShortcutChange = (shortcut: any) => {
    if (shortcut && typeof shortcut.value === 'function') {
      const range = shortcut.value();
      if (Array.isArray(range) && range.length >= 2) {
        handleChange(range);
      }
    }
  };

  // 点击外部区域关闭面板
  const handleDocumentClick = (e: MouseEvent) => {
    if (!isPanelOpen.value) return;
    const target = e.target as HTMLElement;
    // 点击在标签自身内部 → 不关闭（由 handleTogglePanel 控制）
    if (tagRef.value?.contains(target)) return;
    // 点击在日期面板弹出层内部 → 不关闭
    const pickerDropdowns = document.querySelectorAll('.bk-date-picker-dropdown');
    for (const dropdown of pickerDropdowns) {
      if (dropdown.contains(target)) return;
    }
    // 其他区域 → 关闭面板
    isPanelOpen.value = false;
  };

  onMounted(() => {
    document.addEventListener('click', handleDocumentClick, true);
  });

  onBeforeUnmount(() => {
    document.removeEventListener('click', handleDocumentClick, true);
  });

  // 快捷选项配置（参照用户提供的第二个输入框）
  const shortcutsRange = [
    {
      text: t('近1天'),
      value() {
        const end = new Date();
        const start = new Date();
        start.setTime(start.getTime() - 3600 * 1000 * 24 * 1);
        return [start, end];
      },
    },
    {
      text: t('近3天'),
      value() {
        const end = new Date();
        const start = new Date();
        start.setTime(start.getTime() - 3600 * 1000 * 24 * 3);
        return [start, end];
      },
    },
    {
      text: t('近7天'),
      value() {
        const end = new Date();
        const start = new Date();
        start.setTime(start.getTime() - 3600 * 1000 * 24 * 7);
        return [start, end];
      },
    },
    {
      text: t('近14天'),
      value() {
        const end = new Date();
        const start = new Date();
        start.setTime(start.getTime() - 3600 * 1000 * 24 * 14);
        return [start, end];
      },
    },
    {
      text: t('近1月'),
      value() {
        const end = new Date();
        const start = new Date();
        start.setTime(start.getTime() - 3600 * 1000 * 24 * 30);
        return [start, end];
      },
    },
    {
      text: t('近3月'),
      value() {
        const end = new Date();
        const start = new Date();
        start.setTime(start.getTime() - 3600 * 1000 * 24 * 90);
        return [start, end];
      },
    },
    {
      text: t('近6月'),
      value() {
        const end = new Date();
        const start = new Date();
        start.setTime(start.getTime() - 3600 * 1000 * 24 * 182);
        return [start, end];
      },
    },
    {
      text: t('近12月'),
      value() {
        const end = new Date();
        const start = new Date();
        start.setTime(start.getTime() - 3600 * 1000 * 24 * 365);
        return [start, end];
      },
    },
  ];

  // 快捷选项 origin 值到索引的映射
  const shortcutOriginMap: Record<string, number> = {
    'now-1d': 0,
    'now-3d': 1,
    'now-7d': 2,
    'now-14d': 3,
    'now-1M': 4,
    'now-3M': 5,
    'now-6M': 6,
    'now-12M': 7,
  };

  // 根据 datetime_origin 确定默认选中的快捷索引
  const shortcutSelectedIndex = computed(() => {
    const origin = props.searchModel.datetime_origin;
    if (Array.isArray(origin) && origin.length > 0) {
      const idx = shortcutOriginMap[origin[0]];
      if (idx !== undefined) return idx;
    }
    // 默认选中"近6月"
    return 5;
  });

  // 本地值（日期范围数组）
  const localValue = ref<any>(props.tag.value || []);

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
      localValue.value = val;
    }
  }, { deep: true });
</script>
<style lang="postcss" scoped>
  .condition-tag-date-item {
    .tag-value-date-wrapper {
      padding: 4px;
      cursor: pointer;
      border-radius: 2px;
      transition: background .15s;

      :deep(.bk-date-picker) {
        width: auto;
        background: transparent;
        border: none;

        .bk-date-picker-rel {
          /* 隐藏日历图标容器 */
          .icon-wrapper {
            display: none;
          }

          /* 去掉为图标预留的左侧空间，调整尺寸 */
          .bk-date-picker-editor {
            height: 22px;
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
  }
</style>

<!-- 全局样式：隐藏日期选择器弹出面板中的确定/清除按钮区域 -->
<style lang="postcss">
  .bk-picker-confirm {
    display: none !important;
  }
</style>
