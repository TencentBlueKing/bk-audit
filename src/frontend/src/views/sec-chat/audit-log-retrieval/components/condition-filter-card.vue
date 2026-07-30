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
  <div class="condition-filter-card">
    <div class="card-header">
      <div class="card-title">
        <audit-icon
          class="title-icon"
          type="search1" />
        <h4>条件筛选</h4>
      </div>
      <div
        class="card-close"
        @click="$emit('close')">
        <audit-icon type="close" />
      </div>
    </div>

    <div class="card-body">
      <p class="card-tip">
        添加条件进行检索
      </p>
      <div class="condition-row">
        <div
          v-for="item in conditions"
          :key="item.id"
          class="condition-tag"
          :class="{ 'is-time': item.type === 'time' }">
          <span class="tag-label">{{ item.field }}：</span>
          <span class="tag-value">{{ item.value }}</span>
          <span
            v-if="item.type === 'time'"
            class="tag-caret" />
          <audit-icon
            v-else-if="item.removable"
            class="tag-close"
            type="close"
            @click="removeCondition(item.id)" />
        </div>

        <bk-popover
          :arrow="false"
          :is-show="addPopoverShow"
          placement="bottom-start"
          theme="light"
          trigger="manual"
          @after-hidden="addPopoverShow = false">
          <button
            class="add-condition-btn"
            type="button"
            @click.stop="addPopoverShow = !addPopoverShow">
            + 添加条件
          </button>
          <template #content>
            <div
              class="add-field-panel"
              @click.stop>
              <div
                v-for="field in addableFields"
                :key="field"
                class="add-field-item"
                @click="handleAddField(field)">
                {{ field }}
              </div>
              <div
                v-if="!addableFields.length"
                class="add-field-empty">
                暂无可添加字段
              </div>
            </div>
          </template>
        </bk-popover>

        <button
          v-if="conditions.length"
          class="clear-btn"
          type="button"
          @click="clearConditions">
          <audit-icon
            class="clear-icon"
            type="delete" />
          <span>清空</span>
        </button>
      </div>

      <div class="card-actions">
        <bk-button
          class="search-btn"
          :disabled="!conditions.length"
          theme="primary"
          @click="handleSearch">
          开始检索
        </bk-button>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { computed, ref, watch } from 'vue';

  import type { SelectedSystem } from '../../types';

  export interface SeedField {
    name: string;
    sample?: string;
  }

  interface ConditionItem {
    id: string;
    field: string;
    value: string;
    type: 'time' | 'normal';
    removable: boolean;
  }

  const props = withDefaults(defineProps<{
    seedField?: SeedField | null;
    systems?: SelectedSystem[];
    fieldOptions?: string[];
  }>(), {
    seedField: null,
    systems: () => [],
    fieldOptions: () => [],
  });

  const emit = defineEmits<{
    close: [];
    search: [summary: string];
  }>();

  const conditions = ref<ConditionItem[]>([]);
  const addPopoverShow = ref(false);
  let conditionSeq = 0;

  const defaultFieldOptions = [
    '操作起始时间',
    '操作人',
    '操作人账号类型',
    '来源系统',
    '操作结果',
    '操作途径',
    '来源IP',
    '事件ID',
    '请求ID',
  ];

  const allFieldOptions = computed(() => {
    const list = props.fieldOptions.length ? props.fieldOptions : defaultFieldOptions;
    return Array.from(new Set(list));
  });

  const addableFields = computed(() => {
    const used = new Set(conditions.value.map(item => item.field));
    return allFieldOptions.value.filter(name => !used.has(name));
  });

  const createId = () => {
    conditionSeq += 1;
    return `cond-${Date.now()}-${conditionSeq}`;
  };

  const buildDefaultValue = (field: string, sample?: string) => {
    if (field === '操作起始时间') return '近 6 月';
    if (field === '来源系统') {
      return sample
        || props.systems[0]?.name
        || 'TOD 账单系统';
    }
    return sample || '替换为实际值';
  };

  const initConditions = () => {
    const next: ConditionItem[] = [{
      id: createId(),
      field: '操作起始时间',
      value: '近 6 月',
      type: 'time',
      removable: false,
    }];

    const seed = props.seedField;
    if (seed?.name && seed.name !== '操作起始时间') {
      next.push({
        id: createId(),
        field: seed.name,
        value: buildDefaultValue(seed.name, seed.sample),
        type: 'normal',
        removable: true,
      });
    } else if (props.systems.length) {
      next.push({
        id: createId(),
        field: '来源系统',
        value: props.systems.map(item => item.name).slice(0, 1)
          .join('、') || 'TOD 账单系统',
        type: 'normal',
        removable: true,
      });
    }

    conditions.value = next;
    addPopoverShow.value = false;
  };

  watch(() => props.seedField, () => {
    initConditions();
  }, { immediate: true, deep: true });

  const removeCondition = (id: string) => {
    conditions.value = conditions.value.filter(item => item.id !== id);
  };

  const clearConditions = () => {
    conditions.value = [];
  };

  const handleAddField = (field: string) => {
    conditions.value.push({
      id: createId(),
      field,
      value: buildDefaultValue(field),
      type: field === '操作起始时间' ? 'time' : 'normal',
      removable: field !== '操作起始时间',
    });
    addPopoverShow.value = false;
  };

  const handleSearch = () => {
    if (!conditions.value.length) return;
    const summary = conditions.value
      .map(item => `${item.field}为${item.value}`)
      .join('，');
    emit('search', `条件筛选：${summary}`);
  };
</script>

<style lang="postcss" scoped>
  .condition-filter-card {
    width: 100%;
    max-width: 100%;
    overflow: visible;
    font-size: 14px;
    font-weight: 400;
    line-height: 22px;
    color: #63656e;
    letter-spacing: 0;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 8px;
    box-shadow: 0 0 10px rgb(0 0 0 / 10%);
    box-sizing: border-box;
  }

  .card-header {
    display: flex;
    height: 52px;
    padding: 0 24px;
    background: #f0f1f5;
    border-bottom: 1px solid #dcdee5;
    border-radius: 8px 8px 0 0;
    align-items: center;
    justify-content: space-between;
    box-sizing: border-box;

    .card-title {
      display: flex;
      font-size: 16px;
      font-weight: 700;
      line-height: 24px;
      color: #313238;
      letter-spacing: 0;
      align-items: center;
      gap: 8px;

      h4 {
        margin: 0;
        font-size: inherit;
        font-weight: inherit;
        line-height: inherit;
        color: inherit;
      }

      .title-icon {
        font-size: 18px;
        color: #979ba5;
        flex-shrink: 0;
      }
    }

    .card-close {
      display: flex;
      width: 32px;
      height: 32px;
      margin-right: -8px;
      font-size: 18px;
      color: #979ba5;
      cursor: pointer;
      border-radius: 2px;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;

      &:hover {
        color: #63656e;
        background: #eaebf0;
      }
    }
  }

  .card-body {
    padding: 24px;
    background: #fff;
  }

  .card-tip {
    margin: 0 0 16px;
    font-size: 14px;
    line-height: 22px;
    color: #979ba5;
  }

  .condition-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  .condition-tag {
    display: inline-flex;
    max-width: 100%;
    height: 32px;
    padding: 0 8px 0 12px;
    font-size: 12px;
    line-height: 30px;
    color: #63656e;
    background: #f0f1f5;
    border: 1px solid #dcdee5;
    border-radius: 2px;
    align-items: center;
    gap: 4px;
    box-sizing: border-box;

    .tag-label {
      flex-shrink: 0;
      color: #63656e;
    }

    .tag-value {
      font-weight: 700;
      color: #313238;
    }

    .tag-caret {
      display: inline-block;
      width: 0;
      height: 0;
      margin-left: 4px;
      border-style: solid;
      border-width: 5px 4px 0;
      border-color: #979ba5 transparent transparent;
      flex-shrink: 0;
    }

    .tag-close {
      margin-left: 2px;
      font-size: 14px;
      color: #979ba5;
      cursor: pointer;
      flex-shrink: 0;

      &:hover {
        color: #63656e;
      }
    }
  }

  .add-condition-btn {
    height: 32px;
    padding: 0 12px;
    font-size: 12px;
    line-height: 30px;
    color: #3a84ff;
    cursor: pointer;
    background: #fff;
    border: 1px dashed #3a84ff;
    border-radius: 2px;
    box-sizing: border-box;

    &:hover {
      background: #f0f5ff;
    }
  }

  .clear-btn {
    display: inline-flex;
    height: 32px;
    padding: 0 4px;
    font-size: 12px;
    line-height: 32px;
    color: #979ba5;
    cursor: pointer;
    background: none;
    border: none;
    align-items: center;
    gap: 4px;

    &:hover {
      color: #63656e;
    }

    .clear-icon {
      font-size: 14px;
    }
  }

  .card-actions {
    display: flex;
    margin-top: 24px;
    justify-content: flex-start;

    .search-btn {
      min-width: 88px;
      height: 32px;
      padding: 0 16px;
      font-size: 14px;
      font-weight: 400;
      line-height: 32px;
      border-radius: 2px;
    }
  }

  .add-field-panel {
    min-width: 160px;
    max-height: 240px;
    padding: 4px 0;
    overflow: auto;
  }

  .add-field-item {
    padding: 8px 12px;
    font-size: 12px;
    line-height: 20px;
    color: #63656e;
    cursor: pointer;

    &:hover {
      color: #3a84ff;
      background: #f0f5ff;
    }
  }

  .add-field-empty {
    padding: 12px;
    font-size: 12px;
    color: #c4c6cc;
    text-align: center;
  }
</style>
