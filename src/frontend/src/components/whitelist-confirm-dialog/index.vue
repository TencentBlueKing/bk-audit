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
    class="whitelist-confirm-dialog"
    :esc-close="false"
    header-align="center"
    :quick-close="false"
    :title="t(roleText.text.value.confirmTitle)"
    width="480">
    <div class="confirm-body">
      <div class="desc-row">
        <span class="desc-label">{{ t('匹配范围') }}：</span>
        <match-scope-expression
          mode="text"
          :scope="scope" />
      </div>
      <div class="desc-row">
        <span class="desc-label">{{ t('加白类型') }}：</span>
        <span class="desc-text">{{ t(typeText) }}</span>
      </div>
      <div class="desc-row">
        <span class="desc-label">{{ t('有效期') }}：</span>
        <span class="desc-text">{{ validityText }}</span>
      </div>
      <div class="impact-box">
        <ul>
          <li
            v-for="item in impacts"
            :key="item">
            {{ t(item) }}
          </li>
        </ul>
      </div>
    </div>
    <template #footer>
      <bk-button
        data-testid="risk-whitelist-confirm"
        theme="primary"
        @click="handleConfirm">
        {{ t(roleText.text.value.confirmOk) }}
      </bk-button>
      <bk-button
        class="ml8"
        @click="handleCancel">
        {{ t('取消') }}
      </bk-button>
    </template>
  </bk-dialog>
</template>
<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type { MatchScope, ValidityMode, WhitelistType } from '@model/risk-whitelist/whitelist';

  import useWhitelistRoleText from '@hooks/use-whitelist-role-text';

  import MatchScopeExpression from '@components/risk-whitelist/match-scope-expression.vue';
  import {
    durationLabel,
    hasStrategyOnlyGroup,
    WHITELIST_TYPE_TEXT,
  } from '@components/risk-whitelist/constants';

  interface OpenOptions {
    scope: MatchScope;
    whitelistType: WhitelistType;
    validityMode?: ValidityMode;
    customDays?: number;
    source?: 'menu' | 'risk';
    expireAt?: string;
  }

  const { t } = useI18n();
  const roleText = useWhitelistRoleText();
  const { isAdmin } = roleText;
  const isShow = ref(false);
  const scope = ref<MatchScope>({ groups: [] });
  const whitelistType = ref<WhitelistType>('false_positive');
  const validityMode = ref<ValidityMode>('permanent');
  const customDays = ref(1);
  const source = ref<'menu' | 'risk'>('menu');
  const expireAt = ref<string | null>(null);
  let resolver: ((value: boolean) => void) | null = null;

  const typeText = computed(() => WHITELIST_TYPE_TEXT[whitelistType.value]);
  const validityText = computed(() => {
    if (expireAt.value !== null) return expireAt.value || '--';
    return validityMode.value === 'permanent'
      ? t('永久生效')
      : durationLabel(validityMode.value, customDays.value);
  });

  const impacts = computed(() => {
    const lines: string[] = [];
    if (!isAdmin.value) {
      lines.push(roleText.text.value.applyHint);
    }
    if (source.value === 'risk') {
      lines.push(isAdmin.value ? '当前风险单将关闭。' : '审批通过后当前风险单将关闭。');
    }
    if (isAdmin.value || source.value === 'menu') {
      lines.push('白名单立即生效。后续命中该匹配范围的风险将不再生成新单，已有风险单不再追加事件。');
    } else {
      lines.push('审批通过后白名单生效。后续命中该匹配范围的风险将不再生成新单，已有风险单不再追加事件。');
    }
    if (whitelistType.value === 'false_positive') {
      lines.push('误报加白用于检测不准的情况，命中后不再作为风险处理。');
    }
    if (whitelistType.value === 'risk_acceptance') {
      lines.push('冒险加白表示风险真实存在，可能带来安全风险。因冒险加白导致重大安全事故的，申请人需承担主要责任，请谨慎操作。');
    }
    if (hasStrategyOnlyGroup(scope.value)) {
      lines.push('当前存在只锁定整条策略的条件组，命中该策略的风险都会被抑制。');
    }
    return lines;
  });

  const open = (options: OpenOptions) => {
    scope.value = options.scope;
    whitelistType.value = options.whitelistType;
    validityMode.value = options.validityMode || 'permanent';
    customDays.value = options.customDays || 1;
    source.value = options.source || 'menu';
    expireAt.value = options.expireAt === undefined ? null : options.expireAt;
    isShow.value = true;
    return new Promise<boolean>((resolve) => {
      resolver = resolve;
    });
  };

  const finish = (confirmed: boolean) => {
    isShow.value = false;
    resolver?.(confirmed);
    resolver = null;
  };

  const handleConfirm = () => finish(true);
  const handleCancel = () => finish(false);

  defineExpose({ open });
</script>
<style lang="postcss" scoped>
  .confirm-body {
    text-align: left;
  }

  .desc-row {
    display: flex;
    gap: 12px;
    margin-bottom: 8px;
    font-size: var(--audit-font-size-base);
    line-height: var(--audit-line-height-base);
  }

  .desc-label {
    width: 84px;
    flex-shrink: 0;
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-02);
    text-align: right;
  }
  .desc-text {
    color: var(--audit-neutral-text-01);
    font-size: var(--audit-font-size-sm);
  }
  .impact-box {
    padding: 8px 6px;
    margin-top: 12px;
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-02);
    background: var(--audit-neutral-bg-01);
    border-radius: var(--audit-radius-control);
  }

  .impact-box ul {
    padding: 0;
    margin: 0;
  }

  .impact-box li {
    margin-left: 18px;
    list-style: disc;
  }
</style>
