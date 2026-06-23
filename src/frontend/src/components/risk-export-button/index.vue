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
  <span
    v-bk-tooltips="tooltip"
    class="risk-export-btn-wrapper"
    :class="{ 'is-export-disabled': disabled && !isExporting }">
    <bk-button
      class="risk-export-btn"
      :class="[buttonClass, { 'is-exporting': isExporting }]"
      :disabled="disabled || isExporting"
      outline
      @click="handleClick">
      <audit-icon
        v-if="isExporting"
        class="rotate-loading risk-export-btn__loading"
        type="loading" />
      {{ t('批量导出') }}
    </bk-button>
  </span>
</template>

<script setup lang="ts">
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';

  import {
    isRiskExportLoading,
    withRiskExportLoading,
  } from '@hooks/use-risk-export-loading';

  interface Props {
    disabled?: boolean;
    tooltip?: Record<string, unknown>;
    exportFn: () => Promise<void>;
    buttonClass?: string;
  }

  const props = withDefaults(defineProps<Props>(), {
    disabled: false,
    tooltip: () => ({ disabled: true, content: '' }),
    buttonClass: '',
  });

  const { t } = useI18n();
  const isExporting = computed(() => isRiskExportLoading.value);

  const handleClick = async () => {
    if (props.disabled || isRiskExportLoading.value) {
      return;
    }
    await withRiskExportLoading(() => props.exportFn());
  };
</script>

<style lang="postcss" scoped>
.risk-export-btn-wrapper {
  display: inline-flex;

  &.is-export-disabled :deep(.risk-export-btn) {
    color: #c4c6cc;
    pointer-events: none;
    cursor: not-allowed;
    background-color: #fff;
    border-color: #dcdee5;

    &:hover,
    &:active {
      color: #c4c6cc;
      background-color: #fff;
      border-color: #dcdee5;
    }
  }
}

:deep(.risk-export-btn) {
  &.is-exporting {
    cursor: wait;
    opacity: 85%;
  }
}

.risk-export-btn__loading {
  margin-right: 4px;
  font-size: 12px;
  color: #3a84ff;
}
</style>
