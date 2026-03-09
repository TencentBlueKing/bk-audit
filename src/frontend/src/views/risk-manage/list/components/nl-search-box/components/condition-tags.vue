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
    v-if="hasConditions"
    class="nl-condition-tags">
    <!-- 条件标签列表 -->
    <template
      v-for="tag in conditionTags"
      :key="tag.fieldName">
      <!-- 日期类型 -->
      <tag-datetimerange
        v-if="tag.type === 'datetimerange'"
        :is-editing="editingField === tag.fieldName"
        :removable="tag.removable"
        :search-model="searchModel"
        :tag="tag"
        @finish-edit="handleFinishEdit"
        @remove="handleRemove"
        @start-edit="handleStartEdit"
        @update="handleUpdate" />

      <!-- 下拉选择类型 -->
      <tag-select
        v-else-if="tag.type === 'select'"
        :is-editing="editingField === tag.fieldName"
        :options-cache="optionsCache"
        :search-model="searchModel"
        :tag="tag"
        @finish-edit="handleFinishEdit"
        @remove="handleRemove"
        @start-edit="handleStartEdit"
        @update="handleUpdate"
        @update-cache="handleUpdateCache" />

      <!-- 人员选择类型 -->
      <tag-user-selector
        v-else-if="tag.type === 'user-selector'"
        :is-editing="editingField === tag.fieldName"
        :search-model="searchModel"
        :tag="tag"
        @finish-edit="handleFinishEdit"
        @remove="handleRemove"
        @start-edit="handleStartEdit"
        @update="handleUpdate" />

      <!-- 输入类型 -->
      <tag-input
        v-else
        :is-editing="editingField === tag.fieldName"
        :search-model="searchModel"
        :tag="tag"
        @finish-edit="handleFinishEdit"
        @remove="handleRemove"
        @start-edit="handleStartEdit"
        @update="handleUpdate" />
    </template>

    <!-- 清空按钮 -->
    <div
      v-if="conditionTags.length > 1"
      v-bk-tooltips="t('清空搜索条件')"
      class="condition-clear-btn"
      @click="handleClearAll">
      <audit-icon type="delete-fill" />
    </div>
  </div>
</template>
<script setup lang="ts">
  import {
    computed,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type { IFieldConfig } from '@components/search-box/components/render-field-config/config';

  import type { IConditionTag } from '../types';

  import {
    TagDatetimerange,
    TagInput,
    TagSelect,
    TagUserSelector,
  } from './condition-tag-editors';

  interface Props {
    searchModel: Record<string, any>;
    fieldConfig: Record<string, IFieldConfig>;
  }
  interface Emits {
    (e: 'remove', fieldName: string): void;
    (e: 'clearAll'): void;
    (e: 'update', fieldName: string, value: any): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();

  const { t } = useI18n();

  // 当前正在编辑的字段
  const editingField = ref<string | null>(null);
  // 选项缓存（供 select 子组件复用）
  const optionsCache = ref<Record<string, Array<Record<string, any>>>>({});

  // ========================
  // 条件标签列表（全部展示 fieldConfig 中的字段，后续对接接口再改为动态展示）
  // ========================
  const conditionTags = computed<IConditionTag[]>(() => {
    const tags: IConditionTag[] = [];
    // 首先放入 datetimerange 类型的标签（首次发现时间），确保排第一且不可删除
    const datetimeTags: IConditionTag[] = [];
    const otherTags: IConditionTag[] = [];

    Object.entries(props.fieldConfig).forEach(([fieldName, config]) => {
      // 从 searchModel 中获取值，没有则给默认空值
      const value = props.searchModel[fieldName];
      const defaultValue = (() => {
        switch (config.type) {
        case 'select':
        case 'user-selector':
          return [];
        case 'datetimerange':
          return props.searchModel.datetime || [];
        default:
          return '';
        }
      })();

      const tag: IConditionTag = {
        fieldName,
        label: config.label,
        value: (value !== undefined && value !== null) ? value : defaultValue,
        type: config.type,
        config,
        removable: config.type !== 'datetimerange', // 日期类型标签不可删除
      };

      if (config.type === 'datetimerange') {
        datetimeTags.push(tag);
      } else {
        otherTags.push(tag);
      }
    });

    // 日期标签排第一，其余保持原顺序
    tags.push(...datetimeTags, ...otherTags);
    return tags;
  });

  // 全部展示模式下始终为 true
  const hasConditions = computed(() => conditionTags.value.length > 0);

  // ========================
  // 编辑态控制
  // ========================
  const handleStartEdit = (fieldName: string) => {
    editingField.value = fieldName;
  };

  const handleFinishEdit = () => {
    editingField.value = null;
  };

  const handleUpdate = (fieldName: string, value: any) => {
    emit('update', fieldName, value);
  };

  const handleUpdateCache = (fieldName: string, options: Array<Record<string, any>>) => {
    optionsCache.value[fieldName] = options;
  };

  // ========================
  // 移除 / 清空
  // ========================
  const handleRemove = (fieldName: string) => {
    if (editingField.value === fieldName) {
      editingField.value = null;
    }
    emit('remove', fieldName);
  };

  const handleClearAll = () => {
    editingField.value = null;
    emit('clearAll');
  };

  // 监听 searchModel 变化
  watch(() => props.searchModel, () => {
    if (editingField.value) {
      const currentTag = conditionTags.value.find(item => item.fieldName === editingField.value);
      if (!currentTag) {
        editingField.value = null;
      }
    }
  }, { deep: true });
</script>
<style lang="postcss">
  .nl-condition-tags {
    display: flex;
    font-size: 12px;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;

    /* 所有条件标签的通用样式 */
    .condition-tag-item {
      position: relative;
      display: inline-flex;
      height: 22px;
      max-width: 100%;
      padding: 3px 8px;
      font-size: 12px;
      color: #63656e;
      cursor: pointer;
      background: #fff;
      border-radius: 2px;
      transition: all .15s;
      align-items: center;

      &:hover {
        .tag-value-wrapper {
          background: #f0f1f5;
          border-radius: 2px;
        }

        .tag-remove-btn {
          color: #63656e;
        }
      }

      &.is-editing {
        .tag-value-wrapper {
          background: #e1ecff;
          border-radius: 2px;
        }

        .tag-value {
          color: #1768ef;
        }
      }

      .tag-view-content {
        display: inline-flex;
        align-items: center;
      }

      .tag-label {
        margin-right: 2px;
        color: #4d4f56;
        white-space: nowrap;
      }

      .tag-value-wrapper {
        display: inline-flex;
        padding: 0 4px;
        transition: background .15s;
        align-items: center;
      }

      .tag-value-icon {
        margin-right: 4px;
        font-size: 14px;
        color: #979ba5;
      }

      .tag-value {
        display: inline-block;
        max-width: 260px;
        overflow: hidden;
        font-weight: 700;
        color: #4d4f56;
        text-overflow: ellipsis;
        word-break: keep-all;
        white-space: nowrap;
      }

      .tag-remove-btn {
        margin-left: 6px;
        font-size: 12px;
        color: #979ba5;
        transition: color .15s;

        &:hover {
          color: #ea3636 !important;
        }
      }
    }

    .condition-clear-btn {
      display: flex;
      height: 22px;
      color: #c4c6cc;
      cursor: pointer;
      align-items: center;
      justify-content: center;
      transition: all .15s;

      &:hover {
        color: #ea3636;
      }
    }
  }

  /* popover 内编辑器的通用样式 */
  .nl-tag-editor-popover {
    min-width: 200px;
  }

  /* popover 主题样式 - 去掉默认padding */
  .tippy-box[data-theme~='nl-tag-popover'] {
    .tippy-content {
      padding: 0;
    }
  }
</style>
