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
    dialog-type="show"
    :esc-close="false"
    header-align="center"
    :quick-close="false"
    :title="t('确定删除白名单？')"
    width="480">
    <div class="delete-body">
      <div class="desc-row">
        <span class="desc-label">{{ t('规则ID') }}：</span>
        <span class="desc-value">{{ record?.rule_code || '--' }}</span>
      </div>
      <div class="desc-row">
        <span class="desc-label">{{ t('匹配范围') }}：</span>
        <match-scope-expression
          mode="text"
          :scope="record?.match_scope" />
      </div>
      <bk-alert
        class="action-alert"
        theme="warning"
        :title="t(alertText)" />
      <div class="action-buttons">
        <bk-button
          style="width:88px;"
          data-testid="risk-whitelist-delete"
          :loading="loading"
          theme="danger"
          @click="handleSubmit">
          {{ t('删除') }}
        </bk-button>
        <bk-button @click="isShow = false">
          {{ t('取消') }}
        </bk-button>
      </div>
    </div>
  </bk-dialog>
</template>
<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskWhitelistService from '@service/risk-whitelist';

  import type RiskWhitelist from '@model/risk-whitelist/whitelist';

  import useMessage from '@hooks/use-message';

  import MatchScopeExpression from '@components/risk-whitelist/match-scope-expression.vue';

  const DELETE_ALERT = {
    rejected: '删除后，这条已驳回的加白申请会被移除，申请人需要重新提交。',
    expired: '删除后，这条已到期的规则会被移除，历史命中记录一并删除且不可恢复。',
    disabled: '删除后，这条已停用的规则会被移除，历史命中记录一并删除且不可恢复。',
  };

  const emit = defineEmits<{(e: 'success'): void}>();
  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const isShow = ref(false);
  const loading = ref(false);
  const record = ref<RiskWhitelist | null>(null);
  const alertText = computed(() => {
    const status = record.value?.status;
    if (status === 'rejected' || status === 'expired' || status === 'disabled') {
      return DELETE_ALERT[status];
    }
    return DELETE_ALERT.disabled;
  });

  const open = (row: RiskWhitelist) => {
    record.value = row;
    isShow.value = true;
  };

  const handleSubmit = () => {
    if (!record.value) return;
    loading.value = true;
    RiskWhitelistService.remove({ id: record.value.id }).then(() => {
      messageSuccess(t('已删除'));
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
  .delete-body {
    padding: 0 8px;
    font-size: var(--audit-font-size-sm);
    line-height: 20px;
  }

  .desc-row {
    box-sizing: border-box;
    display: flex;
    gap: 8px;
    align-items: flex-start;
    padding: 3px 0;
  }

  .desc-label {
    width: 84px;
    flex-shrink: 0;
    font-family: var(--audit-font-family);
    font-size: var(--audit-font-size-sm);
    font-style: normal;
    font-weight: var(--audit-font-weight-regular);
    line-height: 20px;
    color: var(--audit-neutral-text-02);
    text-align: right;
  }

  .desc-value {
    font-size: var(--audit-font-size-sm);
    font-weight: var(--audit-font-weight-regular);
    line-height: 20px;
    color: var(--audit-neutral-text-01);
  }

  .action-alert {
    margin-top: 16px;
  }

  .action-buttons {
    display: flex;
    gap: 8px;
    justify-content: center;
    margin-top: 24px;
  }
</style>
