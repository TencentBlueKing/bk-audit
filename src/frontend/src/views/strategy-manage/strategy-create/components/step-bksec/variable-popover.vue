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
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
  either express or implied. See the License for the
  specific language governing permissions and limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
-->
<template>
  <div
    class="bksec-var-panel"
    data-testid="bksec-variable-picker">
    <div class="bksec-var-search">
      <audit-icon
        class="bksec-var-search-icon"
        type="search1" />
      <input
        v-model="keyword"
        class="bksec-var-search-input"
        :placeholder="t('搜索变量名称或标识')">
    </div>
    <div
      v-if="groups.length"
      class="bksec-var-tabs"
      role="tablist">
      <button
        v-for="group in groups"
        :key="group.key"
        class="bksec-var-tab"
        :class="{ 'is-active': group.key === activeKey }"
        role="tab"
        type="button"
        @click="activeKey = group.key">
        <span>{{ t(group.label) }}</span>
        <span class="bksec-var-count">{{ filteredCount(group.key) }}</span>
      </button>
    </div>
    <div
      v-if="!activeItems.length"
      class="bksec-var-empty"
      data-testid="bksec-variable-empty">
      {{ t('暂无匹配的变量') }}
    </div>
    <button
      v-for="item in activeItems"
      :key="`${activeKey}-${item.token}`"
      class="bksec-var-row"
      type="button"
      @click="emit('insert', item.insertText)">
      <span class="bksec-var-name">
        <span class="bksec-var-label">{{ item.label }}</span>
        <span class="bksec-var-token">{{ item.insertText }}</span>
      </span>
      <span
        v-if="showSample"
        class="bksec-var-sample">{{ item.sample || '-' }}</span>
      <span class="bksec-var-insert">{{ t('引用') }}</span>
    </button>
  </div>
</template>
<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type { VariableGroup } from './variable-groups';

  interface Props {
    groups: VariableGroup[];
  }
  interface Emits {
    (e: 'insert', value: string): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const keyword = ref('');
  const activeKey = ref<VariableGroup['key']>('risk');

  const matchItem = (item: VariableGroup['items'][number], rule: RegExp) => (
    rule.test(item.label) || rule.test(item.token) || rule.test(item.sample) || rule.test(item.insertText)
  );

  const filteredGroups = computed(() => {
    const text = keyword.value.trim();
    if (!text) return props.groups;
    const rule = new RegExp(text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i');
    return props.groups.map(group => ({
      ...group,
      items: group.items.filter(item => matchItem(item, rule)),
    }));
  });

  const filteredCount = (key: VariableGroup['key']) => (
    filteredGroups.value.find(group => group.key === key)?.items.length || 0
  );
  const activeGroup = computed(() => (
    filteredGroups.value.find(group => group.key === activeKey.value) || filteredGroups.value[0]
  ));
  const activeItems = computed(() => activeGroup.value?.items || []);
  const showSample = computed(() => activeItems.value.some(item => !!item.sample));

  watch(() => props.groups, (groups) => {
    if (!groups.some(group => group.key === activeKey.value)) {
      activeKey.value = groups[0]?.key || 'risk';
    }
  }, { immediate: true });
</script>
<style lang="postcss" scoped>
.bksec-var-panel {
  width: 480px;
  max-height: 360px;
  overflow: auto;
  background: var(--audit-neutral-bg-04);
}

.bksec-var-search {
  display: flex;
  margin: 0 var(--audit-space-8);
  border-bottom: 1px solid var(--audit-neutral-border-01);
  align-items: center;
  gap: var(--audit-space-8);
}

.bksec-var-search-icon {
  font-size: var(--audit-font-size-lg);
  color: var(--audit-neutral-text-03);
}

.bksec-var-search-input {
  width: 100%;
  height: 32px;
  padding: 6px 0;
  font-size: var(--audit-font-size-sm);
  line-height: var(--audit-line-height-sm);
  color: var(--audit-neutral-text-01);
  background: transparent;
  border: 0;
  outline: none;
}

.bksec-var-search-input::placeholder {
  color: var(--audit-neutral-text-04);
}

.bksec-var-tabs {
  display: flex;
  height: 32px;
  padding: var(--audit-space-4);
  margin: var(--audit-space-4) var(--audit-space-8) 0;
  background: var(--audit-neutral-bg-01);
  border-radius: var(--audit-radius-control);
}

.bksec-var-tab {
  display: flex;
  height: 24px;
  min-width: 0;
  padding: 0 var(--audit-space-12);
  font-size: var(--audit-font-size-sm);
  line-height: var(--audit-line-height-sm);
  color: var(--audit-neutral-text-02);
  cursor: pointer;
  background: transparent;
  border: 0;
  border-radius: var(--audit-radius-control);
  flex: 1;
  align-items: center;
  justify-content: center;
  gap: var(--audit-space-4);
}

.bksec-var-tab.is-active {
  color: var(--audit-brand-02);
  background: var(--audit-neutral-bg-04);
  box-shadow: var(--audit-shadow-card-hover);
}

.bksec-var-count {
  display: inline-flex;
  height: 16px;
  padding: 0 6px;
  font-size: var(--audit-font-size-mini);
  line-height: var(--audit-line-height-mini);
  color: var(--audit-neutral-text-02);
  background: var(--audit-neutral-bg-04);
  border-radius: 8px;
  align-items: center;
}

.bksec-var-tab.is-active .bksec-var-count {
  color: var(--audit-brand-01);
  background: var(--audit-brand-06);
}

.bksec-var-empty {
  padding: var(--audit-space-16) 0;
  font-size: var(--audit-font-size-sm);
  line-height: var(--audit-line-height-sm);
  color: var(--audit-neutral-text-03);
  text-align: center;
}

.bksec-var-row {
  display: flex;
  width: 100%;
  padding: 6px var(--audit-space-12);
  cursor: pointer;
  background: var(--audit-neutral-bg-04);
  border: 0;
  align-items: center;
  gap: var(--audit-space-8);
  text-align: left;
}

.bksec-var-row:hover {
  background: var(--audit-neutral-bg-03);
}

.bksec-var-name {
  display: flex;
  min-width: 0;
  flex: 1;
  align-items: center;
  gap: var(--audit-space-8);
}

.bksec-var-label,
.bksec-var-token,
.bksec-var-sample {
  overflow: hidden;
  font-size: var(--audit-font-size-sm);
  line-height: var(--audit-line-height-sm);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bksec-var-label,
.bksec-var-sample {
  color: var(--audit-neutral-text-02);
}

.bksec-var-token {
  color: var(--audit-neutral-text-03);
}

.bksec-var-sample {
  width: 140px;
  flex: none;
}

.bksec-var-insert {
  font-size: var(--audit-font-size-sm);
  line-height: var(--audit-line-height-sm);
  color: var(--audit-brand-02);
  white-space: nowrap;
  visibility: hidden;
  flex: none;
}

.bksec-var-row:hover .bksec-var-insert {
  visibility: visible;
}
</style>
