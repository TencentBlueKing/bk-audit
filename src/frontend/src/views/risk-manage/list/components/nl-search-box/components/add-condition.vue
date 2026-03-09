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
    :is-show="isShow"
    placement="bottom-start"
    theme="light"
    trigger="click"
    @after-hidden="isShow = false">
    <span
      class="nl-add-condition-trigger"
      @click="isShow = !isShow">
      <audit-icon
        style="margin-right: 4px;"
        type="add" />
      <span>{{ t('添加条件') }}</span>
    </span>
    <template #content>
      <div class="nl-add-condition-panel">
        <!-- Tab 切换：风险字段 / 事件字段 -->
        <div class="panel-tabs">
          <div
            class="panel-tab-item"
            :class="{ active: activeTab === 'risk' }"
            @click="activeTab = 'risk'">
            {{ t('风险字段') }}
          </div>
          <div
            v-if="eventFields.length > 0"
            class="panel-tab-item"
            :class="{ active: activeTab === 'event' }"
            @click="activeTab = 'event'">
            {{ t('事件字段') }}
          </div>
        </div>

        <!-- 搜索过滤 -->
        <div class="panel-search">
          <bk-input
            v-model="searchKeyword"
            clearable
            :placeholder="t('搜索字段')"
            size="small" />
        </div>

        <!-- 字段列表 -->
        <div class="panel-field-list">
          <template v-if="activeTab === 'risk'">
            <div
              v-for="(config, fieldName) in filteredRiskFields"
              :key="fieldName"
              class="field-item"
              :class="{ 'is-selected': isFieldSelected(fieldName as string) }"
              @click="handleSelectField(fieldName as string, config)">
              <span>{{ t(config.label) }}</span>
              <audit-icon
                v-if="isFieldSelected(fieldName as string)"
                style="color: #3a84ff;"
                type="check-line" />
            </div>
          </template>
          <template v-else>
            <div
              v-for="item in filteredEventFields"
              :key="item.id"
              class="field-item"
              :class="{ 'is-selected': isEventFieldSelected(item.id) }"
              @click="handleSelectEventField(item)">
              <span>{{ `${item.display_name}[${item.field_name}]` }}</span>
              <audit-icon
                v-if="isEventFieldSelected(item.id)"
                style="color: #3a84ff;"
                type="check-line" />
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
  const activeTab = ref<'risk' | 'event'>('risk');
  const searchKeyword = ref('');

  // 过滤风险字段
  const filteredRiskFields = computed(() => {
    const keyword = searchKeyword.value.trim().toLowerCase();
    if (!keyword) return props.fieldConfig;

    return Object.entries(props.fieldConfig).reduce((acc, [name, config]) => {
      if (config.label.toLowerCase().includes(keyword) || name.toLowerCase().includes(keyword)) {
        Object.assign(acc, { [name]: config });
      }
      return acc;
    }, {} as Record<string, IFieldConfig>);
  });

  // 过滤事件字段
  const filteredEventFields = computed(() => {
    const keyword = searchKeyword.value.trim().toLowerCase();
    if (!keyword) return props.eventFields;

    return props.eventFields.filter(item => item.display_name.toLowerCase().includes(keyword)
      || item.field_name.toLowerCase().includes(keyword));
  });

  // 列表是否为空
  const isListEmpty = computed(() => {
    if (activeTab.value === 'risk') {
      return Object.keys(filteredRiskFields.value).length === 0;
    }
    return filteredEventFields.value.length === 0;
  });

  // 判断风险字段是否已选中
  const isFieldSelected = (fieldName: string) => props.selectedFields.includes(fieldName);

  // 判断事件字段是否已选中
  const isEventFieldSelected = (id: string) => props.selectedEventFieldIds.includes(id);

  // 选择风险字段
  const handleSelectField = (fieldName: string, config: IFieldConfig) => {
    emit('addField', fieldName, config);
  };

  // 选择/取消事件字段
  const handleSelectEventField = (item: Record<string, any>) => {
    if (isEventFieldSelected(item.id)) {
      emit('removeEventField', item.id);
    } else {
      emit('addEventField', item);
    }
  };
</script>
<style lang="postcss">
  .nl-add-condition-trigger {
    display: inline-flex;
    height: 22px;
    padding: 0 8px;
    margin-bottom: 4px;
    font-size: 12px;
    color: #3a84ff;
    cursor: pointer;
    align-items: center;
    transition: all .15s;

    &:hover {
      color: #699df4;
    }
  }

  .nl-add-condition-panel {
    width: 280px;

    .panel-tabs {
      display: flex;
      border-bottom: 1px solid #dcdee5;

      .panel-tab-item {
        flex: 1;
        height: 36px;
        font-size: 12px;
        line-height: 36px;
        color: #63656e;
        text-align: center;
        cursor: pointer;
        transition: all .15s;

        &:hover {
          color: #3a84ff;
        }

        &.active {
          color: #3a84ff;
          border-bottom: 2px solid #3a84ff;
        }
      }
    }

    .panel-search {
      padding: 8px;
    }

    .panel-field-list {
      max-height: 240px;
      overflow-y: auto;

      .field-item {
        display: flex;
        height: 32px;
        padding: 0 12px;
        font-size: 12px;
        color: #63656e;
        cursor: pointer;
        align-items: center;
        justify-content: space-between;
        transition: background .15s;

        &:hover {
          background: #e1ecff;
        }

        &.is-selected {
          color: #3a84ff;
          background: #f0f5ff;
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
</style>
