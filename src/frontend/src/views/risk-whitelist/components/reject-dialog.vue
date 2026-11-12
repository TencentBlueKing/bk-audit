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
  <bk-dialog
    v-model:is-show="isShow"
    :esc-close="false"
    :is-loading="loading"
    :quick-close="false"
    :title="t('驳回加白申请')"
    width="480"
    @closed="reset">
    <bk-alert
      theme="info"
      :title="t('驳回后关联风险单回到「待处理」，申请人可在风险单中看到驳回理由并重新提交。')" />
    <div class="desc-list">
      <div class="desc-row">
        <span class="desc-label">{{ t('规则ID') }}：</span>
        <span class="desc-value">{{ record?.rule_code || '--' }}</span>
      </div>
      <div class="desc-row">
        <span class="desc-label">{{ t('申请人') }}：</span>
        <span class="desc-value">{{ record?.applicant || record?.flow?.applicant || '--' }}</span>
      </div>
      <div class="desc-row">
        <span class="desc-label">{{ t('加白原因') }}：</span>
        <span class="desc-value">{{ record?.reason || '--' }}</span>
      </div>
    </div>
    <div class="reason-field">
      <div class="reason-label">{{ t('驳回理由') }}</div>
      <bk-input
        v-model="reason"
        :maxlength="200"
        :placeholder="t('请说明驳回理由，申请人将在风险单中看到')"
        :rows="2"
        type="textarea" />
      <div
        v-if="error"
        class="field-error">
        {{ error }}
      </div>
    </div>
    <template #footer>
      <bk-button
        data-testid="risk-whitelist-reject"
        :loading="loading"
        theme="danger"
        @click="handleSubmit">
        {{ t('驳回') }}
      </bk-button>
      <bk-button
       
        @click="isShow = false" style="margin-left: var(--bk-theme-space-8)">
        {{ t('取消') }}
      </bk-button>
    </template>
  </bk-dialog>
</template>
<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskWhitelistService from '@service/risk-whitelist';

  import type RiskWhitelist from '@model/risk-whitelist/whitelist';

  import useMessage from '@hooks/use-message';

  const emit = defineEmits<{(e: 'success'): void}>();
  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const isShow = ref(false);
  const loading = ref(false);
  const reason = ref('');
  const error = ref('');
  const record = ref<RiskWhitelist | null>(null);

  const open = (row: RiskWhitelist) => {
    record.value = row;
    reason.value = '';
    error.value = '';
    isShow.value = true;
  };

  const reset = () => {
    reason.value = '';
    error.value = '';
  };

  const handleSubmit = () => {
    if (!reason.value.trim()) {
      error.value = t('请说明驳回理由');
      return;
    }
    if (!record.value) return;
    loading.value = true;
    RiskWhitelistService.reject({
      id: record.value.id,
      reason: reason.value.trim(),
    }).then(() => {
      messageSuccess(t('已驳回，关联风险单回到待处理'));
      isShow.value = false;
      emit('success');
    })
      .finally(() => {
        loading.value = false;
      });
  };

  defineExpose({ open });
</script>
<style lang="postcss" scoped>
  .desc-list {
    display: flex;
    flex-direction: column;
    margin: var(--bk-theme-space-16) 0 var(--bk-theme-space-24);
    font-size: var(--bk-theme-font-size-sm);
    line-height: 20px;
  }

  .desc-row {
    box-sizing: border-box;
    display: flex;
    gap: var(--bk-theme-space-8);
    align-items: center;
    height: 26px;
    padding: var(--bk-theme-space-4) 0;
  }

  .desc-label {
    flex-shrink: 0;
    font-family: var(--bk-theme-font-family);
    font-size: var(--bk-theme-font-size-sm);
    font-style: normal;
    font-weight: var(--bk-theme-font-weight-regular);
    line-height: var(--bk-theme-line-height-sm);
    color: var(--bk-theme-text-default);
    text-align: left;
  }

  .desc-value {
    color: var(--bk-theme-text-strong);
  }

  .reason-field {
    display: flex;
    flex: none;
    flex-direction: column;
    gap: var(--bk-theme-space-6);
  }

  .reason-label {
    font-family: var(--bk-theme-font-family);
    font-size: var(--bk-theme-font-size-sm);
    font-style: normal;
    font-weight: var(--bk-theme-font-weight-regular);
    line-height: var(--bk-theme-line-height-sm);
    color: var(--bk-theme-text-default);
    text-align: left;
  }

  .reason-label::after {
    margin-left: var(--bk-theme-space-2);
    color: var(--bk-theme-color-danger-2);
    content: '*';
  }

  .reason-field :deep(textarea) {
    height: 60px;
    min-height: 60px;
  }

  .reason-field :deep(.bk-textarea--max-length) {
    word-spacing: -0.42em;
  }

  .field-error {
    width: 100%;
    color: var(--bk-theme-color-danger-2);
  }
</style>
