<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
-->
<template>
  <div
    v-if="record"
    class="whitelist-apply">
    <bk-alert
      v-if="isPending"
      class="whitelist-apply__alert"
      theme="info"
      :title="t(pendingAlertTitle)" />
    <div class="whitelist-apply__card">
      <div class="whitelist-apply__row">
        <span class="whitelist-apply__label">{{ t('匹配范围') }}</span>
        <match-scope-expression
          inline
          :scope="record.scope" />
      </div>
      <div
        v-if="showItsm"
        class="whitelist-apply__row">
        <span class="whitelist-apply__label">{{ t('ITSM单号') }}</span>
        <span
          v-if="record.itsmSn || record.itsmUrl"
          class="jump-cell">
          <span class="jump-text">{{ record.itsmSn || '--' }}</span>
          <a
            v-if="record.itsmUrl"
            v-bk-tooltips="{ content: t('打开ITSM单据'), delay: 80 }"
            class="jump-icon"
            :href="record.itsmUrl"
            rel="noopener noreferrer"
            target="_blank">
            <audit-icon type="jump-link" />
          </a>
        </span>
        <span v-else>--</span>
      </div>
      <div class="whitelist-apply__row">
        <span class="whitelist-apply__label">{{ t('申请状态') }}</span>
        <span class="whitelist-apply__status">
          <audit-icon
            v-if="statusVisual.showIcon"
            :class="{ 'rotate-loading': statusVisual.icon === 'loading' }"
            :style="{ color: statusVisual.color }"
            :svg="statusVisual.svg"
            :type="statusVisual.icon" />
          <span>{{ statusKind === 'other' ? statusText : t(statusText) }}</span>
        </span>
      </div>
      <div
        v-if="showCurrentNode"
        class="whitelist-apply__row">
        <span class="whitelist-apply__label">{{ t('当前节点') }}</span>
        <span>{{ record.currentNode || '--' }}</span>
      </div>
      <div
        v-if="isPending"
        class="whitelist-apply__row">
        <span class="whitelist-apply__label">{{ t('当前审批人') }}</span>
        <span>{{ record.approvers || '--' }}</span>
      </div>
      <template v-if="isRejected">
        <div class="whitelist-apply__row">
          <span class="whitelist-apply__label">{{ t('驳回人') }}</span>
          <span>{{ record.rejector || '--' }}</span>
        </div>
        <div class="whitelist-apply__row">
          <span class="whitelist-apply__label">{{ t('驳回理由') }}</span>
          <span>{{ record.rejectReason || '--' }}</span>
        </div>
        <div class="whitelist-apply__row">
          <span class="whitelist-apply__label">{{ t('驳回时间') }}</span>
          <span>{{ record.rejectedAt || '--' }}</span>
        </div>
      </template>
      <div class="whitelist-apply__row">
        <span class="whitelist-apply__label">{{ t('申请人') }}</span>
        <span>{{ record.applicant || '--' }}</span>
      </div>
      <div class="whitelist-apply__row">
        <span class="whitelist-apply__label">{{ t('加白类型') }}</span>
        <span>{{ t(record.typeLabel) }}</span>
      </div>
      <div class="whitelist-apply__row">
        <span class="whitelist-apply__label">{{ t('有效期') }}</span>
        <span>{{ record.validityText || '--' }}</span>
      </div>
      <div class="whitelist-apply__row">
        <span class="whitelist-apply__label">{{ t('加白原因') }}</span>
        <span>{{ record.reason || '--' }}</span>
      </div>
      <div class="whitelist-apply__row">
        <span class="whitelist-apply__label">{{ t('规则ID') }}</span>
        <span>{{ record.ruleId || '--' }}</span>
      </div>
      <div class="whitelist-apply__row">
        <span class="whitelist-apply__label">{{ t('提交时间') }}</span>
        <span>{{ record.submittedAt || '--' }}</span>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type { CompareOperator, MatchScope } from '@model/risk-whitelist/whitelist';

  import MatchScopeExpression from '@components/risk-whitelist/match-scope-expression.vue';

  interface HistoryItem {
    action?: string;
    operator?: string;
    time?: string;
    description?: string;
    whitelist?: Record<string, any>;
    process_result?: Record<string, any>;
    [key: string]: any;
  }

  interface Props {
    data: HistoryItem;
  }

  const props = defineProps<Props>();
  const { t } = useI18n();

  const raw = computed(() => props.data.whitelist || props.data.extra || props.data);
  const ticket = computed(() => {
    const source = raw.value || {};
    return source.process_result?.ticket
      || props.data.process_result?.ticket
      || {};
  });

  const joinNames = (list: unknown): string => {
    if (!Array.isArray(list)) return '';
    return list
      .flatMap((item) => {
        if (item && typeof item === 'object') {
          const named = item as Record<string, any>;
          const processor = named.processor;
          if (Array.isArray(processor)) {
            return processor.map(String);
          }
          if (processor !== undefined && processor !== null && String(processor).trim() !== '') {
            return [String(processor)];
          }
          const label = named.name || named.display_name || named.username || named.id || '';
          return label ? [String(label)] : [];
        }
        return item !== undefined && item !== null && String(item).trim() !== ''
          ? [String(item)]
          : [];
      })
      .join(', ');
  };

  const normalizeScope = (value: any): MatchScope => {
    const groups = value?.groups || value?.match_scope?.groups;
    if (!Array.isArray(groups) || !groups.length) {
      return { groups: [] };
    }
    return {
      groups: groups.map((group: any) => ({
        connector: group.connector || group.logic || 'and',
        conditions: (group.conditions || group.rows || []).map((row: any) => ({
          field: row.field,
          field_name: row.field_name || row.field,
          field_label: row.field_label || row.field,
          operator: (row.operator === 'ne' ? 'neq' : row.operator || 'eq') as CompareOperator,
          value: row.value || '',
          value_display: row.value_display || row.value_label || row.value || '',
          connector: row.connector || 'and',
        })),
      })),
    };
  };

  const record = computed(() => {
    const source = raw.value || {};
    const ticketInfo = ticket.value || {};
    const scopeSource = source.match_scope || source.scope || source;
    const status = source.itsm_status
      || ticketInfo.status
      || source.apply_status
      || source.status
      || 'pending';
    const statusDisplay = source.itsm_status_display || ticketInfo.status_display || '';
    const type = source.whitelist_type || source.whitelistType;
    return {
      scope: normalizeScope(scopeSource),
      itsmSn: source.itsm_sn || ticketInfo.sn || source.sn,
      itsmUrl: source.itsm_url
        || ticketInfo.frontend_url
        || ticketInfo.ticket_url
        || source.ticket_url,
      currentNode: joinNames(source.current_steps)
        || joinNames(ticketInfo.current_steps)
        || source.current_node
        || source.currentNode
        || '',
      approvers: joinNames(source.current_processors)
        || joinNames(ticketInfo.current_processors)
        || (Array.isArray(source.current_approvers)
          ? source.current_approvers.join(', ')
          : (source.current_approver || source.approvers || '')),
      applicant: source.applicant || source.operator || props.data.operator,
      typeLabel: type === 'risk_acceptance' || type === 'adventure' ? '冒险加白' : '误报加白',
      whitelistType: type === 'risk_acceptance' || type === 'adventure' ? 'risk_acceptance' : 'false_positive',
      validityText: source.validity_text || source.validity || source.expire_text,
      reason: source.reason || source.description || props.data.description,
      ruleId: source.rule_id || source.rule_code || source.ruleId,
      submittedAt: source.submitted_at || source.submit_time || props.data.time,
      rejector: source.rejector || source.rejected_by,
      rejectReason: source.reject_reason,
      rejectedAt: source.rejected_at,
      status,
      statusDisplay,
    };
  });

  const pendingAlertTitle = computed(() => (
    record.value.whitelistType === 'false_positive'
      ? '加白申请已提交至蓝鲸流程服务，当前风险单已按误报关闭；场景管理员审批通过后规则生效。'
      : '加白申请已提交至蓝鲸流程服务，场景管理员审批通过后规则生效并关单。'
  ));

  const PENDING_STATUS = ['pending', 'approving', 'pending_approve', '审批中', '待审批'];
  const REJECTED_STATUS = ['rejected', '已驳回'];
  const APPROVED_STATUS = ['approved', 'passed', 'active', '已通过', '生效中'];

  const statusKind = computed(() => {
    const status = String(record.value.status ?? '');
    const display = String(record.value.statusDisplay ?? '');
    if (PENDING_STATUS.includes(status) || PENDING_STATUS.includes(display)) return 'pending';
    if (REJECTED_STATUS.includes(status) || REJECTED_STATUS.includes(display)) return 'rejected';
    if (APPROVED_STATUS.includes(status) || APPROVED_STATUS.includes(display)) return 'approved';
    return 'other';
  });
  const isPending = computed(() => statusKind.value === 'pending');
  const isRejected = computed(() => statusKind.value === 'rejected');
  const statusText = computed(() => {
    if (isPending.value) return '审批中';
    if (isRejected.value) return '已驳回';
    if (statusKind.value === 'approved') return '已通过';
    const display = String(record.value.statusDisplay ?? '').trim();
    if (display) return display;
    const rawStatus = String(record.value.status ?? '').trim();
    return rawStatus || '--';
  });
  /** 与风险详情「执行前审批 / 任务状态」一致：icon + 色值区分审批结果 */
  const statusVisual = computed(() => {
    if (statusKind.value === 'pending') {
      return {
        showIcon: true,
        icon: 'loading',
        color: 'var(--bk-theme-color-brand-2)',
        svg: true,
      };
    }
    if (statusKind.value === 'approved') {
      return {
        showIcon: true,
        icon: 'completed',
        color: 'var(--bk-theme-color-success-2)',
        svg: true,
      };
    }
    if (statusKind.value === 'rejected') {
      return {
        showIcon: true,
        icon: 'delete-fill',
        color: 'var(--bk-theme-color-danger-2)',
        svg: false,
      };
    }
    return {
      showIcon: false,
      icon: '',
      color: '',
      svg: false,
    };
  });
  const hasText = (value: unknown) => value !== undefined && value !== null && String(value).trim() !== '';
  const showItsm = computed(() => (
    hasText(record.value.itsmSn)
    || hasText(record.value.itsmUrl)
    || isPending.value
    || isRejected.value
  ));
  const showCurrentNode = computed(() => (
    hasText(record.value.currentNode)
    || isPending.value
    || isRejected.value
  ));
</script>
<style lang="postcss" scoped>
.whitelist-apply {
  display: flex;
  flex-direction: column;
  gap: var(--bk-theme-space-8);
}

.whitelist-apply__card {
  padding: var(--bk-theme-space-8) var(--bk-theme-space-12);
  background: var(--bk-theme-surface-page);
  border-radius: var(--bk-theme-card-radius);
}

.whitelist-apply__row {
  display: flex;
  gap: var(--bk-theme-space-8);
  align-items: flex-start;
  padding: var(--bk-theme-space-4) 0;
  font-size: var(--bk-theme-font-size-sm);
  line-height: var(--bk-theme-line-height-sm);
  color: var(--bk-theme-text-strong);
}

.whitelist-apply__label {
  flex: 0 0 84px;
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

.whitelist-apply__status {
  display: inline-flex;
  gap: var(--bk-theme-space-4);
  align-items: center;
}

.rotate-loading {
  animation: whitelist-spin 1s linear infinite;
}

@keyframes whitelist-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
