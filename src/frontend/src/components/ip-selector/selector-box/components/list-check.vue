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
    class="list-check"
    :class="{ disabled }">
    <bk-checkbox
      :model-value="isChecked"
      @change="handleCheckboxChange" />
    <bk-popover
      placement="bottom"
      theme="light"
      trigger="click">
      <audit-icon type="angle-line-down" />
      <template #content>
        <div class="pop-menu">
          <div
            class="item"
            @click="handleChange('page')">
            {{ t('本页全选') }}
          </div>
          <div
            class="item"
            @click="handleChange('all')">
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

  interface Props {
    value?: string,
    disabled: boolean;
  }
  interface Emits {
    (e: 'change', actionType: string): void
  }

  const props = withDefaults(defineProps<Props>(), {
    value: '',
    disabled: true,
  });

  const emits = defineEmits<Emits>();
  const select = ref('');
  const { t } = useI18n();

  const isChecked = computed(() => select.value === 'page' || select.value === 'all');

  watch(() => props.value, (value) => {
    select.value = value;
  });

  const triggerChange = (actionType: string) => {
    emits('change', actionType);
  };

  const handleAllCheckCancle = () => {
    select.value = '';
    triggerChange('allCancel');
  };

  const handlePageChange = (value: boolean | string | number) => {
    if (!value) {
      triggerChange('pageCancel');
    } else {
      triggerChange('page');
    }
  };

  const handleCheckboxChange = (value: boolean | string | number) => {
    if (!value) {
      if (select.value === 'all') {
        handleAllCheckCancle();
      } else {
        handlePageChange(false);
        select.value = '';
      }
      return;
    }
    if (select.value === 'page' || select.value === 'all') {
      return;
    }
    select.value = 'page';
    triggerChange('page');
  };

  const handleChange = (value: string) => {
    if (value === select.value) {
      return;
    }
    select.value = value;
    triggerChange(select.value);
  };
</script>
<style lang="postcss" scoped>
  .list-check {
    position: relative;
    display: inline-flex;
    vertical-align: middle;
    align-items: center;
    gap: var(--bk-theme-space-6);

    &.disabled {
      color: var(--bk-theme-border-default);
      pointer-events: none;
      cursor: not-allowed;
    }
  }

  .pop-menu {
    margin: 0 -var(--bk-theme-space-12);
    font-size: 12px;
    line-height: 32px;
    text-align: center;
    cursor: pointer;
    background: var(--bk-theme-surface-default);

    .item {
      padding: 0 var(--bk-theme-space-12);

      &:hover {
        color: var(--bk-theme-color-brand-2);
        background: var(--bk-theme-surface-subtle);
      }
    }
  }
</style>
