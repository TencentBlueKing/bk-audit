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
  <div class="report-jump-scope-menu-outer">
    <!-- 搜索：对齐工具管理可见范围选择器 -->
    <div
      class="jump-scope-search"
      @mousedown.stop>
      <span class="search-prefix-wrap">
        <audit-icon
          class="search-prefix"
          type="search1" />
      </span>
      <bk-input
        v-model="searchKeyword"
        behavior="simplicity"
        clearable
        :placeholder="t('搜索')" />
    </div>

    <bk-loading
      class="jump-scope-loading"
      :class="{ 'is-loading': loading }"
      :loading="loading"
      size="small">
      <div class="report-jump-scope-menu">
        <div
          v-if="filteredScenes.length > 0"
          class="jump-scope-section">
          <div class="jump-scope-section-title">
            {{ t('所属场景') }}
          </div>
          <div
            v-for="scene in filteredScenes"
            :key="`scene-${scene.id}`"
            class="jump-scope-item"
            @click.stop="emit('select', scene)">
            <img
              alt=""
              class="jump-scope-item-icon scene-icon"
              :src="sceneIconUrl">
            <span class="jump-scope-item-content">
              <span class="jump-scope-item-name">
                <tooltips :data="scene.name" />
              </span>
              <span
                v-if="typeof scene.count === 'number'"
                class="jump-scope-item-count">
                <audit-icon
                  class="jump-scope-count-icon"
                  type="gaojingshijian" />
                {{ scene.count }}
              </span>
              <audit-icon
                v-else
                class="jump-scope-link-icon"
                type="jump-link" />
            </span>
          </div>
        </div>

        <div
          v-if="filteredSystems.length > 0"
          class="jump-scope-section">
          <div class="jump-scope-section-title">
            {{ t('所属系统') }}
          </div>
          <div
            v-for="system in filteredSystems"
            :key="`system-${system.id}`"
            class="jump-scope-item"
            @click.stop="emit('select', system)">
            <img
              alt=""
              class="jump-scope-item-icon system-icon"
              :src="systemIconUrl">
            <span class="jump-scope-item-content">
              <span class="jump-scope-item-name">
                <tooltips :data="system.name" />
              </span>
              <audit-icon
                class="jump-scope-link-icon"
                type="jump-link" />
            </span>
          </div>
        </div>

        <div
          v-if="!loading && isEmpty"
          class="jump-scope-empty">
          {{ t('无数据') }}
        </div>
      </div>
    </bk-loading>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import Tooltips from '@components/show-tooltips-text/index.vue';

  import sceneIconUrl from '@images/scene.svg';
  import systemIconUrl from '@images/system.svg';

  export interface JumpScopeItem {
    type: 'scene' | 'system';
    id: number | string;
    name: string;
    count?: number;
  }

  const props = withDefaults(defineProps<{
    scenes?: JumpScopeItem[];
    systems?: JumpScopeItem[];
    loading?: boolean;
  }>(), {
    scenes: () => [],
    systems: () => [],
    loading: false,
  });

  const emit = defineEmits<{(e: 'select', scope: JumpScopeItem): void}>();

  const { t } = useI18n();
  const searchKeyword = ref('');

  const normalizedKeyword = computed(() => searchKeyword.value.trim().toLowerCase());

  const filterItems = (items: JumpScopeItem[]) => {
    const keyword = normalizedKeyword.value;
    if (!keyword) return items;
    // 仅按名称过滤
    return items.filter(item => item.name.toLowerCase().includes(keyword));
  };

  const filteredScenes = computed(() => filterItems(props.scenes));
  const filteredSystems = computed(() => filterItems(props.systems));
  const isEmpty = computed(() => filteredScenes.value.length === 0 && filteredSystems.value.length === 0);
</script>

<style lang="postcss" scoped>
  .report-jump-scope-menu-outer {
    width: 240px;
    max-height: 320px;
    overflow: hidden;
  }

  .jump-scope-search {
    display: flex;
    align-items: center;
    padding: var(--bk-theme-space-4) 0 0;
    margin: 0 var(--bk-theme-space-12);
    background: var(--bk-theme-surface-default);
    border-bottom: 1px solid var(--bk-theme-border-default);

    :deep(.bk-input) {
      flex: 1;
      background: var(--bk-theme-surface-default) !important;
      border: none !important;
      box-shadow: none !important;
    }

    :deep(.bk-input--text),
    :deep(.bk-input--default),
    :deep(input) {
      background: var(--bk-theme-surface-default) !important;
      background-color: var(--bk-theme-surface-default) !important;
    }
  }

  .search-prefix-wrap {
    display: inline-flex;
    flex-shrink: 0;
    align-items: center;
    justify-content: center;
    margin-right: var(--bk-theme-space-4);

    .search-prefix {
      font-size: 18px;
      line-height: 1;
      color: var(--bk-theme-text-weak);
    }
  }

  .jump-scope-loading.is-loading {
    min-height: 120px;

    :deep(.bk-loading-wrapper) {
      min-height: 120px;
    }
  }

  .report-jump-scope-menu {
    width: 240px;
    max-height: 280px;
    padding: var(--bk-theme-space-4) 0;
    overflow: hidden auto;
    box-sizing: border-box;
    scrollbar-width: thin;
    scrollbar-color: var(--bk-theme-border-strong) transparent;
  }

  .report-jump-scope-menu::-webkit-scrollbar {
    width: 4px;
  }

  .report-jump-scope-menu::-webkit-scrollbar-track {
    background: transparent;
  }

  .report-jump-scope-menu::-webkit-scrollbar-thumb {
    background-color: var(--bk-theme-border-strong);
    border-radius: var(--bk-theme-tag-radius);
  }

  .jump-scope-section-title {
    padding: var(--bk-theme-space-8) var(--bk-theme-space-12) var(--bk-theme-space-4);
    font-size: 12px;
    line-height: 20px;
    color: var(--bk-theme-text-weak);
  }

  .jump-scope-item {
    display: flex;
    align-items: center;
    gap: var(--bk-theme-space-8);
    padding: var(--bk-theme-space-8) var(--bk-theme-space-12);
    cursor: pointer;

    &:hover {
      background: var(--bk-theme-surface-subtle);

      .jump-scope-link-icon {
        visibility: visible;
      }
    }
  }

  .jump-scope-item-icon {
    flex-shrink: 0;
    width: 16px;
    height: 16px;
  }

  .jump-scope-item-name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    font-size: 12px;
    line-height: 20px;
    color: var(--bk-theme-text-strong);
    text-overflow: ellipsis;
    white-space: nowrap;

    :deep(.show-tooltips-text) {
      display: block;
    }
  }

  .jump-scope-item-content {
    display: flex;
    flex: 1;
    min-width: 0;
    align-items: center;
    justify-content: space-between;
  }

  .jump-scope-item-count {
    display: inline-flex;
    flex-shrink: 0;
    align-items: center;
    gap: var(--bk-theme-space-4);
    height: 20px;
    padding: 0 var(--bk-theme-space-8);
    margin-left: var(--bk-theme-space-8);
    font-size: 12px;
    line-height: 20px;
    color: var(--bk-theme-text-default);
    background: var(--bk-theme-surface-muted);
    border-radius: var(--bk-theme-message-radius);
  }

  .jump-scope-count-icon {
    font-size: 14px;
    color: var(--bk-theme-text-weak);
  }

  .jump-scope-link-icon {
    flex-shrink: 0;
    margin-left: var(--bk-theme-space-8);
    font-size: 14px;
    color: var(--bk-theme-color-brand-2);
    visibility: hidden;
  }

  .jump-scope-empty {
    padding: var(--bk-theme-space-24) var(--bk-theme-space-12);
    font-size: 12px;
    line-height: 20px;
    color: var(--bk-theme-border-strong);
    text-align: center;
  }
</style>
