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
  <div class="column-enum-filter">
    <div class="content-list">
      <div class="search-box">
        <bk-input
          v-model="keyword"
          clearable
          :placeholder="t('请输入关键字')" />
      </div>
      <div class="content-items">
        <bk-checkbox-group v-model="checked">
          <div
            v-for="item in visibleOptions"
            :key="String(item.value)"
            class="list-item">
            <bk-checkbox :label="item.value">
              {{ item.label }}
            </bk-checkbox>
          </div>
        </bk-checkbox-group>
      </div>
    </div>
    <div class="content-footer">
      <bk-button
        size="small"
        theme="primary"
        @click="handleConfirm">
        {{ t('确定') }}
      </bk-button>
      <bk-button
        :disabled="!hasAppliedValue && checked.length === 0"
        size="small"
        @click="handleReset">
        {{ t('重置') }}
      </bk-button>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  type FilterValue = string | number | boolean;

  interface FilterOption {
    label: string;
    value: FilterValue;
  }

  interface Props {
    value?: FilterValue[] | FilterValue;
    options?: FilterOption[];
  }

  const props = withDefaults(defineProps<Props>(), {
    value: () => [],
    options: () => [],
  });

  const emit = defineEmits<{
    change: [value: FilterValue[]];
    confirm: [];
  }>();

  const { t } = useI18n();
  const keyword = ref('');
  const checked = ref<FilterValue[]>([]);

  const normalizeValue = (val: Props['value']): FilterValue[] => {
    if (Array.isArray(val)) {
      return [...val];
    }
    if (val === undefined || val === null || val === '') {
      return [];
    }
    return [val];
  };

  watch(() => props.value, (val) => {
    checked.value = normalizeValue(val);
    keyword.value = '';
  }, { immediate: true });

  const visibleOptions = computed(() => {
    const kw = keyword.value.trim().toLowerCase();
    const list = props.options || [];
    if (!kw) return list;
    return list.filter(item => (
      String(item.label).toLowerCase()
        .includes(kw)
      || String(item.value).toLowerCase()
        .includes(kw)
    ));
  });

  const hasAppliedValue = computed(() => normalizeValue(props.value).length > 0);

  const handleConfirm = () => {
    emit('change', [...checked.value]);
    emit('confirm');
  };

  const handleReset = () => {
    checked.value = [];
    emit('change', []);
    emit('confirm');
  };
</script>

<script lang="ts">
  export default {
    name: 'ColumnEnumFilter',
  };
</script>

<style scoped lang="postcss">
.column-enum-filter {
  min-width: 200px;
  max-width: 300px;
  background: #fff;

  .content-list {
    display: block;
    width: 100%;
  }

  .search-box {
    padding: 0 10px 8px;
  }

  .content-items {
    max-height: 200px;
    overflow: auto;

    :deep(.bk-checkbox-group) {
      display: flex;
      flex-direction: column;
      align-items: stretch;
    }
  }

  .list-item {
    display: block;
    width: 100%;
    height: 32px;
    padding: 0 10px;
    font-size: 12px;
    line-height: 32px;
    color: #63656e;
    text-align: left;

    &:hover {
      background: #f0f1f5;
    }

    :deep(.bk-checkbox) {
      display: flex;
      width: 100%;
      margin-right: 0;
      margin-left: 0;
    }

    :deep(.bk-checkbox-label) {
      overflow: hidden;
      max-width: calc(100% - 22px);
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .content-footer {
    display: flex;
    gap: 8px;
    align-items: center;
    padding: 12px;
    border-top: 1px solid #dcdee5;
  }
}
</style>
