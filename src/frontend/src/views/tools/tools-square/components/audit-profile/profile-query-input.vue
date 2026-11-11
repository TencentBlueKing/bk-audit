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
  <div class="top-search">
    <div class="top-search-title">
      {{ t('查询输入') }}
    </div>
    <div class="query-form">
      <div class="form-item">
        <div class="form-label">
          {{ t('账号类型') }}
          <span class="required">*</span>
        </div>
        <div class="account-type-group">
          <div
            v-for="item in visibleAccountTypes"
            :key="item.value"
            class="account-type-item"
            :class="{ active: selectedAccountType === item.value }"
            @click="handleAccountTypeChange(item.value)">
            {{ item.label }}
          </div>
        </div>
      </div>
      <div class="form-item">
        <div class="form-label">
          {{ t('账号标识') }}
          <span class="required">*</span>
        </div>
        <bk-input
          v-model="accountId"
          class="account-input"
          :placeholder="accountPlaceholder"
          @keydown="handleKeydown" />
      </div>
    </div>
    <div class="query-actions">
      <bk-button
        class="query-btn"
        :disabled="isThrottled || loading"
        :loading="loading"
        theme="primary"
        @click="handleQuery" style="margin-right: var(--bk-theme-space-8)">
        {{ t('查询') }}
      </bk-button>
      <bk-button
        class="query-btn"
        @click="handleReset">
        {{ t('重置') }}
      </bk-button>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import useMessage from '@hooks/use-message';

  interface Props {
    loading?: boolean;
    /** 为 null 时展示全部账号类型；有值时只展示这些取值 */
    allowedAccountTypes?: string[] | null;
  }

  interface Emits {
    (e: 'query', accountType: string, accountId: string): void;
    (e: 'reset'): void;
  }

  interface Exposes {
    resetForm: () => void;
    setForm: (accountType: string, account: string) => void;
    getFormValues: () => { accountType: string; accountId: string };
  }

  const props = withDefaults(defineProps<Props>(), {
    loading: false,
    allowedAccountTypes: null,
  });
  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const { messageWarn } = useMessage();


  const isThrottled = ref(false);
  const throttleDelay = 2000; // 2秒节流间隔

  const accountTypes = [
    { label: t('企业微信'), value: 'ctx' },
    { label: 'openid', value: 'openid' },
    { label: t('微信'), value: 'form_wechat' },
    { label: 'QQ', value: 'form_qq' },
  ];

  const selectedAccountType = ref('ctx');
  const accountId = ref('');

  const visibleAccountTypes = computed(() => {
    if (!props.allowedAccountTypes) return accountTypes;
    return accountTypes.filter(item => props.allowedAccountTypes?.includes(item.value));
  });

  const defaultAccountType = () => visibleAccountTypes.value[0]?.value || 'ctx';

  watch(visibleAccountTypes, (list) => {
    if (!list.length) return;
    if (!list.some(item => item.value === selectedAccountType.value)) {
      selectedAccountType.value = list[0].value;
      accountId.value = '';
    }
  }, { immediate: true });

  // 根据选择的账号类型动态生成 placeholder
  const placeholderMap: Record<string, string> = {
    ctx: '请输入企业微信账号',
    openid: '请输入 openid',
    form_wechat: '请输入微信号',
    form_qq: '请输入QQ号',
  };

  const accountPlaceholder = computed(() => t(placeholderMap[selectedAccountType.value] || '请输入'));

  const handleAccountTypeChange = (value: string) => {
    if (!visibleAccountTypes.value.some(item => item.value === value)) {
      return;
    }
    if (selectedAccountType.value === value) {
      return;
    }
    selectedAccountType.value = value;
    accountId.value = '';
  };

  // 查询
  const handleQuery = () => {
    if (isThrottled.value || props.loading) {
      return;
    }
    const trimmedAccountId = accountId.value.trim();
    if (!trimmedAccountId) {
      messageWarn(t('账号标识不能为空'));
      return;
    }
    accountId.value = trimmedAccountId;
    emit('query', selectedAccountType.value, trimmedAccountId);


    isThrottled.value = true;
    setTimeout(() => {
      isThrottled.value = false;
    }, throttleDelay);
  };

  // 输入框 keydown 事件
  // bk-input 的 keydown 回调签名为 (value: string, event: KeyboardEvent)
  const handleKeydown = (value: string, event: KeyboardEvent) => {
    if (event.key !== 'Enter') {
      return;
    }
    // 输入法组合输入状态下的回车（中文输入法确认候选词）不触发查询。
    // 浏览器原生提供两种判断方式：
    // 1. event.isComposing：现代浏览器标准 API
    // 2. event.keyCode === 229：老浏览器中输入法交互时 keydown 的特殊 keyCode
    if (event.isComposing || event.keyCode === 229) {
      return;
    }
    handleQuery();
  };

  // 重置
  const handleReset = () => {
    accountId.value = '';
    selectedAccountType.value = defaultAccountType();
    emit('reset');
  };

  // 重置表单（供父组件调用）
  const resetForm = () => {
    accountId.value = '';
    selectedAccountType.value = defaultAccountType();
  };

  // 设置表单值（供父组件恢复状态时调用）
  const setForm = (accountType: string, account: string) => {
    if (!visibleAccountTypes.value.some(item => item.value === accountType)) {
      selectedAccountType.value = defaultAccountType();
      accountId.value = '';
      return;
    }
    selectedAccountType.value = accountType;
    accountId.value = account;
  };

  // 获取当前表单值（供父组件读取）
  const getFormValues = () => ({
    accountType: selectedAccountType.value,
    accountId: accountId.value,
  });

  defineExpose<Exposes>({
    resetForm,
    setForm,
    getFormValues,
  });
</script>

<style scoped lang="postcss">
.top-search {padding: var(--bk-theme-space-16) var(--bk-theme-space-24) var(--bk-theme-space-24);
  background: var(--bk-theme-surface-default);

  .top-search-title {
    margin-bottom: var(--bk-theme-space-16);
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    letter-spacing: 0;
    color: var(--bk-theme-text-strong);
  }
}

.query-form {
  display: flex;
  gap: var(--bk-theme-space-24);
  margin-top: var(--bk-theme-space-16);
  align-items: flex-end;
  flex-wrap: wrap;
}

.form-item {
  .form-label {
    display: flex;
    margin-bottom: var(--bk-theme-space-8);
    font-size: 12px;
    line-height: 22px;
    color: var(--bk-theme-text-default);
    align-items: center;
    gap: var(--bk-theme-space-4);

    .required {
      color: var(--bk-theme-color-danger-2);
    }
  }
}

.account-type-group {
  display: flex;
  border-radius: var(--bk-theme-tag-radius);

  .account-type-item {
    width: 88px;
    margin-left: -var(--bk-theme-space-2);
    font-size: 12px;
    line-height: 30px;
    color: var(--bk-theme-text-default);
    text-align: center;
    cursor: pointer;
    background: var(--bk-theme-surface-default);
    border: 1px solid var(--bk-theme-border-strong);
    transition: all .15s;

    &:first-child {
      margin-left: 0;border-radius: var(--bk-theme-control-radius) 0 0 var(--bk-theme-control-radius);
    }

    &:last-child {border-radius: 0 var(--bk-theme-control-radius) var(--bk-theme-control-radius) 0;
    }

    &:hover {
      color: var(--bk-theme-color-brand-2);
      background: var(--bk-theme-fill-selected);
    }

    &.active {
      position: relative;
      z-index: 1;
      color: var(--bk-theme-color-brand-2);
      background: var(--bk-theme-fill-selected);
      border-color: var(--bk-theme-color-brand-2);
    }
  }
}

.account-input {
  width: 400px;
}

.query-actions {
  margin-top: var(--bk-theme-space-24);

  .query-btn {
    height: 32px;
    min-width: 88px;
    padding: 0 var(--bk-theme-space-16);
    font-size: 14px;
  }
}
</style>
