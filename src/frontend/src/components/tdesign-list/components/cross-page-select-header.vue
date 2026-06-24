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
    class="cross-page-select-header"
    :class="{ disabled: disabled || isHeaderLoading }">
    <span class="tdesign-list-select-slot">
      <select-checkbox-loading v-if="isHeaderLoading" />
      <bk-checkbox
        v-else
        :disabled="disabled"
        :model-value="isChecked"
        @change="handleCheckboxChange" />
    </span>
    <bk-popover
      ref="popoverRef"
      :arrow="false"
      :is-show="popoverVisible"
      placement="bottom"
      theme="light"
      trigger="manual"
      @after-hidden="handleAfterHidden">
      <audit-icon
        type="angle-line-down"
        @click.stop="handleTogglePopover"
        @mousedown.stop />
      <template #content>
        <div
          class="pop-menu"
          @click.stop
          @mousedown.stop>
          <div
            class="item"
            @click.stop="handleChange('page')"
            @mousedown.stop>
            {{ t('本页全选') }}
          </div>
          <div
            class="item"
            @click.stop="handleChange('all')"
            @mousedown.stop>
            {{ t('跨页全选') }}
          </div>
        </div>
      </template>
    </bk-popover>
  </div>
</template>
<script setup lang="ts">
  import {
    computed,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import SelectCheckboxLoading from './select-checkbox-loading.vue';

  interface Props {
    value?: string,
    disabled: boolean;
    loading?: boolean;
  }
  interface Emits {
    (e: 'change', actionType: string): void
  }

  const props = withDefaults(defineProps<Props>(), {
    value: '',
    disabled: true,
    loading: false,
  });

  const emits = defineEmits<Emits>();
  const select = ref('');
  const popoverRef = ref<{ hide?:() => void }>();
  const popoverVisible = ref(false);
  const localLoading = ref(false);
  const { t } = useI18n();

  const isChecked = computed(() => (
    !isHeaderLoading.value && (select.value === 'page' || select.value === 'all')
  ));
  const isHeaderLoading = computed(() => props.loading || localLoading.value);

  watch(() => props.value, (value) => {
    select.value = value;
  }, { immediate: true });

  const closePopover = () => {
    popoverVisible.value = false;
    popoverRef.value?.hide?.();
  };

  const handleAfterHidden = () => {
    popoverVisible.value = false;
  };

  const handleTogglePopover = () => {
    if (props.disabled || isHeaderLoading.value) {
      return;
    }
    popoverVisible.value = !popoverVisible.value;
  };

  watch(() => props.loading, (loading) => {
    if (!loading) {
      localLoading.value = false;
    }
    if (loading) {
      closePopover();
    }
  });

  const triggerChange = (actionType: string) => {
    emits('change', actionType);
  };

  const handleAllCheckCancel = () => {
    localLoading.value = true;
    triggerChange('allCancel');
  };

  const handlePageChange = (value: boolean | string | number) => {
    if (!value) {
      localLoading.value = true;
      triggerChange('pageCancel');
    } else {
      localLoading.value = true;
      triggerChange('page');
    }
  };

  const handleCheckboxChange = (value: boolean | string | number) => {
    if (isHeaderLoading.value) {
      return;
    }
    closePopover();
    if (!value) {
      if (select.value === 'all') {
        handleAllCheckCancel();
      } else {
        handlePageChange(false);
      }
      return;
    }
    if (select.value === 'page' || select.value === 'all') {
      return;
    }
    localLoading.value = true;
    triggerChange('page');
  };

  const handleChange = (value: string) => {
    if (isHeaderLoading.value) {
      return;
    }
    closePopover();
    if (value === select.value) {
      return;
    }
    localLoading.value = true;
    triggerChange(value);
  };
</script>
<style lang="postcss" scoped>
  .cross-page-select-header {
    position: relative;
    display: inline-flex;
    vertical-align: middle;
    align-items: center;
    gap: 6px;

    &.disabled {
      color: #dcdee5;
      pointer-events: none;
      cursor: not-allowed;
    }
  }

  .pop-menu {
    margin: 0 -14px;
    font-size: 12px;
    line-height: 32px;
    text-align: center;
    cursor: pointer;
    background: #fff;

    .item {
      padding: 0 14px;

      &:hover {
        color: #3a84ff;
        background: #f5f6fa;
      }
    }
  }
</style>
