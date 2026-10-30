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
    v-if="interactive"
    placement="top"
    theme="light"
    trigger="hover"
    width="360">
    <span class="status-text">
      <i
        class="status-dot"
        :style="{ '--dot-color': dotColor }" />
      <span
        class="status-label"
        :class="{ 'is-link': interactive }">{{ t(label) }}</span>
    </span>
    <template #content>
      <div class="flow-popover">
        <div class="flow-title">{{ t('蓝鲸流程服务') }}</div>
        <div class="flow-row">
          <span class="flow-label">{{ t('ITSM单号') }}</span>
          <a
            v-if="flow.itsm_url"
            class="flow-link"
            :href="flow.itsm_url"
            rel="noopener noreferrer"
            target="_blank">
            {{ flow.itsm_sn || '--' }}
            <audit-icon type="jump-link" />
          </a>
          <span v-else>{{ flow.itsm_sn || '--' }}</span>
        </div>
        <div class="flow-row">
          <span class="flow-label">{{ t('申请状态') }}</span>
          <span>{{ status === 'rejected' ? t('已驳回') : t('审批中') }}</span>
        </div>
        <div class="flow-row">
          <span class="flow-label">{{ t('当前节点') }}</span>
          <span>{{ status === 'rejected' ? t('已结束（驳回）') : (flow.current_node || '--') }}</span>
        </div>
        <div
          v-if="status === 'pending'"
          class="flow-row">
          <span class="flow-label">{{ t('当前审批人') }}</span>
          <span>{{ flow.current_approvers || '--' }}</span>
        </div>
        <template v-else>
          <div class="flow-row">
            <span class="flow-label">{{ t('驳回人') }}</span>
            <span>{{ flow.rejector || '--' }}</span>
          </div>
          <div class="flow-row">
            <span class="flow-label">{{ t('驳回理由') }}</span>
            <span>{{ flow.reject_reason || '--' }}</span>
          </div>
        </template>
        <div class="flow-row">
          <span class="flow-label">{{ t('申请人') }}</span>
          <span>{{ flow.applicant || applicant || '--' }}</span>
        </div>
        <div class="flow-row">
          <span class="flow-label">{{ t('提交时间') }}</span>
          <span>{{ flow.submitted_at || '--' }}</span>
        </div>
      </div>
    </template>
  </bk-popover>
  <span
    v-else
    class="status-text">
    <i
      class="status-dot"
      :style="{ '--dot-color': dotColor }" />
    <span class="status-label">{{ t(label) }}</span>
  </span>
</template>
<script setup lang="ts">
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type { WhitelistFlow, WhitelistStatus } from '@model/risk-whitelist/whitelist';

  import { STATUS_DOT_TOKEN, WHITELIST_STATUS_TEXT } from '@components/risk-whitelist/constants';

  interface Props {
    status: WhitelistStatus;
    flow?: WhitelistFlow;
    applicant?: string;
  }

  const props = withDefaults(defineProps<Props>(), {
    flow: undefined,
    applicant: '',
  });
  const { t } = useI18n();
  const interactive = computed(() => props.status === 'pending' || props.status === 'rejected');
  const label = computed(() => WHITELIST_STATUS_TEXT[props.status] || props.status);
  const dotColor = computed(() => STATUS_DOT_TOKEN[props.status] || 'var(--audit-neutral-text-03)');
  const flow = computed(() => props.flow || {
    itsm_sn: '',
    itsm_url: '',
    apply_status: '',
    current_node: '',
    current_approvers: '',
    applicant: '',
    submitted_at: '',
    rejector: '',
    reject_reason: '',
    rejected_at: '',
  });
</script>
<style lang="postcss" scoped>
  .status-text {
    display: inline-flex;
    gap: 4px;
    align-items: center;
  }

  .status-label.is-link {
    border-bottom: 1px dashed var(--audit-neutral-text-03);
    cursor: pointer;
  }

  .status-dot {
    display: inline-block;
    flex-shrink: 0;
    width: 6px;
    height: 6px;
    background: var(--dot-color);
    border-radius: 50%;
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--dot-color) 24%, transparent);
    margin-right: 4px;
  }

  .flow-title {
    margin-bottom: 8px;
    font-weight: var(--audit-font-weight-bold);
  }

  .flow-row {
    display: flex;
    gap: 8px;
    margin-top: 6px;
    line-height: var(--audit-line-height-base);
  }

  .flow-label {
    width: 84px;
    flex-shrink: 0;
    color: var(--audit-neutral-text-02);
    text-align: right;
  }

  .flow-link {
    color: var(--audit-brand-02);
  }
</style>
