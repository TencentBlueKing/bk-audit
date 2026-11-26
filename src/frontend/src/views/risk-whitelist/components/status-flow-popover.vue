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
    :is-show="visible"
    placement="top"
    :popover-delay="0"
    theme="light"
    trigger="manual"
    width="360"
    @after-hidden="handleAfterHidden">
    <span
      class="status-text"
      @mouseenter="handleEnter"
      @mouseleave="handleLeave">
      <i
        class="status-dot"
        :style="{ '--dot-color': dotColor }" />
      <span
        class="status-label"
        :class="{ 'is-link': interactive }">{{ t(label) }}</span>
    </span>
    <template #content>
      <div
        class="flow-popover"
        @mouseenter="handleEnter"
        @mouseleave="handleLeave">
        <div class="flow-title">{{ t('蓝鲸流程服务') }}</div>
        <div
          v-if="loading"
          class="flow-loading">
          {{ t('加载中') }}
        </div>
        <template v-else>
          <div class="flow-row">
            <span class="flow-label">{{ t('ITSM单号') }}</span>
            <span
              v-if="flow.itsm_sn || flow.itsm_url"
              class="jump-cell">
              <span class="jump-text">{{ flow.itsm_sn || '--' }}</span>
              <a
                v-if="flow.itsm_url"
                v-bk-tooltips="{ content: t('打开ITSM单据'), delay: 80 }"
                class="jump-icon"
                :href="flow.itsm_url"
                rel="noopener noreferrer"
                target="_blank">
                <audit-icon type="jump-link" />
              </a>
            </span>
            <span v-else>--</span>
          </div>
          <div class="flow-row">
            <span class="flow-label">{{ t('申请状态') }}</span>
            <span>{{ status === 'rejected' ? t('已驳回') : t('审批中') }}</span>
          </div>
          <div class="flow-row">
            <span class="flow-label">{{ t('当前节点') }}</span>
            <span>{{ flow.current_node || '--' }}</span>
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
        </template>
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
  import {
    computed,
    inject,
    onBeforeUnmount,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type { WhitelistFlow, WhitelistStatus } from '@model/risk-whitelist/whitelist';

  import { STATUS_DOT_TOKEN, WHITELIST_STATUS_TEXT } from '@components/risk-whitelist/constants';

  import { WHITELIST_FLOW_STATE_KEY } from './flow-state';

  /** 模块级单例：快速滑过多行时只保留一个气泡，未驻留不展示 */
  const SHOW_DELAY_MS = 280;
  const HIDE_DELAY_MS = 80;
  let showTimer: ReturnType<typeof setTimeout> | null = null;
  let hideTimer: ReturnType<typeof setTimeout> | null = null;
  const activeKey = ref<string | null>(null);

  const clearTimers = () => {
    if (showTimer) {
      clearTimeout(showTimer);
      showTimer = null;
    }
    if (hideTimer) {
      clearTimeout(hideTimer);
      hideTimer = null;
    }
  };

  interface Props {
    status: WhitelistStatus;
    rowId?: string | number;
    flow?: WhitelistFlow;
    applicant?: string;
    itsmSn?: string;
    itsmUrl?: string;
    loading?: boolean;
  }

  const props = withDefaults(defineProps<Props>(), {
    rowId: undefined,
    flow: undefined,
    applicant: '',
    itsmSn: '',
    itsmUrl: '',
    loading: false,
  });
  const { t } = useI18n();
  const flowState = inject(WHITELIST_FLOW_STATE_KEY, null);

  const interactive = computed(() => props.status === 'pending' || props.status === 'rejected');
  const instanceKey = computed(() => String(props.rowId ?? `${props.status}-${props.applicant}`));
  const visible = computed(() => activeKey.value === instanceKey.value);
  const label = computed(() => WHITELIST_STATUS_TEXT[props.status] || props.status);
  const dotColor = computed(() => STATUS_DOT_TOKEN[props.status] || 'var(--bk-theme-text-weak)');

  const loading = computed(() => {
    if (flowState && props.rowId != null && props.rowId !== '') {
      return flowState.flowLoadingIds.value.has(String(props.rowId));
    }
    return props.loading;
  });

  const emptyFlow = (): WhitelistFlow => ({
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

  const flow = computed(() => {
    const remote = (flowState && props.rowId != null && props.rowId !== '')
      ? flowState.flowMap.value[String(props.rowId)]
      : undefined;
    const local = props.flow;
    if (!remote && !local && !props.itsmSn && !props.itsmUrl) {
      return emptyFlow();
    }
    return {
      itsm_sn: remote?.itsm_sn || local?.itsm_sn || props.itsmSn || '',
      itsm_url: remote?.itsm_url || local?.itsm_url || props.itsmUrl || '',
      apply_status: remote?.apply_status || local?.apply_status || '',
      current_node: remote?.current_node || local?.current_node || '',
      current_approvers: remote?.current_approvers || local?.current_approvers || '',
      applicant: remote?.applicant || local?.applicant || props.applicant || '',
      submitted_at: remote?.submitted_at || local?.submitted_at || '',
      rejector: remote?.rejector || local?.rejector || '',
      reject_reason: remote?.reject_reason || local?.reject_reason || '',
      rejected_at: remote?.rejected_at || local?.rejected_at || '',
    };
  });

  const handleEnter = () => {
    clearTimers();
    showTimer = setTimeout(() => {
      activeKey.value = instanceKey.value;
      showTimer = null;
    }, SHOW_DELAY_MS);
  };

  const handleLeave = () => {
    clearTimers();
    hideTimer = setTimeout(() => {
      if (activeKey.value === instanceKey.value) {
        activeKey.value = null;
      }
      hideTimer = null;
    }, HIDE_DELAY_MS);
  };

  const handleAfterHidden = () => {
    if (activeKey.value === instanceKey.value) {
      activeKey.value = null;
    }
  };

  onBeforeUnmount(() => {
    clearTimers();
    if (activeKey.value === instanceKey.value) {
      activeKey.value = null;
    }
  });
</script>
<style lang="postcss" scoped>
  .status-text {
    display: inline-flex;
    gap: var(--bk-theme-space-4);
    align-items: center;
  }

  .status-label.is-link {
    border-bottom: 1px dashed var(--bk-theme-text-weak);
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
    margin-right: var(--bk-theme-space-4);
  }

  .flow-title {
    margin-bottom: var(--bk-theme-space-8);
    font-weight: var(--bk-theme-font-weight-bold);
  }

  .flow-loading {
    color: var(--bk-theme-text-weak);
    line-height: var(--bk-theme-line-height-base);
  }

  .flow-row {
    display: flex;
    gap: var(--bk-theme-space-8);
    margin-top: var(--bk-theme-space-6);
    line-height: var(--bk-theme-line-height-base);
  }

  .flow-label {
    width: 84px;
    flex-shrink: 0;
    color: var(--bk-theme-text-default);
    text-align: right;
  }

  .jump-cell {
    display: inline-flex;
    gap: var(--bk-theme-space-4);
    align-items: center;
    min-width: 0;
  }

  .jump-text {
    color: var(--bk-theme-text-strong);
  }

  .jump-icon {
    display: inline-flex;
    color: var(--bk-theme-color-brand-2);
  }
</style>
