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
    :quick-close="false"
    :title="t('续期白名单')"
    width="480"
    @closed="reset">
    <bk-alert
      class="renew-alert"
      theme="info"
      :title="t('续期会把到期时间重置为本次选择的有效期,而不是在到期时间上累加。')" />
    <div class="meta-row">
      <div class="meta-item">
        <span class="meta-label">{{ t('规则ID') }}：</span>
        <span class="meta-value">{{ record?.rule_code || '--' }}</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">{{ t('加白类型') }}：</span>
        <span class="meta-value">{{ record ? t(typeText) : '--' }}</span>
      </div>
    </div>
    <div class="duration-block">
      <div class="field-label is-required">
        {{ t('续期时长') }}
      </div>
      <div
        class="duration-group"
        role="radiogroup">
        <button
          v-for="item in RENEW_DURATION_OPTIONS"
          :key="item.id"
          class="duration-item"
          :class="{ 'is-active': validityMode === item.id }"
          type="button"
          @click="validityMode = item.id">
          {{ t(item.name) }}
        </button>
      </div>
      <bk-date-picker
        v-if="validityMode === 'custom'"
        v-model="customExpire"
        append-to-body
        class="custom-expire"
        :clearable="false"
        data-testid="risk-whitelist-renew-expire"
        :disabled-date="disablePastDate"
        format="yyyy-MM-dd HH:mm:ss"
        :placeholder="t('请选择到期时间')"
        type="datetime" />
      <div class="expire-preview">
        <span>{{ t('续期后到期时间为：') }}</span>
        <strong>{{ nextExpire || '--' }}</strong>
      </div>
      <div
        v-if="customError"
        class="field-error">
        {{ customError }}
      </div>
    </div>
    <div class="remark-field">
      <div class="field-label">
        {{ t('续期说明') }}
      </div>
      <bk-input
        v-model="remark"
        :maxlength="200"
        :placeholder="t('选填，记录本次续期原因')"
        :rows="2"
        type="textarea" />
    </div>
    <template #footer>
      <bk-button
        data-testid="risk-whitelist-renew"
        :loading="loading"
        theme="primary"
        @click="handleSubmit">
        {{ t('确定') }}
      </bk-button>
      <bk-button
        class="ml8"
        @click="isShow = false">
        {{ t('取消') }}
      </bk-button>
    </template>
  </bk-dialog>
</template>
<script setup lang="ts">
  import dayjs from 'dayjs';
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskWhitelistService from '@service/risk-whitelist';

  import type RiskWhitelist from '@model/risk-whitelist/whitelist';
  import type { ValidityMode } from '@model/risk-whitelist/whitelist';

  import useMessage from '@hooks/use-message';

  import { calcExpireAt, RENEW_DURATION_OPTIONS, WHITELIST_TYPE_TEXT } from '@components/risk-whitelist/constants';

  const emit = defineEmits<{(e: 'success', row: RiskWhitelist): void}>();
  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const isShow = ref(false);
  const loading = ref(false);
  const record = ref<RiskWhitelist | null>(null);
  const validityMode = ref<Exclude<ValidityMode, 'permanent'>>('1m');
  const customExpire = ref('');
  const customError = ref('');
  const remark = ref('');

  const typeText = computed(() => (
    record.value ? WHITELIST_TYPE_TEXT[record.value.whitelist_type] : ''
  ));
  const nextExpire = computed(() => {
    if (validityMode.value !== 'custom') return calcExpireAt(validityMode.value);
    if (!customExpire.value || !dayjs(customExpire.value).isValid()) return '';
    return dayjs(customExpire.value).format('YYYY-MM-DD HH:mm:ss');
  });

  const disablePastDate = (date: Date) => dayjs(date).endOf('day').isBefore(dayjs());

  const open = (row: RiskWhitelist) => {
    record.value = row;
    validityMode.value = '1m';
    customExpire.value = '';
    customError.value = '';
    remark.value = '';
    isShow.value = true;
  };

  const reset = () => {
    remark.value = '';
    customError.value = '';
  };

  const handleSubmit = () => {
    if (!record.value) return;
    customError.value = '';
    let customDays: number | undefined;
    let expireAt: string | undefined;
    if (validityMode.value === 'custom') {
      const picked = dayjs(customExpire.value);
      if (!customExpire.value || !picked.isValid() || !picked.isAfter(dayjs())) {
        customError.value = t('请选择晚于当前时间的到期时间');
        return;
      }
      expireAt = picked.format('YYYY-MM-DD HH:mm:ss');
      customDays = Math.max(Math.ceil(picked.diff(dayjs(), 'hour', true) / 24), 1);
    }
    loading.value = true;
    RiskWhitelistService.renew({
      id: record.value.id,
      validity_mode: validityMode.value,
      custom_days: customDays,
      expire_at: expireAt,
      remark: remark.value.trim(),
    }).then((data) => {
      messageSuccess(t('续期成功'));
      isShow.value = false;
      emit('success', data);
    })
      .finally(() => {
        loading.value = false;
      });
  };

  defineExpose({ open });
</script>
<style lang="postcss" scoped>
  .renew-alert :deep(.bk-alert-wraper) {
    padding: 6px 8px;
  }

  .meta-row {
    display: flex;
    gap: 40px;
    justify-content: flex-start;
    margin: 16px 0;
    text-align: left;
  }

  .meta-item {
    display: flex;
    gap: 8px;
    align-items: center;
    padding: 6px 0;
  }

  .meta-label,
  .field-label {
    font-family: var(--audit-font-family);
    font-size: var(--audit-font-size-sm);
    font-style: normal;
    font-weight: var(--audit-font-weight-regular);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-02);
    text-align: left;
  }

  .meta-value {
    font-size: var(--audit-font-size-sm);
    font-style: normal;
    font-weight: var(--audit-font-weight-regular);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-01);
  }

  .duration-block {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .field-label {
    text-align: left;
  }

  .field-label.is-required::after {
    margin-left: 2px;
    color: var(--audit-danger-02);
    content: '*';
  }

  .duration-group {
    display: flex;
    width: 100%;
  }

  .duration-item {
    position: relative;
    flex: 1;
    height: 32px;
    margin-right: -1px;
    font-size: var(--audit-font-size-sm);
    line-height: 20px;
    color: var(--audit-neutral-text-02);
    cursor: pointer;
    background: var(--audit-neutral-bg-04);
    border: 1px solid var(--audit-neutral-text-04);
  }

  .duration-item:first-child {
    border-radius: var(--audit-radius-control) 0 0 var(--audit-radius-control);
  }

  .duration-item:last-child {
    margin-right: 0;
    border-radius: 0 var(--audit-radius-control) var(--audit-radius-control) 0;
  }

  .duration-item.is-active {
    z-index: 1;
    color: var(--audit-brand-02);
    background: var(--audit-brand-06);
    border-color: var(--audit-brand-02);
  }

  .custom-expire {
    width: 100%;
  }

  .expire-preview {
    display: flex;
    align-items: center;
    height: 32px;
    padding: 0 12px;
    font-size: var(--audit-font-size-sm);
    line-height: 20px;
    color: var(--audit-neutral-text-02);
    background: var(--audit-neutral-bg-03);
  }

  .expire-preview strong {
    font-weight: var(--audit-font-weight-bold);
  }

  .remark-field {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 24px;
  }

  .remark-field :deep(textarea) {
    height: 60px;
    min-height: 60px;
  }

  .remark-field :deep(.bk-textarea--max-length) {
    word-spacing: -0.42em;
  }

  .field-error {
    color: var(--audit-danger-02);
  }
</style>
