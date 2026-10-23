<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and limitations
  under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
-->
<template>
  <div class="package-name-filter">
    <bk-input
      v-model="keyword"
      class="package-name-filter-search"
      clearable
      :placeholder="t('请输入关键字')" />
    <div
      v-if="visibleList.length"
      class="package-name-filter-list">
      <bk-checkbox-group
        :model-value="visibleChecked"
        @change="handleChange">
        <div
          v-for="item in visibleList"
          :key="item.value"
          class="package-name-filter-item">
          <bk-checkbox :label="item.value">
            {{ item.label }}
          </bk-checkbox>
        </div>
      </bk-checkbox-group>
    </div>
    <div
      v-else
      class="package-name-filter-empty">
      {{ t('搜索为空') }}
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import { packageFilterOptions, type PackageFilterOption } from './package-filter-state';

  interface Props {
    value?: string[] | string;
    list?: PackageFilterOption[];
  }

  const props = withDefaults(defineProps<Props>(), {
    value: () => [],
    list: () => [],
  });

  const emit = defineEmits<{
    change: [value: string[]];
  }>();

  const { t } = useI18n();
  const keyword = ref('');
  const sourceList = computed(() => (props.list.length ? props.list : packageFilterOptions.value));

  const normalize = (value: Props['value']) => {
    if (Array.isArray(value)) return value.map(item => String(item));
    if (value === undefined || value === null || value === '') return [];
    return [String(value)];
  };

  const checked = ref<string[]>([]);

  watch(() => props.value, (value) => {
    checked.value = normalize(value);
  }, { immediate: true });

  const matched = (item: PackageFilterOption) => {
    const text = keyword.value.trim().toLowerCase();
    if (!text) return true;
    return item.label.toLowerCase().includes(text) || item.value.toLowerCase().includes(text);
  };

  const visibleList = computed(() => sourceList.value.filter(matched));
  const visibleChecked = computed(() => (
    checked.value.filter(id => visibleList.value.some(item => item.value === id))
  ));

  const handleChange = (value: Array<string | number>) => {
    const visibleIds = new Set(visibleList.value.map(item => item.value));
    const hiddenChecked = checked.value.filter(id => !visibleIds.has(id));
    checked.value = [...new Set([...hiddenChecked, ...value.map(item => String(item))])];
    emit('change', checked.value);
  };
</script>
<style lang="postcss" scoped>
.package-name-filter {
  width: 240px;
}

.package-name-filter-search {
  margin-bottom: 8px;
}

.package-name-filter-list {
  max-height: 240px;
  overflow: auto;

  :deep(.bk-checkbox-group) {
    display: flex;
    flex-direction: column;
    align-items: stretch;
  }
}

.package-name-filter-item {
  display: block;
  width: 100%;
  height: 32px;
  padding: 0 4px;
  line-height: 32px;

  :deep(.bk-checkbox) {
    display: flex;
    width: 100%;
    margin: 0;
  }

  :deep(.bk-checkbox-label) {
    overflow: hidden;
    max-width: calc(100% - 22px);
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.package-name-filter-empty {
  padding: 8px 0 4px;
  font-size: 12px;
  line-height: 20px;
  color: var(--audit-neutral-text-03);
  text-align: center;
}
</style>
