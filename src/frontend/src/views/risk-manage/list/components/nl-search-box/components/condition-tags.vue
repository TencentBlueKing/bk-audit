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
    <!-- 第一行：首个条件标签 + 清空按钮固定在最右侧 -->
    <div class="nl-condition-tags-first-row">
      <div class="nl-condition-tags-content">
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
            @finish-edit="handleDateFinishEdit"
            @remove="handleRemove"
            @start-edit="handleDateStartEdit"
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

        <!-- 事件字段条件标签 -->
        <tag-event-field
          v-for="item in eventFieldItems"
          :key="item.id"
          :condition-list="conditionList || []"
          :item="item"
          @finish-edit="handleEventFieldFinishEdit"
          @remove="handleRemoveEventField"
          @start-edit="handleEventFieldStartEdit"
          @update-operator="handleUpdateEventOperator"
          @update-value="handleUpdateEventValue" />

        <!-- 添加条件（slot） -->
        <slot />
      </div>

      <!-- 清空按钮固定在第一行最右侧（始终展示） -->
      <div
        class="condition-clear-btn"
        @click="handleClearAll">
        <img
          class="clear-icon"
          src="@/images/qingchu.svg">
        <span>{{ t('清空') }}</span>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { InfoBox } from 'bkui-vue';
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
    TagEventField,
    TagInput,
    TagSelect,
    TagUserSelector,
  } from './condition-tag-editors';

  interface Props {
    searchModel: Record<string, any>;
    fieldConfig: Record<string, IFieldConfig>;
    eventFieldItems?: Array<Record<string, any>>;
    conditionList?: Array<{ id: string; name: string }>;
  }
  interface Emits {
    (e: 'remove', fieldName: string): void;
    (e: 'clearAll'): void;
    (e: 'update', fieldName: string, value: any): void;
    (e: 'startEdit'): void;
    (e: 'finishEdit'): void;
    (e: 'removeEventField', id: string): void;
    (e: 'updateEventOperator', id: string, operator: string): void;
    (e: 'updateEventValue', id: string, value: any): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();

  const { t } = useI18n();

  // 当前正在编辑的字段
  const editingField = ref<string | null>(null);
  // 选项缓存（供 select 子组件复用）
  const optionsCache = ref<Record<string, Array<Record<string, any>>>>({});

  // ========================
  // 条件标签列表（根据 searchModel 中已有的字段动态展示，而非全部展示 fieldConfig）
  // ========================
  const conditionTags = computed<IConditionTag[]>(() => {
    const datetimeTags: IConditionTag[] = [];
    const otherTags: IConditionTag[] = [];

    // 先处理 datetime 类型（始终展示且排第一）
    Object.entries(props.fieldConfig).forEach(([fieldName, config]) => {
      if (config.type === 'datetimerange') {
        const value = props.searchModel[fieldName] || props.searchModel.datetime || [];
        datetimeTags.push({
          fieldName,
          label: config.label,
          value,
          type: config.type,
          config,
          removable: false, // 日期类型标签不可删除
        });
      }
    });

    // 其他字段：按 searchModel 中 key 的顺序遍历，确保新添加的字段排在最后
    Object.keys(props.searchModel).forEach((fieldName) => {
      // 跳过辅助字段和 datetime 类型
      if (fieldName === 'datetime' || fieldName === 'datetime_origin' || fieldName === 'sort') return;
      const config = props.fieldConfig[fieldName];
      if (!config) return;
      if (config.type === 'datetimerange') return;

      const value = props.searchModel[fieldName];
      otherTags.push({
        fieldName,
        label: config.label,
        value: (value !== undefined && value !== null) ? value : '',
        type: config.type,
        config,
        removable: true, // 可删除
      });
    });

    // 日期标签排第一，其余按 searchModel 中的添加顺序
    return [...datetimeTags, ...otherTags];
  });

  // 有条件才显示
  const hasConditions = computed(() => conditionTags.value.length > 0);

  // ========================
  // 编辑态控制
  // ========================
  const handleStartEdit = (fieldName: string) => {
    editingField.value = fieldName;
    // 通知父组件编辑开始，用于记录快照
    emit('startEdit');
  };

  const handleFinishEdit = () => {
    editingField.value = null;
    // 编辑面板关闭时，通知父组件触发搜索
    emit('finishEdit');
  };

  // 日期选择器面板关闭时的回调（日期选择器自行管理开关状态，不走 editingField）
  const handleDateFinishEdit = () => {
    emit('finishEdit');
  };

  // 日期选择器面板打开时的回调
  const handleDateStartEdit = () => {
    emit('startEdit');
  };

  // 事件字段编辑完成时的回调
  const handleEventFieldFinishEdit = () => {
    emit('finishEdit');
  };

  // 事件字段开始编辑时的回调
  const handleEventFieldStartEdit = () => {
    emit('startEdit');
  };

  const handleUpdate = (fieldName: string, value: any) => {
    emit('update', fieldName, value);
  };

  const handleUpdateCache = (fieldName: string, options: Array<Record<string, any>>) => {
    optionsCache.value[fieldName] = options;
  };

  // ========================
  // 事件字段操作
  // ========================
  const handleRemoveEventField = (id: string) => {
    emit('removeEventField', id);
  };

  const handleUpdateEventOperator = (id: string, operator: string) => {
    emit('updateEventOperator', id, operator);
  };

  const handleUpdateEventValue = (id: string, value: any) => {
    emit('updateEventValue', id, value);
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
    InfoBox({
      title: t('确认清空所有搜索条件？'),
      subTitle: t('清空后将恢复默认搜索条件'),
      confirmText: t('确定'),
      cancelText: t('取消'),
      headerAlign: 'center',
      contentAlign: 'center',
      footerAlign: 'center',
      onConfirm() {
        editingField.value = null;
        emit('clearAll');
      },
    });
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
    font-size: 12px;

    .nl-condition-tags-first-row {
      display: flex;
      align-items: flex-start;
      gap: 8px;
    }

    .nl-condition-tags-content {
      display: flex;
      flex: 1;
      flex-wrap: wrap;
      gap: 8px;
      align-items: flex-start;
      min-width: 0;
    }

    /* 所有条件标签的通用样式 */
    .condition-tag-item {
      position: relative;
      display: inline-flex;
      height: 26px;
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
      font-size: 12px;
      color: #979ba5;
      white-space: nowrap;
      cursor: pointer;
      transition: all .15s;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;

      .clear-icon {
        width: 14px;
        height: 14px;
        margin-right: 4px;
      }

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
  .bk-popover.bk-pop2-content[data-theme~='nl-tag-popover'] {
    padding: 0;
    pointer-events: auto !important;
  }

  /* tooltip 最大宽度限制，超出自动换行 */
  .nl-tag-tooltip-wrap {
    max-width: 400px;
    word-break: break-all;
    white-space: normal;
  }
</style>
