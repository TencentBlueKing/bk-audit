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
  <bk-user-selector
    v-bind="$attrs"
    ref="userSelectorRef"
    v-model="localValue"
    :allow-create="allowCreate"
    :api-base-url="apiBaseUrl"
    :auto-focus="autoFocus"
    :disabled="isDisabled"
    empty-text=""
    :free-paste="freePasteEnabled"
    :multiple="multiple"
    :placeholder="resolvedPlaceholder"
    :render-list-item="renderListItem"
    :render-tag="renderTag"
    :tenant-id="tenantId"
    :user-group="userGroup"
    :user-group-name="userGroupName"
    @blur="handleBlur"
    @update:model-value="handleValueChange" />
</template>

<script setup lang="ts">
  import {
    computed,
    nextTick,
    ref,
    onBeforeUnmount,
    onMounted,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import BkUserSelector from '@blueking/bk-user-selector';

  import '@blueking/bk-user-selector/vue3/vue3.css';

  interface Props {
    modelValue: Array<string> | string;
    allowCreate?: boolean;
    /** 未传入时使用人员选择器默认占位；调用方传入的文案保持不变 */
    placeholder?: string;
    /** 粘贴未命中用户中心的人员时是否创建（离职人员等）；默认跟随 allowCreate */
    freePaste?: boolean;
    multiple?: boolean;
    // collapseTags?: boolean;  //bk-select 属性 bk-user-select 不支持
    // needRecord?: boolean;
    isDisabled?: boolean;
    autoFocus?: boolean;
    userGroup?: Array<{ id: string; name: string; }>;
    userGroupName?: string;
  }

  interface Emits {
    (e: 'update:modelValue', value: Array<string> | string): void;
    (e: 'change', value: Array<string> | string): void;
    (e: 'blur'): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    modelValue: () => [],
    allowCreate: true,
    placeholder: '',
    freePaste: undefined,
    multiple: true,
    // collapseTags: true,
    // needRecord: false,
    isDisabled: false,
    autoFocus: false,
    userGroup: () => [],
    userGroupName: '用户组',
  });

  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const userSelectorRef = ref();
  const searchKeyword = ref('');
  const resolvedPlaceholder = computed(() => props.placeholder || t('搜索在职人员，未匹配人员可按 Enter 填入'));
  const normalizeMatchText = (value: unknown) => String(value ?? '').trim().toLowerCase();
  const readExposed = <T>(value: unknown, fallback: T): T => {
    if (value === undefined || value === null) return fallback;
    if (typeof value === 'object' && 'value' in value && !Array.isArray(value)) {
      return (value as { value: T }).value;
    }
    return value as T;
  };
  const hasExactMatch = (keyword: string) => {
    const target = normalizeMatchText(keyword);
    if (!target) return false;
    const popover = getVisiblePopover();
    const matchedUser = Array.from(popover?.querySelectorAll('.audit-user-render-item') ?? []).some(node => (
      (node.getAttribute('data-match-values') || '').split('\u001f').includes(target)
    ));
    if (matchedUser) return true;
    return (props.userGroup ?? []).some(group => (
      normalizeMatchText(group.id) === target || normalizeMatchText(group.name) === target
    ));
  };
  const isSearchLoading = () => {
    const selectorState = userSelectorRef.value as { searchLoading?: boolean | { value: boolean } } | undefined;
    return Boolean(readExposed(selectorState?.searchLoading, false));
  };

  // allowCreate 开启时默认同步开启 freePaste，否则粘贴离职/不存在人员会被丢弃
  const freePasteEnabled = computed(() => (
    props.freePaste === undefined ? props.allowCreate : props.freePaste
  ));

  const normalizeModelValue = (modelValue: Props['modelValue']): Props['modelValue'] => {
    if (props.multiple) {
      if (Array.isArray(modelValue)) {
        return modelValue;
      }
      return modelValue ? [String(modelValue)] : [];
    }
    if (Array.isArray(modelValue)) {
      return modelValue[0] || '';
    }
    return modelValue || '';
  };

  const localValue = ref<Props['modelValue']>(normalizeModelValue(props.modelValue));

  const getUserGroupLabel = (id: string) => {
    const groupItem = props.userGroup?.find(item => item.id === id);
    return groupItem?.name || '';
  };

  const getTagDisplayText = (userInfo: Record<string, any> | string) => {
    if (!userInfo) {
      return '';
    }
    if (typeof userInfo === 'string') {
      return getUserGroupLabel(userInfo) || userInfo;
    }
    const id = userInfo.id || userInfo.username || userInfo.bk_username || '';
    return userInfo.display_name
      || userInfo.name
      || getUserGroupLabel(id)
      || userInfo.username
      || userInfo.bk_username
      || id;
  };
  // 离职/不存在人员：用户中心未命中（含 allowCreate、freePaste 的 custom）用灰色失效字色
  // 命中列表（含搜索到的用户）用正常样式 —— 对齐 c77c074c8 / 776efa61b
  const isUserInList = (userInfo: Record<string, any>) => {
    if (userInfo.type === 'custom') {
      return false;
    }
    if (userInfo.type === 'userGroup' || userInfo.type === 'virtual') {
      return true;
    }
    if (userInfo.display_name || userInfo.data_source_type) {
      return true;
    }
    const loginName = userInfo.login_name || userInfo.bk_username || userInfo.username || '';
    if (loginName && userInfo.name && userInfo.name !== loginName) {
      return true;
    }
    return false;
  };

  const isResignedUser = (userInfo: Record<string, any> | string) => {
    if (!userInfo || typeof userInfo !== 'object') {
      return false;
    }
    return !isUserInList(userInfo);
  };
  // 自定义标签渲染（兼容用户组变量：无 display_name / logo）
  const renderTag = (createElement: any, userInfo: Record<string, any> | string) => {
    const displayText = getTagDisplayText(userInfo);
    const resigned = isResignedUser(userInfo);
    const children: any[] = [];
    if (userInfo && typeof userInfo === 'object' && userInfo.logo) {
      children.push(createElement('img', { src: userInfo.logo, class: 'avatar' }));
    }
    children.push(displayText);
    return createElement('span', {
      class: ['custom-tag', { 'is-resigned': resigned }],
    }, children);
  };

  const renderListItem = (createElement: any, userInfo: Record<string, any>) => {
    const displayText = userInfo.display_name
      || userInfo.name
      || userInfo.username
      || userInfo.bk_username
      || userInfo.id
      || '';
    const matchValues = [
      userInfo.id,
      userInfo.name,
      userInfo.bk_username,
      userInfo.username,
      userInfo.login_name,
      userInfo.display_name,
      userInfo.full_name,
    ].map(value => normalizeMatchText(value)).filter(Boolean);
    return createElement('div', {
      class: 'audit-user-render-item',
      'data-match-values': Array.from(new Set(matchValues)).join('\u001f'),
    }, [
      createElement('span', { class: 'audit-user-render-item__name' }, displayText),
    ]);
  };
  // 从sessionStorage中获取配置
  const getConfig = () => {
    try {
      const configStr = sessionStorage.getItem('BK_AUDIT_CONFIG');
      if (configStr) {
        return JSON.parse(configStr);
      }
    } catch (e) {
      console.error('Failed to parse BK_AUDIT_CONFIG:', e);
    }
    return null;
  };
  // 计算apiBaseUrl
  // apiBaseUrl 由后端配置中的 BK_API_URL_TMPL 与 BK_USER_WEB_APIGW_URL 以及网关环境拼接而成
  const apiBaseUrl = computed(() => {
    const config = getConfig();
    if (config?.tenant_config?.BK_USER_WEB_APIGW_URL) {
      return config?.tenant_config?.BK_USER_WEB_APIGW_URL;
    }
    return '';
  });
  // 获取租户ID
  const tenantId = computed(() => {
    const config = getConfig();
    if (config?.tenant_config?.BK_TENANT_ID) {
      return config.tenant_config.BK_TENANT_ID;
    }
    return '';
  });

  const handleValueChange = (v: string | string[]) => {
    searchKeyword.value = '';
    emit('update:modelValue', v);
    emit('change', v);
  };

  const getVisiblePopover = () => {
    const nodes = Array.from(document.querySelectorAll('.bk-user-selector-popover'));
    for (const node of nodes) {
      if (!(node instanceof HTMLElement)) continue;
      const style = window.getComputedStyle(node);
      if (style.display === 'none' || style.visibility === 'hidden') continue;
      if (node.getClientRects().length === 0) continue;
      return node;
    }
    return null;
  };

  const CREATE_OPTION_SELECTOR = '.audit-user-create-option';
  let createOptionTimer = 0;
  let createOptionActive = false;
  // 搜索结果出来后库会高亮第一条人员。在用户按向下键之前，光标停在「按 Enter 填入」。
  let createOptionPinned = true;

  const syncCreateOption = () => {
    const popover = getVisiblePopover();
    const content = popover?.querySelector('.dropdown-content');
    if (!content) return;
    const keyword = searchKeyword.value.trim();
    const canCreate = props.allowCreate && Boolean(keyword) && !isSearchLoading() && !hasExactMatch(keyword);
    const current = content.querySelector(CREATE_OPTION_SELECTOR);
    if (!canCreate) {
      current?.remove();
      createOptionActive = false;
      createOptionPinned = true;
      content.classList.remove('is-create-option-active');
      return;
    }
    if (createOptionPinned) createOptionActive = true;
    let option = current;
    if (!(option instanceof HTMLElement)) {
      option = document.createElement('div');
      option.className = 'audit-user-create-option';
      const name = document.createElement('span');
      name.className = 'audit-user-create-option__name';
      const hint = document.createElement('span');
      hint.className = 'audit-user-create-option__hint';
      option.append(name, hint);
      content.insertBefore(option, content.firstChild);
    }
    const nameEl = option.querySelector('.audit-user-create-option__name');
    const hintEl = option.querySelector('.audit-user-create-option__hint');
    const hintText = t('(按 Enter 填入)');
    if (nameEl && nameEl.textContent !== keyword) nameEl.textContent = keyword;
    if (hintEl && hintEl.textContent !== hintText) hintEl.textContent = hintText;
    option.classList.toggle('is-current', createOptionActive);
    content.classList.toggle('is-create-option-active', createOptionActive);
    if (createOptionActive) {
      content.querySelectorAll('.user-option.is-highlighted').forEach((el) => {
        el.classList.remove('is-highlighted');
      });
      return;
    }
    if (!content.querySelector('.user-option.is-highlighted')) {
      content.querySelector('.user-option:not(.is-disabled)')?.classList.add('is-highlighted');
    }
  };

  // 库的搜索有防抖，结果渲染时会清掉手动插入的节点。只跟一段时间，不再监听 DOM，避免插入后又触发回调。
  const scheduleSyncCreateOption = () => {
    window.clearInterval(createOptionTimer);
    let ticks = 0;
    let sawLoading = false;
    const run = () => {
      const loading = isSearchLoading();
      if (loading) sawLoading = true;
      syncCreateOption();
      ticks += 1;
      const settled = sawLoading && !loading;
      if (!searchKeyword.value.trim() || ticks >= 30) {
        window.clearInterval(createOptionTimer);
        return;
      }
      if (settled) {
        window.clearInterval(createOptionTimer);
        window.setTimeout(syncCreateOption, 0);
        window.setTimeout(syncCreateOption, 50);
        window.setTimeout(syncCreateOption, 200);
      }
    };
    run();
    createOptionTimer = window.setInterval(run, 100);
  };

  const handleBlur = () => {
    searchKeyword.value = '';
    emit('blur');
  };

  // 库会把高亮停在第一个人员上。只要「按 Enter 填入」还在，默认就停在这一行；
  // 这时 Enter 不拦截，交给库自己创建，光标会立刻落到标签后面。移到人员上再按 Enter 才选中那个人。
  let rootEl: HTMLElement | null = null;
  let enterInputEl: HTMLInputElement | null = null;
  const isSearchInput = (target: EventTarget | null): target is HTMLInputElement => (
    target instanceof HTMLInputElement && target.classList.contains('search-input')
  );
  const handleKeydownCapture = (event: KeyboardEvent) => {
    if (event.isComposing || event.key === 'Process' || event.keyCode === 229) return;
    if (!isSearchInput(event.target)) return;
    const popover = getVisiblePopover();
    const content = popover?.querySelector('.dropdown-content');
    const createOption = content?.querySelector(CREATE_OPTION_SELECTOR);
    if (event.key === 'ArrowUp' && createOption instanceof HTMLElement) {
      const highlighted = content?.querySelector('.user-option.is-highlighted');
      const firstUser = content?.querySelector('.user-option');
      if (createOptionActive || (highlighted instanceof HTMLElement && highlighted === firstUser)) {
        event.preventDefault();
        event.stopPropagation();
        createOptionPinned = true;
        createOptionActive = true;
        syncCreateOption();
        return;
      }
    }
    if (event.key === 'ArrowDown' && createOptionActive) {
      event.preventDefault();
      event.stopPropagation();
      createOptionPinned = false;
      createOptionActive = false;
      syncCreateOption();
      return;
    }
    if (event.key !== 'Enter') return;
    if (createOptionActive) return;
    const highlighted = popover?.querySelector('.user-option.is-highlighted:not(.is-disabled)');
    if (!(highlighted instanceof HTMLElement)) return;
    event.preventDefault();
    event.stopPropagation();
    highlighted.click();
  };
  const handleKeydownBubble = (event: KeyboardEvent) => {
    if (event.key !== 'Enter' || !isSearchInput(event.target)) return;
    event.stopPropagation();
  };
  const handleSearchInput = (event: Event) => {
    if (!isSearchInput(event.target)) return;
    enterInputEl = event.target;
    searchKeyword.value = event.target.value;
    createOptionPinned = true;
    createOptionActive = true;
    scheduleSyncCreateOption();
  };
  const handleFocusIn = (event: FocusEvent) => {
    if (!isSearchInput(event.target)) return;
    enterInputEl = event.target;
  };
  const handleDocumentMouseDown = (event: MouseEvent) => {
    if (!enterInputEl || document.activeElement !== enterInputEl) return;
    const target = event.target;
    if (!(target instanceof Element) || !target.closest('.bk-user-selector-popover .no-data, .audit-user-create-option')) return;
    const keyword = searchKeyword.value.trim();
    if (!keyword) return;
    event.preventDefault();
    createOptionActive = true;
    enterInputEl.dispatchEvent(new KeyboardEvent('keydown', {
      key: 'Enter',
      code: 'Enter',
      bubbles: true,
      cancelable: true,
    }));
  };

  onMounted(async () => {
    await nextTick();
    rootEl = userSelectorRef.value?.$el as HTMLElement | null | undefined ?? null;
    if (!rootEl) return;
    rootEl.addEventListener('keydown', handleKeydownCapture, true);
    rootEl.addEventListener('keydown', handleKeydownBubble);
    rootEl.addEventListener('input', handleSearchInput);
    rootEl.addEventListener('focusin', handleFocusIn);
    document.addEventListener('mousedown', handleDocumentMouseDown, true);
    rootEl.addEventListener('keyup', syncCreateOption);
  });

  onBeforeUnmount(() => {
    rootEl?.removeEventListener('keydown', handleKeydownCapture, true);
    rootEl?.removeEventListener('keydown', handleKeydownBubble);
    rootEl?.removeEventListener('input', handleSearchInput);
    rootEl?.removeEventListener('focusin', handleFocusIn);
    document.removeEventListener('mousedown', handleDocumentMouseDown, true);
    rootEl?.removeEventListener('keyup', syncCreateOption);
    window.clearInterval(createOptionTimer);
    rootEl = null;
    enterInputEl = null;
  });

  watch(
    () => [props.modelValue, props.multiple] as const,
    ([modelValue]) => {
      localValue.value = normalizeModelValue(modelValue);
    },
    {
      immediate: true,
      deep: true,
    },
  );
</script>

<style lang="postcss">
  .bk-user-selector {
    width: 100%;

    .custom-tag {
      display: inline-flex;
      align-items: center;color: var(--bk-theme-text-default);background-color: var(--bk-theme-surface-muted);border-color: var(--bk-theme-surface-muted);
    }

    /* 聚焦时库会给当前标签加 active，改成蓝底蓝边；保持和未聚焦一致 */
    .user-tag.user-tag.active {color: var(--bk-theme-text-default);background-color: var(--bk-theme-surface-muted);
      border-color: #979ba54d;
    }

    .user-tag.user-tag.active:hover {background-color: var(--bk-theme-border-default);
    }

    /* 离职/不存在：灰色 tag + 失效字色 #c4c6cc */
    .custom-tag.is-resigned {color: var(--bk-theme-text-disabled);background-color: var(--bk-theme-surface-muted);border-color: var(--bk-theme-surface-muted);
    }

    .user-tag.is-custom {color: var(--bk-theme-text-disabled) !important;background-color: var(--bk-theme-surface-muted) !important;border-color: var(--bk-theme-surface-muted) !important;
    }

    .user-tag.is-custom:hover {color: var(--bk-theme-text-disabled) !important;background-color: var(--bk-theme-surface-muted) !important;
    }

    .user-tag.is-custom .tag-content .user-name {color: var(--bk-theme-text-disabled) !important;
    }

    &.nl-tag-user-selector .user-tag.is-custom,
    &.nl-tag-user-selector .user-tag.is-custom .tag-content .user-name,
    &.nl-tag-user-selector .custom-tag.is-resigned {color: var(--bk-theme-text-disabled) !important;background-color: var(--bk-theme-surface-muted) !important;border-color: var(--bk-theme-surface-muted) !important;
    }

    &.nl-tag-user-selector .user-tag.is-custom:hover {color: var(--bk-theme-text-disabled) !important;background-color: var(--bk-theme-surface-muted) !important;
    }

    .avatar {
      width: 16px;
      height: 16px;margin-right: var(--bk-theme-space-4);
      border-radius: 50%;
    }
  }

  .bk-user-selector-popover .dropdown-content .audit-user-create-option {
    display: flex;
    align-items: center;
    height: var(--bk-theme-space-32);
    padding: var(--bk-theme-space-8) var(--bk-theme-space-12);
    overflow: hidden;
    cursor: pointer;
    gap: var(--bk-theme-space-8);
  }

  .bk-user-selector-popover .dropdown-content.is-create-option-active .user-option.is-highlighted,
  .bk-user-selector-popover .dropdown-content.is-create-option-active .user-option.is-highlighted:hover {
    background-color: transparent;
  }

  .bk-user-selector-popover .dropdown-content .audit-user-create-option:hover,
  .bk-user-selector-popover .dropdown-content .audit-user-create-option.is-current {
    background-color: var(--bk-theme-table-row-hover);
  }

  .bk-user-selector-popover .dropdown-content .audit-user-create-option__name {
    overflow: hidden;
    color: var(--bk-theme-text-default);
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .bk-user-selector-popover .dropdown-content .audit-user-create-option__hint {
    flex: none;
    color: var(--bk-theme-text-weak);
  }

  .bk-user-selector-popover .dropdown-content:has(.audit-user-create-option) .no-data,
  .bk-user-selector-popover .dropdown-content:has(.bk-loading-indicator) .no-data {
    display: none;
  }
</style>
