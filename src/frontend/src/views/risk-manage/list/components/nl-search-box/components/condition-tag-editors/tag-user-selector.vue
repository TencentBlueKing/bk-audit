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
    ref="popoverRef"
    :arrow="false"
    :is-show="isShow"
    placement="bottom-start"
    theme="light nl-tag-popover"
    trigger="manual"
    @after-hidden="handlePopoverHidden">
    <div
      ref="tagRef"
      class="condition-tag-item"
      :class="{ 'is-editing': isShow }"
      @click="handleToggle">
      <span class="tag-label">{{ t(tag.label) }}：</span>
      <span
        v-bk-tooltips="{
          content: fullDisplayValue,
          disabled: !isOverflow,
          extCls: 'nl-tag-tooltip-wrap',
        }"
        class="tag-value-wrapper">
        <span class="tag-value">{{ displayValue }}</span>
      </span>
      <audit-icon
        class="tag-remove-btn"
        type="close"
        @click.stop="$emit('remove', tag.fieldName)" />
    </div>
    <template #content>
      <div
        class="nl-tag-editor-popover nl-tag-user-popover"
        @click.stop
        @mousedown.stop>
        <!-- 搜索框 -->
        <div class="nl-tag-user-search">
          <audit-icon
            class="nl-tag-user-search-icon"
            type="search1" />
          <input
            ref="searchInputRef"
            v-model="searchKey"
            class="nl-tag-user-search-input"
            :placeholder="t('请输入关键字')"
            type="text"
            @input="handleSearchInput">
        </div>
        <!-- 用户列表 -->
        <div class="nl-tag-user-list">
          <div
            v-for="item in userList"
            :key="item.id"
            class="nl-tag-user-item"
            :class="{ 'is-selected': isUserSelected(item.username) }"
            @click="handleToggleUser(item.username)">
            <span class="nl-tag-user-name">{{ `${item.username}(${item.display_name})` }}</span>
            <audit-icon
              v-if="isUserSelected(item.username)"
              class="nl-tag-user-check"
              type="check-line" />
          </div>
          <!-- 空状态 -->
          <div
            v-if="userList.length === 0"
            class="nl-tag-user-empty">
            {{ emptyText }}
          </div>
        </div>
      </div>
    </template>
  </bk-popover>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import {
    computed,
    nextTick,
    onBeforeUnmount,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';

  import useRequest from '@hooks/use-request';

  import type { IConditionTag } from '../../types';

  interface Props {
    tag: IConditionTag;
    // eslint-disable-next-line vue/no-unused-properties
    searchModel: Record<string, any>;
    isEditing: boolean;
  }
  interface Emits {
    (e: 'startEdit', fieldName: string): void;
    (e: 'update', fieldName: string, value: any): void;
    (e: 'remove', fieldName: string): void;
    (e: 'finishEdit'): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const { t } = useI18n();

  const maxMultiLen = 10;
  const pageSize = 30;

  const isShow = ref(props.isEditing);
  const localValue = ref<string[]>([]);
  const tagRef = ref<HTMLElement>();
  const popoverRef = ref();
  const searchInputRef = ref<HTMLInputElement>();
  const searchKey = ref('');
  const emptyText = ref(t('请输入关键字'));
  // 用户名 -> 中文名 映射缓存
  const userDisplayMap = ref<Record<string, string>>({});

  // 远程搜索用户
  const {
    data: userData,
    run: fetchUsers,
  } = useRequest(MetaManageService.fetchUserList, {
    defaultParams: {
      page: 1,
      page_size: pageSize,
      fuzzy_lookups: '',
    },
    defaultValue: {
      count: 0,
      results: [],
    },
    onSuccess: (res) => {
      if (res.results.length <= 0) {
        emptyText.value = t('找不到对应用户');
      }
      // 将返回的用户信息缓存到映射表
      res.results.forEach((item: any) => {
        if (item.username && item.display_name) {
          userDisplayMap.value[item.username] = item.display_name;
        }
      });
    },
  });

  // 过滤后的用户列表
  const userList = computed(() => userData.value.results
    .filter((item: any) => item && item.username && item.id));

  // 判断用户是否已选中
  const isUserSelected = (username: string) => localValue.value.includes(username);

  // 加载初始用户列表（无搜索关键字时展示全部用户）
  const loadInitialUsers = () => {
    fetchUsers({
      page: 1,
      page_size: pageSize,
      fuzzy_lookups: '',
    });
  };

  // 防抖搜索
  const debouncedSearch = _.debounce((keyword: string) => {
    if (!_.trim(keyword)) {
      // 搜索关键字为空时，重新加载初始用户列表
      loadInitialUsers();
      return;
    }
    fetchUsers({
      page: 1,
      page_size: pageSize,
      fuzzy_lookups: keyword,
    });
  }, 300);

  const handleSearchInput = () => {
    debouncedSearch(searchKey.value);
  };

  // 选择/取消用户
  const handleToggleUser = (username: string) => {
    const index = localValue.value.indexOf(username);
    if (index > -1) {
      localValue.value.splice(index, 1);
    } else {
      localValue.value.push(username);
    }
    emit('update', props.tag.fieldName, [...localValue.value]);
  };

  // 格式化用户名（带中文名）
  const formatUser = (username: string) => {
    const displayName = userDisplayMap.value[username];
    return displayName ? `${username}(${displayName})` : username;
  };

  // 完整的显示值（用于 tooltip）
  const fullDisplayValue = computed(() => {
    const { value } = props.tag;
    if (!Array.isArray(value) || value.length === 0) return '--';
    return value.map(formatUser).join('，');
  });

  // 截断后的显示值
  const displayValue = computed(() => {
    const { value } = props.tag;
    if (!Array.isArray(value) || value.length === 0) return '--';
    let displayText = '';
    let visibleCount = 0;
    for (const item of value) {
      const formatted = formatUser(String(item));
      const nextText = visibleCount === 0 ? formatted : `${displayText}，${formatted}`;
      if (nextText.length > maxMultiLen && visibleCount > 0) break;
      displayText = nextText;
      visibleCount += 1;
    }
    const remaining = value.length - visibleCount;
    return remaining > 0 ? `${displayText}，+${remaining}` : displayText;
  });

  // 是否溢出（需要 tooltip）
  const isOverflow = computed(() => {
    const { value } = props.tag;
    if (!Array.isArray(value)) return false;
    return value.map(formatUser).join('，').length > maxMultiLen;
  });

  // 切换编辑态
  const handleToggle = () => {
    if (isShow.value) {
      emit('finishEdit');
    } else {
      emit('startEdit', props.tag.fieldName);
    }
  };

  // 点击外部区域关闭下拉框
  const handleDocumentClick = (e: MouseEvent) => {
    if (!isShow.value) return;
    const target = e.target as HTMLElement;
    if (tagRef.value?.contains(target)) return;
    const closestTippy = (target as Element)?.closest?.('.tippy-box[data-theme~="nl-tag-popover"]');
    if (closestTippy) return;
    emit('finishEdit');
  };

  const handlePopoverHidden = () => {
    // 由外部点击和 handleToggle 控制关闭
  };

  // 监听编辑态切换
  watch(() => props.isEditing, (val) => {
    isShow.value = val;
    if (val) {
      localValue.value = _.cloneDeep(props.tag.value) || [];
      searchKey.value = '';
      // 弹出时自动加载初始用户列表
      loadInitialUsers();
      nextTick(() => {
        searchInputRef.value?.focus();
      });
      setTimeout(() => {
        document.addEventListener('click', handleDocumentClick);
      });
    } else {
      document.removeEventListener('click', handleDocumentClick);
    }
  });

  onBeforeUnmount(() => {
    document.removeEventListener('click', handleDocumentClick);
  });
</script>
<style lang="postcss">
  /* popover 下拉样式（非 scoped，作用于 popover content） */
  .nl-tag-user-popover {
    width: 280px;
    padding: 0;

    .nl-tag-user-search {
      display: flex;
      padding: 4px 12px;
      align-items: center;
      border-bottom: 1px solid #dcdee5;

      .nl-tag-user-search-icon {
        margin-right: 6px;
        font-size: 15px;
        color: #979ba5;
        flex-shrink: 0;
      }

      .nl-tag-user-search-input {
        height: 32px;
        font-size: 12px;
        color: #63656e;
        background: transparent;
        border: none;
        outline: none;
        flex: 1;

        &::placeholder {
          color: #c4c6cc;
        }
      }
    }

    .nl-tag-user-list {
      max-height: 260px;
      padding: 4px 0;
      overflow-y: auto;

      /* 窄灰色滚动条 */
      &::-webkit-scrollbar {
        width: 4px;
      }

      &::-webkit-scrollbar-thumb {
        background: #c4c6cc;
        border-radius: 2px;
      }

      &::-webkit-scrollbar-track {
        background: transparent;
      }

      .nl-tag-user-item {
        display: flex;
        height: 36px;
        padding: 0 16px;
        font-size: 12px;
        color: #63656e;
        cursor: pointer;
        align-items: center;
        justify-content: space-between;
        transition: background .15s;

        &:hover {
          background: #f5f7fa;
        }

        &.is-selected {
          color: #3a84ff;
        }

        .nl-tag-user-check {
          font-size: 16px;
          color: #3a84ff;
        }
      }

      .nl-tag-user-empty {
        padding: 24px 0;
        font-size: 12px;
        color: #c4c6cc;
        text-align: center;
      }
    }
  }
</style>
