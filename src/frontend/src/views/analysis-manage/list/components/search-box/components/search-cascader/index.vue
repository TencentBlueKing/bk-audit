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
    ext-cls="add-search-cascader-popover"
    :is-show="isShow"
    placement="bottom"
    style="padding: 0;"
    theme="light"
    trigger="click"
    @after-hidden="handleAfterHidden">
    <span
      class="add-search-icon">
      <audit-icon
        style="margin-right: 5px;"
        type="add" />
      <span>{{ t('添加其他条件') }}</span>
    </span>
    <template #content>
      <div class="add-search-cascader-content">
        <div style="width: 290px; padding: 0 8px;">
          <bk-input
            v-model="searchKeyword"
            behavior="simplicity"
            class="mb8"
            placeholder="请输入关键字">
            <template #prefix>
              <div style="line-height: 30px;">
                <audit-icon
                  type="search1" />
              </div>
            </template>
          </bk-input>
        </div>

        <field-cascader
          v-model="selectedItems"
          :data="localData"
          :is-searching="isSearching"
          :search-keyword="searchKeyword"
          @clear-search="handleClearSearch"
          @select="handleSelect" />
      </div>
    </template>
  </bk-popover>
</template>

<script setup lang="ts">
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import FieldCascader from '../field-cascader/index.vue';
  import type { IFieldConfig } from '../render-field-config/config';

  import useDebouncedRef from '@/hooks/use-debounced-ref';

  interface CascaderItem {
    allow_operators: string[]
    children: CascaderItem[]
    disabled: boolean
    dynamic_content: boolean
    id: string
    isJson: boolean
    level: number
    name: string
  }

  interface Props {
    data: CascaderItem[];
    modelValue?: Record<string, boolean>;
    filedConfig: Record<string, IFieldConfig>
  }

  interface Emits {
    (e: 'update:modelValue', value: Record<string, boolean>): void;
    (e: 'select', item: CascaderItem, isChecked: boolean): void;
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const isShow = ref(false);
  const searchKeyword = useDebouncedRef('');
  const isSearching = ref(false);
  const selectedItems = ref<Record<string, boolean>>({});
  const localData = ref<CascaderItem[]>([]);

  // 弹出层隐藏后的处理
  const handleAfterHidden = (value: { isShow: boolean}) => {
    isShow.value = value.isShow;
    if (!value.isShow) {
      searchKeyword.value = '';
      isSearching.value = false;
    }
  };

  // 处理选择事件
  const handleSelect = (item: CascaderItem, isChecked: boolean) => {
    emits('select', item, isChecked);
  };

  const handleClearSearch = () => {
    searchKeyword.value = '';
    isSearching.value = false;
  };

  // 同步外部值的改动
  watch(() => props.modelValue, (newVal) => {
    selectedItems.value = { ...newVal };
  }, {
    immediate: true,
  });

  // 监听搜索关键词变化
  watch(() => searchKeyword.value, (newVal) => {
    isSearching.value = !!newVal;
  });

  // 设置disabled
  watch(
    () => props.data,
    newVal => localData.value = newVal.map(item => ({
      ...item,
      disabled: Object.keys(props.filedConfig).includes(item.id),
    })),
  );
</script>
<style lang="postcss">
  .add-search-popover {
    padding: 0 !important;
  }

  .add-search-icon {
    color: #3a84ff;
    cursor: pointer;
  }

  .add-search-cascader-content {
    width: auto;
    min-width: 290px;
  }
</style>
