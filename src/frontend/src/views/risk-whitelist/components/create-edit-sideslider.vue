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
  <audit-sideslider
    v-model:isShow="isShow"
    :quick-close="false"
    show-footer-slot
    :title="isEdit ? '编辑风险白名单' : '新建风险白名单'"
    :width="960">
    <risk-whitelist-form
      ref="formRef"
      :record="record"
      @renew="openRenew" />
    <template #footer>
      <bk-button
        class="footer-action"
        data-testid="risk-whitelist-submit"
        :loading="submitting"
        theme="primary"
        @click="handleSubmit">
        {{ t('提交') }}
      </bk-button>
      <bk-button
        class="footer-action ml8"
        @click="isShow = false">
        {{ t('取消') }}
      </bk-button>
    </template>
  </audit-sideslider>
  <whitelist-confirm-dialog ref="confirmRef" />
  <renew-dialog
    ref="renewRef"
    @success="handleRenewed" />
</template>
<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskWhitelistService from '@service/risk-whitelist';

  import type RiskWhitelist from '@model/risk-whitelist/whitelist';

  import useMessage from '@hooks/use-message';

  import RiskWhitelistForm from '@components/risk-whitelist-form/index.vue';
  import WhitelistConfirmDialog from '@components/whitelist-confirm-dialog/index.vue';

  import RenewDialog from './renew-dialog.vue';

  const emit = defineEmits<{(e: 'success'): void}>();
  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const isShow = ref(false);
  const submitting = ref(false);
  const isEdit = ref(false);
  const record = ref<RiskWhitelist | null>(null);
  const formRef = ref<InstanceType<typeof RiskWhitelistForm>>();
  const confirmRef = ref<InstanceType<typeof WhitelistConfirmDialog>>();
  const renewRef = ref<InstanceType<typeof RenewDialog>>();

  const open = (row?: RiskWhitelist) => {
    record.value = row || null;
    isEdit.value = Boolean(row?.id);
    isShow.value = true;
  };

  const openRenew = () => {
    if (record.value) renewRef.value?.open(record.value);
  };

  const handleRenewed = (row: RiskWhitelist) => {
    formRef.value?.applyRenewed(row.expire_at, row.validity_mode, row.custom_days);
    emit('success');
  };

  const handleSubmit = async () => {
    if (!formRef.value?.validate()) return;
    const payload = formRef.value.getPayload();
    const preview = formRef.value.getValidityPreview();
    const confirmed = await confirmRef.value?.open({
      scope: payload.match_scope,
      whitelistType: payload.whitelist_type,
      validityMode: payload.validity_mode,
      customDays: payload.custom_days,
      expireAt: payload.validity_mode === 'custom'
        ? preview.expireAt
        : (preview.editable ? undefined : preview.expireAt),
      source: 'menu',
    });
    if (!confirmed) return;
    submitting.value = true;
    const request = isEdit.value && record.value
      ? RiskWhitelistService.update({ ...payload, id: record.value.id })
      : RiskWhitelistService.create(payload);
    request.then(() => {
      messageSuccess(t(isEdit.value ? '白名单已更新' : '白名单已生效'));
      isShow.value = false;
      emit('success');
    })
      .finally(() => {
        submitting.value = false;
      });
  };

  defineExpose({ open });
</script>
<style lang="postcss" scoped>
  .footer-action {
    min-width: 88px;
  }
</style>
