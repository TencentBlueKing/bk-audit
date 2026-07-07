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
    :multiple="multiple"
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
    ref,
    watch,
  } from 'vue';

  import BkUserSelector from '@blueking/bk-user-selector';

  import '@blueking/bk-user-selector/vue3/vue3.css';

  interface Props {
    modelValue: Array<string> | string;
    allowCreate?: boolean;
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
    allowCreate: false,
    multiple: true,
    // collapseTags: true,
    // needRecord: false,
    isDisabled: false,
    autoFocus: false,
    userGroup: () => [],
    userGroupName: '用户组',
  });

  const emit = defineEmits<Emits>();
  const userSelectorRef = ref();

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

  const isResignedUser = (userInfo: Record<string, any> | string) => {
    if (!userInfo || typeof userInfo !== 'object') {
      return false;
    }
    if (userInfo.type === 'custom') {
      return true;
    }
    const { status } = userInfo;
    if (status && status !== '在职') {
      return true;
    }
    const staffStatus = userInfo.staff_status;
    if (staffStatus && String(staffStatus).includes('离职')) {
      return true;
    }
    return false;
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
    const resigned = isResignedUser(userInfo);
    const displayText = userInfo.display_name
      || userInfo.name
      || userInfo.username
      || userInfo.bk_username
      || userInfo.id
      || '';
    return createElement('div', {
      class: ['audit-user-render-item', { 'is-resigned': resigned }],
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
    emit('update:modelValue', v);
    emit('change', v);
  };

  const handleBlur = () => {
    emit('blur');
  };

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

    .audit-user-render-item.is-resigned .audit-user-render-item__name {
      color: #c4c6cc;
    }

    .avatar {
      width: 16px;
      height: 16px;
      margin-right: 4px;
      border-radius: 50%;
    }
  }
</style>
