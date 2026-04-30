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
            v-for="item in accountTypes"
            :key="item.value"
            class="account-type-item"
            :class="{ active: selectedAccountType === item.value }"
            @click="selectedAccountType = item.value">
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
          :placeholder="accountPlaceholder" />
      </div>
    </div>
    <div class="query-actions">
      <bk-button
        class="mr8"
        theme="primary"
        @click="handleQuery">
        {{ t('查询') }}
      </bk-button>
      <bk-button
        @click="handleReset">
        {{ t('重置') }}
      </bk-button>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Emits {
    (e: 'query', accountType: string, accountId: string): void;
    (e: 'reset'): void;
  }

  interface Exposes {
    resetForm: () => void;
  }

  const emit = defineEmits<Emits>();
  const { t } = useI18n();

  const accountTypes = [
    { label: t('企业微信'), value: 'ctx' },
    { label: 'openid', value: 'openid' },
    { label: t('微信'), value: 'form_wechat' },
    { label: 'QQ', value: 'form_qq' },
  ];

  const selectedAccountType = ref('ctx');
  const accountId = ref('');

  // 根据选择的账号类型动态生成 placeholder
  const placeholderMap: Record<string, string> = {
    ctx: '请输入企业微信账号，如 frodomei',
    openid: '请输入 openid，如 47B1fC4b-dc0c-86dB-4f7D-d0FF16EDCe19',
    form_wechat: '请输入微信号',
    form_qq: '请输入QQ号',
  };

  const accountPlaceholder = computed(() => t(placeholderMap[selectedAccountType.value] || '请输入'));

  // 查询
  const handleQuery = () => {
    emit('query', selectedAccountType.value, accountId.value);
  };

  // 重置
  const handleReset = () => {
    accountId.value = '';
    selectedAccountType.value = 'ctx';
    emit('reset');
  };

  // 重置表单（供父组件调用）
  const resetForm = () => {
    accountId.value = '';
    selectedAccountType.value = 'ctx';
  };

  defineExpose<Exposes>({
    resetForm,
  });
</script>

<style scoped lang="postcss">
.top-search {
  padding: 16px 24px 22px;
  background: #fff;

  .top-search-title {
    margin-bottom: 16px;
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    letter-spacing: 0;
    color: #313238;
  }
}

.query-form {
  display: flex;
  gap: 24px;
  margin-top: 16px;
  align-items: flex-end;
  flex-wrap: wrap;
}

.form-item {
  .form-label {
    display: flex;
    margin-bottom: 8px;
    font-size: 12px;
    line-height: 22px;
    color: #63656e;
    align-items: center;
    gap: 4px;

    .required {
      color: #ea3636;
    }
  }
}

.account-type-group {
  display: flex;
  border-radius: 2px;

  .account-type-item {
    width: 88px;
    margin-left: -1px;
    font-size: 12px;
    line-height: 30px;
    color: #63656e;
    text-align: center;
    cursor: pointer;
    background: #fff;
    border: 1px solid #c4c6cc;
    transition: all .15s;

    &:first-child {
      margin-left: 0;
      border-radius: 2px 0 0 2px;
    }

    &:last-child {
      border-radius: 0 2px 2px 0;
    }

    &:hover {
      color: #3a84ff;
      background: #e1ecff;
    }

    &.active {
      position: relative;
      z-index: 1;
      color: #3a84ff;
      background: #e1ecff;
      border-color: #3a84ff;
    }
  }
}

.account-input {
  width: 400px;
}

.query-actions {
  margin-top: 16px;
}
</style>
