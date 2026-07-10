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
    ref="dropdownRef"
    class="system-access-dropdown">
    <bk-button
      theme="primary"
      @click.stop="handleToggleDropdown">
      <audit-icon
        class="trigger-icon"
        type="add" />
      {{ t('接入新系统') }}
      <audit-icon
        class="trigger-arrow"
        :class="{ 'is-open': isDropdownVisible }"
        type="angle-line-down" />
    </bk-button>

    <transition name="fade">
      <div
        v-if="isDropdownVisible"
        class="access-dropdown-panel"
        @click.stop>
        <div
          class="access-dropdown-item"
          @click="handleAccessNewSystem">
          <img
            alt=""
            class="access-item-icon"
            :src="newSystemIcon">
          <div class="access-item-content">
            <div class="access-item-title">
              {{ t('接入新系统') }}
            </div>
            <div class="access-item-desc">
              {{ t('适用于新系统首次接入蓝鲸安全体系') }}
            </div>
          </div>
        </div>

        <div
          class="access-dropdown-item access-dropdown-item--existing"
          @mouseenter="handleExistingMouseenter"
          @mouseleave="handleExistingMouseleave">
          <img
            alt=""
            class="access-item-icon"
            :src="existingSystemIcon">
          <div class="access-item-content">
            <div class="access-item-title">
              {{ t('接入已有系统') }}
              <span class="access-item-badge">{{ pendingCount }}</span>
            </div>
            <div class="access-item-desc">
              {{ t('适用于已在蓝鲸权限中心注册过但尚未同步注册到审计中心的系统') }}
            </div>
          </div>
          <audit-icon
            class="access-item-arrow"
            type="angle-line-down" />

          <transition name="fade">
            <div
              v-if="isSubmenuVisible"
              class="access-submenu"
              @mouseenter="handleSubmenuMouseenter"
              @mouseleave="handleSubmenuMouseleave">
              <bk-input
                v-model="searchKeyword"
                behavior="simplicity"
                :placeholder="t('搜索')"
                @input="handleSearch">
                <template #prefix>
                  <audit-icon
                    class="search-icon"
                    type="search1" />
                </template>
              </bk-input>
              <bk-loading :loading="isSystemListLoading">
                <div
                  v-if="filteredSystemList.length"
                  class="access-submenu-list">
                  <div
                    v-for="item in filteredSystemList"
                    :key="item.id"
                    class="access-submenu-item"
                    :class="{ 'is-active': activeItemId === item.id }"
                    @click="handleSelectExistingSystem(item)">
                    <span
                      v-bk-tooltips="{
                        content: `${item.name}(${item.id})`,
                        disabled: item.name.length <= 20,
                        placement: 'top',
                      }"
                      class="access-submenu-text">
                      <span class="access-submenu-name">{{ item.name }}</span>
                      <span class="access-submenu-id">({{ item.id }})</span>
                    </span>
                  </div>
                </div>
                <div
                  v-else-if="!isSystemListLoading"
                  class="access-submenu-empty">
                  {{ t('搜索结果为空') }}
                </div>
              </bk-loading>
            </div>
          </transition>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
  import {
    computed,
    onBeforeUnmount,
    onMounted,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import MetaManageService from '@service/meta-manage';

  import useRequest from '@hooks/use-request';

  import existingSystemIcon from '@images/jieru.svg';
  import newSystemIcon from '@images/new-jieru.svg';

  interface SystemItem {
    id: string;
    name: string;
    source_type: string;
    audit_status: string;
    permission: {
      edit_system: boolean;
      view_system: boolean;
    };
  }

  const { t } = useI18n();
  const router = useRouter();

  const dropdownRef = ref<HTMLElement>();
  const isDropdownVisible = ref(false);
  const isSubmenuVisible = ref(false);
  const searchKeyword = ref('');
  const activeItemId = ref('');
  const originSystemList = ref<SystemItem[]>([]);
  const filteredSystemList = ref<SystemItem[]>([]);
  const pendingCount = computed(() => (
    originSystemList.value.filter(item => item.audit_status === 'pending').length
  ));

  let submenuCloseTimer: number | undefined;

  const normalizeSystemList = (data: unknown) => {
    if (Array.isArray(data)) {
      return data as SystemItem[];
    }
    if (data && typeof data === 'object' && Array.isArray((data as { results?: SystemItem[] }).results)) {
      return (data as { results: SystemItem[] }).results;
    }
    return [];
  };

  const getDisplayList = (list: SystemItem[]) => {
    let result = list.filter(item => (
      item.permission?.edit_system && item.permission?.view_system
    ));
    if (!result.length && list.length) {
      result = list.filter(item => item.permission?.edit_system);
    }
    if (!result.length && list.length) {
      result = list;
    }
    return result;
  };

  const applySystemList = (data: unknown) => {
    const list = normalizeSystemList(data);
    originSystemList.value = list;
    filteredSystemList.value = getDisplayList(list);
  };

  const {
    loading: isSystemListLoading,
    run: fetchSystemWithAction,
  } = useRequest(MetaManageService.fetchSystemWithAction, {
    defaultValue: [],
    manual: true,
    onSuccess: (data) => {
      applySystemList(data);
    },
  });

  const PENDING_SYSTEM_QUERY = {
    sort_keys: 'audit_status,name',
    with_favorite: false,
    with_system_status: false,
    source_type__in: 'iam_v3,iam_v4',
    action_ids: 'edit_system,view_system',
    audit_status__in: 'pending',
  } as const;

  const loadPendingSystems = () => {
    fetchSystemWithAction({ ...PENDING_SYSTEM_QUERY });
  };

  const handleToggleDropdown = () => {
    const nextVisible = !isDropdownVisible.value;
    isDropdownVisible.value = nextVisible;
    if (nextVisible) {
      loadPendingSystems();
    } else {
      isSubmenuVisible.value = false;
      searchKeyword.value = '';
      applySystemList([...originSystemList.value]);
    }
  };

  const handleAccessNewSystem = () => {
    isDropdownVisible.value = false;
    router.push({
      name: 'systemAccessSteps',
      query: {
        step: '1',
        showModelType: 'false',
        isNewSystem: 'true',
        fromList: 'true',
      },
    });
  };

  const handleSelectExistingSystem = (item: SystemItem) => {
    if (item.audit_status !== 'pending') {
      return;
    }
    activeItemId.value = item.id;
    isDropdownVisible.value = false;
    isSubmenuVisible.value = false;
    router.push({
      name: 'systemAccessSteps',
      query: {
        step: '1',
        showModelType: 'false',
        isNewSystem: 'false',
        systemId: item.id,
        fromList: 'true',
      },
    });
  };

  const handleSearch = () => {
    const keyword = searchKeyword.value.trim().toLowerCase();
    const baseList = getDisplayList(originSystemList.value);
    if (!keyword) {
      filteredSystemList.value = baseList;
      return;
    }
    filteredSystemList.value = baseList.filter(item => (
      item.name.toLowerCase().includes(keyword)
      || item.id.toLowerCase().includes(keyword)
    ));
  };

  const clearSubmenuCloseTimer = () => {
    if (submenuCloseTimer) {
      clearTimeout(submenuCloseTimer);
      submenuCloseTimer = undefined;
    }
  };

  const handleExistingMouseenter = () => {
    clearSubmenuCloseTimer();
    isSubmenuVisible.value = true;
    loadPendingSystems();
  };

  const handleExistingMouseleave = () => {
    clearSubmenuCloseTimer();
    submenuCloseTimer = window.setTimeout(() => {
      isSubmenuVisible.value = false;
    }, 120);
  };

  const handleSubmenuMouseenter = () => {
    clearSubmenuCloseTimer();
    isSubmenuVisible.value = true;
  };

  const handleSubmenuMouseleave = () => {
    clearSubmenuCloseTimer();
    submenuCloseTimer = window.setTimeout(() => {
      isSubmenuVisible.value = false;
    }, 120);
  };

  const handleDocumentClick = (event: MouseEvent) => {
    if (!dropdownRef.value?.contains(event.target as Node)) {
      isDropdownVisible.value = false;
      isSubmenuVisible.value = false;
    }
  };

  onMounted(() => {
    document.addEventListener('click', handleDocumentClick);
    loadPendingSystems();
  });

  onBeforeUnmount(() => {
    document.removeEventListener('click', handleDocumentClick);
    clearSubmenuCloseTimer();
  });
</script>

<style scoped lang="postcss">
.system-access-dropdown {
  position: relative;
  display: inline-flex;
}

.trigger-icon {
  margin-right: 8px;
  font-size: 14px;
}

.trigger-arrow {
  margin-left: 4px;
  font-size: 12px;
  transition: transform .2s;

  &.is-open {
    transform: rotate(180deg);
  }
}

.access-dropdown-panel {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  z-index: 2000;
  width: 520px;
  padding: 8px 0;
  background: #fff;
  border: 1px solid #dcdee5;
  border-radius: 2px;
  box-shadow: 0 2px 6px 0 rgb(0 0 0 / 10%);
}

.access-dropdown-item {
  position: relative;
  display: flex;
  padding: 12px 16px;
  cursor: pointer;
  align-items: flex-start;
  gap: 12px;

  &:hover {
    background: #f5f7fa;
  }
}

.access-item-icon {
  width: 32px;
  height: 32px;
  margin-top: 2px;
  flex-shrink: 0;
  object-fit: contain;
}

.access-item-content {
  min-width: 0;
  flex: 1;
}

.access-item-title {
  display: flex;
  margin-bottom: 4px;
  font-size: 14px;
  font-weight: 700;
  line-height: 22px;
  color: #313238;
  align-items: center;
  gap: 8px;
}

.access-item-badge {
  display: inline-flex;
  height: 18px;
  padding: 0 8px;
  font-size: 12px;
  font-weight: 500;
  line-height: 1;
  color: #3a84ff;
  background: #e1ecff;
  border-radius: 9px;
  align-items: center;
}

.access-item-desc {
  overflow: hidden;
  font-size: 12px;
  line-height: 20px;
  color: #979ba5;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.access-item-arrow {
  font-size: 12px;
  color: #c4c6cc;
  flex-shrink: 0;
  align-self: center;
  transform: rotate(-90deg);
}

.access-dropdown-item--existing {
  padding-right: 12px;
  align-items: center;

  .access-item-icon {
    margin-top: 0;
  }
}

.access-submenu {
  position: absolute;
  top: 0;
  left: calc(100% + 4px);
  z-index: 2001;
  width: 320px;
  padding: 12px;
  background: #fff;
  border: 1px solid #dcdee5;
  border-radius: 2px;
  box-shadow: 0 2px 6px 0 rgb(0 0 0 / 10%);
}

.search-icon {
  margin-top: 8px;
}

.access-submenu-list {
  max-height: 280px;
  margin-top: 8px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #c4c6cc transparent;

  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: #c4c6cc;
    border-radius: 2px;
  }

  &::-webkit-scrollbar-thumb:hover {
    background: #979ba5;
  }
}

.access-submenu-item {
  padding: 8px 12px;
  font-size: 12px;
  line-height: 20px;
  color: #63656e;
  cursor: pointer;
  border-radius: 2px;

  &:hover,
  &.is-active {
    color: #3a84ff;
    background: #f0f1f5;
  }
}

.access-submenu-text {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.access-submenu-name {
  color: inherit;
}

.access-submenu-id {
  color: #63656e;
}

.access-submenu-empty {
  padding: 24px 0 8px;
  font-size: 12px;
  color: #979ba5;
  text-align: center;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity .15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0%;
}
</style>
