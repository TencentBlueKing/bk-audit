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
  <bk-popover
    ref="popoverRef"
    :arrow="false"
    ext-cls="nl-add-condition-popover"
    :is-show="isShow"
    placement="bottom-start"
    theme="light"
    trigger="click"
    @after-hidden="isShow = false">
    <span
      class="nl-add-condition-trigger"
      :class="{ 'is-active': isShow }"
      @click="isShow = !isShow">
      <audit-icon
        class="nl-add-condition-icon"
        type="add" />
      <span>{{ t('添加条件') }}</span>
    </span>
    <template #content>
      <div class="nl-add-condition-panel">
        <!-- Tab 切换：风险字段 / 事件字段 -->
        <div class="panel-tabs">
          <span
            class="panel-tab-item"
            :class="{ active: activeTab === 'risk' }"
            @click="activeTab = 'risk'">
            {{ t('风险字段') }}
          </span>
          <span
            class="panel-tab-item"
            :class="{ active: activeTab === 'event' }"
            @click="activeTab = 'event'">
            {{ t('事件字段') }}
          </span>
        </div>

        <!-- 搜索过滤 -->
        <div class="panel-search">
          <audit-icon
            class="nl-tag-search-icon"
            type="search1" />
          <bk-input
            v-model="searchKeyword"
            clearable
            :placeholder="t('搜索字段名称')"
            prefix-icon="bk-icon icon-search"
            size="small" />
        </div>
        <!-- 字段列表 -->
        <div class="panel-field-list">
          <template v-if="activeTab === 'risk'">
            <div
              v-for="(config, fieldName) in filteredRiskFields"
              :key="fieldName"
              class="field-item"
              @click="handleSelectField(fieldName as string, config)">
              <span
                v-bk-tooltips="{
                  content: t(config.label),
                  disabled: !overflowFlags[`risk_${fieldName}`],
                }"
                class="field-item-label"
                @mouseenter="(e: MouseEvent) => checkOverflow(`risk_${fieldName}`, e)">
                {{ t(config.label) }}
              </span>
            </div>
          </template>
          <template v-else>
            <div
              v-for="item in filteredEventFields"
              :key="item.id"
              class="field-item"
              @click="handleSelectEventField(item)">
              <span
                v-bk-tooltips="{
                  content: `${item.display_name}[${item.field_name}]`,
                  disabled: !overflowFlags[`event_${item.id}`],
                }"
                class="field-item-label"
                @mouseenter="(e: MouseEvent) => checkOverflow(`event_${item.id}`, e)">
                {{ `${item.display_name}[${item.field_name}]` }}
              </span>
            </div>
          </template>

          <!-- 空状态 -->
          <div
            v-if="isListEmpty"
            class="field-list-empty">
            {{ t('暂无匹配字段') }}
          </div>
        </div>
      </div>
    </template>
  </bk-popover>
</template>
<script setup lang="ts">
  import {
    computed,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type { IFieldConfig } from '@components/search-box/components/render-field-config/config';

  interface Props {
    fieldConfig: Record<string, IFieldConfig>;
    selectedFields: string[];       // 已选中的风险字段名列表
    eventFields: Array<Record<string, any>>;   // 可用的事件字段列表
    selectedEventFieldIds: string[]; // 已选中的事件字段 ID 列表
  }
  interface Emits {
    (e: 'addField', fieldName: string, config: IFieldConfig): void;
    (e: 'addEventField', item: Record<string, any>): void;
    (e: 'removeEventField', id: string): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const popoverRef = ref();
  const isShow = ref(false);
  // 记录每个字段项是否溢出，用于控制 tooltip 显示
  const overflowFlags = ref<Record<string, boolean>>({});

  // 鼠标进入时检测 DOM 元素文字是否溢出
  const checkOverflow = (key: string, e: MouseEvent) => {
    const el = e.target as HTMLElement;
    if (el) {
      overflowFlags.value[key] = el.scrollWidth > el.clientWidth;
    }
  };
  const activeTab = ref<'risk' | 'event'>('risk');
  const searchKeyword = ref('');

  // 过滤风险字段（排除已添加的字段，且排除 datetimerange 类型，因为首次发现时间始终存在不可添加）
  const filteredRiskFields = computed(() => {
    const keyword = searchKeyword.value.trim().toLowerCase();

    return Object.entries(props.fieldConfig).reduce((acc, [name, config]) => {
      // 排除已选中的字段
      if (props.selectedFields.includes(name)) return acc;
      // 排除 datetimerange 类型（首次发现时间始终展示，无需手动添加）
      if (config.type === 'datetimerange') return acc;
      // 搜索过滤
      if (keyword && !config.label.toLowerCase().includes(keyword) && !name.toLowerCase().includes(keyword)) {
        return acc;
      }
      Object.assign(acc, { [name]: config });
      return acc;
    }, {} as Record<string, IFieldConfig>);
  });

  // 过滤事件字段（排除已添加的字段）
  const filteredEventFields = computed(() => {
    const keyword = searchKeyword.value.trim().toLowerCase();
    let list = props.eventFields.filter(item => !props.selectedEventFieldIds.includes(item.id));

    if (keyword) {
      list = list.filter(item => item.display_name.toLowerCase().includes(keyword)
        || item.field_name.toLowerCase().includes(keyword));
    }
    return list;
  });

  // 列表是否为空
  const isListEmpty = computed(() => {
    if (activeTab.value === 'risk') {
      return Object.keys(filteredRiskFields.value).length === 0;
    }
    return filteredEventFields.value.length === 0;
  });

  // 选择风险字段（点击后添加并关闭下拉）
  const handleSelectField = (fieldName: string, config: IFieldConfig) => {
    emit('addField', fieldName, config);
    isShow.value = false;
  };

  // 选择事件字段（点击后添加并关闭下拉）
  const handleSelectEventField = (item: Record<string, any>) => {
    emit('addEventField', item);
    isShow.value = false;
  };
</script>
<style lang="postcss">
  .nl-add-condition-trigger {
    display: inline-flex;
    height: 26px;
    padding: 7px 10px;
    font-size: 12px;
    color: #4d4f56;
    white-space: nowrap;
    cursor: pointer;
    background: transparent;
    border: 1px dashed #c4c6cc;
    border-radius: 2px;
    transition: all .15s;
    align-items: center;

    .nl-add-condition-icon {
      margin-right: 4px;
      color: #979ba5;
      transition: color .15s;
    }

    &:hover {
      color: #63656e;
      background: #fff;
      border-color: #c4c6cc;
    }

    &.is-active,
    &:active {
      color: #3a84ff;
      background: transparent;
      border-color: #3a84ff;

      .nl-add-condition-icon {
        color: #3a84ff;
      }
    }
  }

  .nl-add-condition-panel {
    width: max-content;
    max-width: 400px;
    min-width: 240px;
    padding: 0;
    gap: 9px;

    .panel-tabs {
      display: flex;
      gap: 8px;
      padding: 4px;
      background-color: #f0f1f5;

      .panel-tab-item {
        display: inline-flex;
        height: 22px;
        padding: 0 30px;
        font-size: 12px;
        line-height: 32px;
        color: #63656e;
        text-align: center;
        cursor: pointer;
        background: transparent;
        border: 1px solid transparent;
        transition: all .15s;
        align-items: center;
        justify-content: center;
        flex: 1;

        &.active {
          color: #3a84ff;
          background: #fff;
        }
      }
    }

    .panel-search {
      display: flex;
      padding: 4px 12px;
      margin-bottom: 2px;
      border-bottom: 1px solid #dcdee5;
      align-items: center;

      .nl-tag-search-icon {
        margin-right: 6px;
        font-size: 15px;
        color: #979ba5;
        flex-shrink: 0;
      }

      .bk-input {
        border: none;
        border-radius: 0;
        box-shadow: none;

        &.is-focused {
          border-bottom-color: #3a84ff;
          box-shadow: none;
        }
      }
    }

    .panel-field-list {
      max-height: 260px;
      padding-bottom: 4px;
      overflow: hidden auto;

      /* 窄灰色滚动条 - 纵向 */
      &::-webkit-scrollbar {
        width: 4px;
        height: 4px;
      }

      &::-webkit-scrollbar-thumb {
        background: #c4c6cc;
        border-radius: 2px;
      }

      &::-webkit-scrollbar-track {
        background: transparent;
      }

      .field-item {
        display: flex;
        min-height: 36px;
        padding: 6px 16px;
        font-size: 12px;
        color: #63656e;
        cursor: pointer;
        align-items: center;
        justify-content: space-between;
        transition: background .15s;

        &:hover {
          background: #f5f7fa;
        }

        &.is-selected {
          color: #3a84ff;
        }

        .field-item-label {
          min-width: 0;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          flex: 1;
        }
      }

      .field-list-empty {
        padding: 24px 0;
        font-size: 12px;
        color: #c4c6cc;
        text-align: center;
      }
    }
  }

  /* popover 主题样式 - 减少默认 padding */
  .nl-add-condition-popover.bk-popover.bk-pop2-content {
    padding: 6px;
  }
</style>
