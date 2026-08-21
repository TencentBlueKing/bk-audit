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
    <div class="card-body">
      <p class="card-tip">
        <img
          alt=""
          class="tip-icon"
          :src="wenhaoIcon">
        <span>
          先选择要查询的系统<span class="tip-extra">（可多选，仅限有权限的系统）</span>
        </span>
      </p>
      <div class="field-block">
        <div class="field-label">
          系统选择
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
              :disabled="isOptionDisabled(item.id)"
              :label="`${item.name}(${item.id})`"
              :value="item.id" />
          </bk-select>
        </div>
        <div
          v-if="selectedIds.length"
          class="field-count">
          已选系统 {{ selectedIds.length }} / {{ MAX_SYSTEM_COUNT }}
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

  import wenhaoIcon from '@images/wenhao.svg';

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

  const MAX_SYSTEM_COUNT = 10;

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

  const selectPopoverOptions = {
    extCls: 'sec-chat-system-select-popover',
    boundary: 'body',
    placement: 'bottom-start',
    autoPlacement: true,
    zIndex: 9999,
  } as const;

  const isOptionDisabled = (id: string) => (
    selectedIds.value.length >= MAX_SYSTEM_COUNT && !selectedIds.value.includes(id)
  );

  watch(() => props.modelValue, (val) => {
    selectedIds.value = [...(val || [])].slice(0, MAX_SYSTEM_COUNT);
  });

  watch(selectedIds, (val) => {
    if (val.length <= MAX_SYSTEM_COUNT) return;
    selectedIds.value = val.slice(0, MAX_SYSTEM_COUNT);
    messageWarn(`最多选择 ${MAX_SYSTEM_COUNT} 个系统`);
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
    overflow: visible;
    padding: 20px 24px 24px;
    font-size: 14px;
    font-weight: 400;
    line-height: 22px;
    color: #63656e;
    letter-spacing: 0;
    text-align: left;
    background: #fff;
    border-radius: 16px;
    box-shadow: 0 12px 32px 0 rgb(0 0 0 / 4%);
    box-sizing: border-box;
  }

  .card-body {
    display: flex;
    padding: 0;
    background: transparent;
    flex-direction: column;
  }

  .card-tip {
    display: flex;
    margin: 0 0 16px;
    font-size: 14px;
    font-weight: 400;
    line-height: 22px;
    color: #63656e;
    letter-spacing: 0;
    text-align: left;
    align-items: flex-start;
    gap: 8px;

    .tip-icon {
      display: block;
      width: 18px;
      height: 18px;
      margin-top: 2px;
      flex-shrink: 0;
    }

    .tip-extra {
      color: #9ea1aa;
    }
  }

  .field-block {
    display: flex;
    width: 100%;
    margin: 0 0 16px;
    padding: 0;
    overflow: visible;
    flex-direction: column;
  }

  .field-label {
    display: block;
    width: 100%;
    margin-bottom: 8px;
    padding: 0;
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    color: #313238;
    letter-spacing: 0;
    text-align: left;
    flex-shrink: 0;
    box-sizing: border-box;
  }

  .field-control {
    display: block;
    width: 100%;
    margin: 0;
    padding: 0;
    flex-shrink: 0;
    box-sizing: border-box;
  }

  .field-count {
    margin-top: 8px;
    font-size: 12px;
    line-height: 20px;
    color: #979ba5;
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
  .sec-chat-system-select-popover {
    z-index: 9999 !important;
  }
</style>
