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
    :empty-text="emptyText"
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
  const resolvedPlaceholder = computed(() => props.placeholder || t('可搜索在职人员，离职人员请输入企微 ID后按回车键'));
  const emptyText = computed(() => {
    if (!props.allowCreate) return '';
    const name = searchKeyword.value.trim();
    if (!name) return '';
    return t('暂未匹配到人员({name})，可按enter填入', { name });
  });

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
    return createElement('div', {
      class: 'audit-user-render-item',
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

  const commitKeyword = (keyword: string) => {
    const name = keyword.trim();
    if (!name || !props.allowCreate) return;
    if (props.multiple) {
      const current = Array.isArray(localValue.value) ? [...localValue.value] : [];
      if (current.includes(name)) return;
      current.push(name);
      localValue.value = current;
      handleValueChange(current);
      return;
    }
    if (localValue.value === name) return;
    localValue.value = name;
    handleValueChange(name);
  };

  const getVisiblePopover = () => {
    const nodes = document.querySelectorAll('.bk-user-selector-popover');
    for (const node of nodes) {
      if (!(node instanceof HTMLElement)) continue;
      const style = window.getComputedStyle(node);
      if (style.display === 'none' || style.visibility === 'hidden') continue;
      if (node.getClientRects().length === 0) continue;
      return node;
    }
    return null;
  };

  const clearSearchInput = () => {
    if (!enterInputEl) return;
    enterInputEl.value = '';
    enterInputEl.dispatchEvent(new Event('input', { bubbles: true }));
    searchKeyword.value = '';
  };

  const handleBlur = () => {
    const keyword = searchKeyword.value.trim();
    const showUnmatched = Boolean(getVisiblePopover()?.querySelector('.no-data'));
    if (keyword && showUnmatched) {
      commitKeyword(keyword);
    }
    searchKeyword.value = '';
    emit('blur');
  };

  // 库在 allowCreate 且输入框有文字时，Enter 会直接创建输入值，盖过高亮项。
  // 有高亮人员时先选中该项；无匹配时仍把输入值交给库。外层表单不再收到这次 Enter。
  let rootEl: HTMLElement | null = null;
  let enterInputEl: HTMLInputElement | null = null;
  const isSearchInput = (target: EventTarget | null): target is HTMLInputElement => (
    target instanceof HTMLInputElement && target.classList.contains('search-input')
  );
  const handleKeydownCapture = (event: KeyboardEvent) => {
    if (event.isComposing || event.key === 'Process' || event.keyCode === 229) return;
    if (event.key !== 'Enter' || !isSearchInput(event.target)) return;
    const highlighted = getVisiblePopover()
      ?.querySelector('.user-option.is-highlighted:not(.is-disabled)');
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
  };
  const handleFocusIn = (event: FocusEvent) => {
    if (!isSearchInput(event.target)) return;
    enterInputEl = event.target;
  };
  const handleDocumentMouseDown = (event: MouseEvent) => {
    if (document.activeElement !== enterInputEl) return;
    const target = event.target;
    if (!(target instanceof Element) || !target.closest('.bk-user-selector-popover .no-data')) return;
    const keyword = searchKeyword.value.trim();
    if (!keyword) return;
    event.preventDefault();
    commitKeyword(keyword);
    clearSearchInput();
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
  });

  onBeforeUnmount(() => {
    rootEl?.removeEventListener('keydown', handleKeydownCapture, true);
    rootEl?.removeEventListener('keydown', handleKeydownBubble);
    rootEl?.removeEventListener('input', handleSearchInput);
    rootEl?.removeEventListener('focusin', handleFocusIn);
    document.removeEventListener('mousedown', handleDocumentMouseDown, true);
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
      align-items: center;
      color: #63656e;
      background-color: #f0f1f5;
      border-color: #f0f1f5;
    }

    /* 聚焦时库会给当前标签加 active，改成蓝底蓝边；保持和未聚焦一致 */
    .user-tag.user-tag.active {
      color: #63656e;
      background-color: #f0f1f5;
      border-color: #979ba54d;
    }

    .user-tag.user-tag.active:hover {
      background-color: #dcdee5;
    }

    /* 离职/不存在：灰色 tag + 失效字色 #c4c6cc */
    .custom-tag.is-resigned {
      color: #c4c6cc;
      background-color: #f0f1f5;
      border-color: #f0f1f5;
    }

    .user-tag.is-custom {
      color: #c4c6cc !important;
      background-color: #f0f1f5 !important;
      border-color: #f0f1f5 !important;
    }

    .user-tag.is-custom:hover {
      color: #c4c6cc !important;
      background-color: #f0f1f5 !important;
    }

    .user-tag.is-custom .tag-content .user-name {
      color: #c4c6cc !important;
    }

    &.nl-tag-user-selector .user-tag.is-custom,
    &.nl-tag-user-selector .user-tag.is-custom .tag-content .user-name,
    &.nl-tag-user-selector .custom-tag.is-resigned {
      color: #c4c6cc !important;
      background-color: #f0f1f5 !important;
      border-color: #f0f1f5 !important;
    }

    &.nl-tag-user-selector .user-tag.is-custom:hover {
      color: #c4c6cc !important;
      background-color: #f0f1f5 !important;
    }

    .avatar {
      width: 16px;
      height: 16px;
      margin-right: 4px;
      border-radius: 50%;
    }
  }

  .bk-user-selector-popover .dropdown-content .no-data {
    display: flex;
    align-items: center;
    height: var(--audit-space-32);
    padding: var(--audit-space-8) var(--audit-space-12);
    color: var(--audit-neutral-text-02);
    text-align: left;
    cursor: pointer;
    background-color: var(--audit-neutral-bg-03);
  }

  .bk-user-selector-popover .dropdown-content .no-data span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .bk-user-selector-popover .dropdown-content:has(.bk-loading-indicator) .no-data {
    display: none;
  }
</style>
