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
    class="all-risk-export-btn-wrapper"
    :class="{ 'is-export-disabled': disabled && !isLoading }">
    <bk-button
      class="all-risk-export-btn"
      :class="{ 'is-exporting': isLoading }"
      :disabled="disabled || isLoading"
      outline
      @click="handleClick">
      <audit-icon
        v-if="isLoading"
        class="rotate-loading all-risk-export-btn__loading"
        type="loading" />
      {{ t('批量导出') }}
    </bk-button>
  </span>
</template>

<script setup lang="ts">
  import { nextTick, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Props {
    disabled?: boolean;
    tooltip?: Record<string, unknown>;
    exportFn: () => Promise<void>;
  }

  const props = withDefaults(defineProps<Props>(), {
    disabled: false,
    tooltip: () => ({ disabled: true, content: '' }),
  });

  const { t } = useI18n();
  const isLoading = ref(false);

  const handleClick = async () => {
    if (props.disabled || isLoading.value) {
      return;
    }
    isLoading.value = true;
    await nextTick();
    try {
      await props.exportFn();
    } finally {
      isLoading.value = false;
    }
  };
</script>

<style lang="postcss" scoped>
.all-risk-export-btn-wrapper {
  display: inline-flex;

  &.is-export-disabled :deep(.all-risk-export-btn) {
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

.all-risk-export-btn {
  &.is-exporting {
    cursor: wait;
    opacity: 85%;
  }
}

.all-risk-export-btn__loading {
  margin-right: 4px;
  font-size: 12px;
  color: #3a84ff;
}
</style>
