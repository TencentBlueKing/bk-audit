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
  <div class="select-system-card">
    <div class="card-header">
      <div class="card-title">
        <audit-icon
          class="title-icon"
          type="help-fill" />
        <h4>选择系统</h4>
      </div>
      <div
        class="card-close"
        @click="$emit('close')">
        <audit-icon type="close" />
      </div>
    </div>
    <div class="card-body">
      <p class="card-tip">
        先选择要查询的系统<span class="tip-extra">（可多选，仅限有权限的系统）</span>
      </p>
      <div class="field-block">
        <div class="field-label">
          系统选择<span class="required">*</span>
        </div>
        <div class="field-control">
          <bk-select
            v-model="selectedIds"
            class="system-select"
            collapse-tags
            filterable
            :input-search="false"
            :loading="false"
            multiple
            multiple-mode="tag"
            placeholder="请选择"
            :popover-options="selectPopoverOptions"
            :scroll-height="240"
            show-selected-icon
            style="width: 100%; margin-left: 0;">
            <bk-option
              v-for="item in displaySystemList"
              :key="item.id"
              :label="`${item.name}(${item.id})`"
              :value="item.id" />
          </bk-select>
        </div>
      </div>
      <div class="card-actions">
        <bk-button
          class="confirm-btn"
          :disabled="!selectedIds.length"
          theme="primary"
          @click="handleConfirm">
          确认选择
        </bk-button>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { ref, watch } from 'vue';

  import useMessage from '@hooks/use-message';

  import type { SelectedSystem } from '../../types';

  export type { SelectedSystem };

  interface SystemOption {
    id: string;
    name: string;
  }

  interface Props {
    modelValue?: string[];
  }

  const props = withDefaults(defineProps<Props>(), {
    modelValue: () => [],
  });

  const emit = defineEmits<{
    confirm: [systemIds: string[], systems: SelectedSystem[]];
    close: [];
  }>();

  const { messageWarn } = useMessage();
  const selectedIds = ref<string[]>([...(props.modelValue || [])]);

  // 临时模拟 20 条系统数据，便于验证下拉滚动与遮挡
  const displaySystemList: SystemOption[] = Array.from({ length: 20 }, (_, index) => {
    const n = index + 1;
    return {
      id: `mock_system_${String(n).padStart(2, '0')}`,
      name: `模拟系统${n}`,
    };
  });

  // 卡片贴底靠近输入区，下拉默认向下会被挡住：强制向上展开并挂到 body
  const selectPopoverOptions = {
    extCls: 'sec-chat-system-select-popover',
    boundary: 'body',
    placement: 'top-start',
    autoPlacement: true,
    zIndex: 9999,
  } as const;

  watch(() => props.modelValue, (val) => {
    selectedIds.value = [...(val || [])];
  });

  const handleConfirm = () => {
    if (!selectedIds.value.length) {
      messageWarn('请选择系统');
      return;
    }
    const systems = selectedIds.value
      .map((id) => {
        const item = displaySystemList.find(sys => sys.id === id);
        return item
          ? { id: item.id, name: item.name }
          : { id, name: id };
      });
    emit('confirm', [...selectedIds.value], systems);
  };
</script>

<style lang="postcss" scoped>
  .select-system-card {
    width: 900px;
    max-width: 100%;
    /* 避免裁剪下拉面板 */
    overflow: visible;
    font-size: 14px;
    font-weight: 400;
    line-height: 22px;
    color: #63656e;
    letter-spacing: 0;
    text-align: left;
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
      font-weight: 400;
      line-height: 24px;
      color: #313238;
      letter-spacing: 0;
      text-align: left;
      align-items: center;
      gap: 8px;

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
    display: flex;
    padding: 24px;
    background: #fff;
    flex-direction: column;
  }

  .card-tip {
    margin: 0 0 12px;
    font-size: 14px;
    font-weight: 400;
    line-height: 22px;
    color: #63656e;
    letter-spacing: 0;
    text-align: left;

    .tip-extra {
      color: #63656e;
    }
  }

  .field-block {
    display: flex;
    width: 100%;
    margin: 0 0 24px;
    padding: 0;
    overflow: visible;
    flex-direction: column;
  }

  .field-label {
    display: block;
    width: 100%;
    padding: 0;
    font-size: 14px;
    font-weight: 400;
    line-height: 22px;
    color: #63656e;
    letter-spacing: 0;
    text-align: left;
    flex-shrink: 0;
    box-sizing: border-box;

    .required {
      margin-left: 4px;
      color: #ea3636;
    }
  }

  .field-control {
    display: block;
    width: 100%;
    margin: 0;
    padding: 0;
    flex-shrink: 0;
    box-sizing: border-box;
  }

  .system-select {
    display: block;
    width: 100%;
    max-width: 100%;
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }

  .field-control :deep(.bk-select),
  .field-control :deep(.system-select) {
    display: block;
    width: 100%;
    max-width: 100%;
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }

  .field-control :deep(.bk-select-trigger),
  .field-control :deep(.bk-input),
  .field-control :deep(.bk-select-tag) {
    display: flex;
    width: 100%;
    max-width: 100%;
    min-height: 32px;
    margin: 0;
    font-family: inherit;
    font-size: 14px;
    letter-spacing: 0;
    vertical-align: top;
    border: 1px solid #c4c6cc;
    border-radius: 2px;
    background: #fff;
    box-shadow: none;
    box-sizing: border-box;
    align-items: center;
  }

  .field-control :deep(.bk-input:hover),
  .field-control :deep(.bk-select-tag:hover) {
    border-color: #979ba5;
  }

  .field-control :deep(.is-focus > .bk-input),
  .field-control :deep(.is-focus .bk-select-tag),
  .field-control :deep(.bk-select.is-focus .bk-select-tag),
  .field-control :deep(.bk-select.is-focus .bk-input) {
    border-color: #3a84ff;
    box-shadow: none;
  }

  .field-control :deep(.bk-select-tag) {
    padding: 0 28px 0 8px;
  }

  .field-control :deep(.bk-select-tag .bk-select-tag-wrapper) {
    min-height: 30px;
    padding: 0;
  }

  .field-control :deep(.bk-select-tag input) {
    height: 30px;
    margin: 0;
    font-family: inherit;
    font-size: 14px;
    line-height: 30px;
    color: #63656e;
    letter-spacing: 0;
  }

  .field-control :deep(.bk-select-tag .placeholder),
  .field-control :deep(.bk-input--text::placeholder),
  .field-control :deep(input::placeholder) {
    font-family: inherit;
    font-size: 14px;
    color: #c4c6cc;
    letter-spacing: 0;
  }

  .field-control :deep(.bk-select-tag .angle-up),
  .field-control :deep(.bk-select-tag .angle-down),
  .field-control :deep(.bk-input--suffix-icon) {
    color: #979ba5;
  }

  .field-control :deep(.bk-tag) {
    max-width: 220px;
    height: 22px;
    padding: 0 8px;
    margin: 4px 4px 4px 0;
    font-family: inherit;
    font-size: 12px;
    line-height: 22px;
    color: #63656e;
    letter-spacing: 0;
    background: #f0f1f5;
    border: none;
    border-radius: 2px;
  }

  .field-control :deep(.bk-loading),
  .field-control :deep(.bk-loading-wrapper),
  .field-control :deep(.bk-spin) {
    width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
  }

  .card-actions {
    display: flex;
    justify-content: flex-start;

    .confirm-btn {
      min-width: 88px;
      height: 32px;
      padding: 0 16px;
      font-family: inherit;
      font-size: 14px;
      font-weight: 400;
      line-height: 32px;
      letter-spacing: 0;
      border-radius: 2px;
    }
  }
</style>

<style lang="postcss">
  /* 下拉挂到 body，向上展开；提高层级避免被底部输入区遮挡 */
  .sec-chat-system-select-popover {
    z-index: 9999 !important;
  }
</style>
