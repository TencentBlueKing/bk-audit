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
    :show-footer="false"
    show-header-slot
    :width="960">
    <template #header>
      <div class="hit-header">
        <span>{{ t('命中记录') }}</span>
        <span class="hit-split" />
        <span>{{ ruleCode }}</span>
      </div>
    </template>
    <div class="hit-body">
      <bk-search-select
        v-model="searchValue"
        class="hit-search"
        clearable
        :data="searchData"
        :placeholder="t('拦截动作、匹配范围、包含条件、关联风险单')"
        unique-select
        @update:model-value="handleSearch" />
      <tdesign-list
        ref="listRef"
        :columns="columns"
        :data-source="dataSource"
        disable-url-sync
        :persist-table-filters="false"
        row-key="id" />
    </div>
  </audit-sideslider>
  <event-detail-dialog ref="eventRef" />
</template>
<script setup lang="tsx">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskWhitelistService from '@service/risk-whitelist';

  import type { HitRecord } from '@model/risk-whitelist/whitelist';

  import MatchScopeExpression from '@components/risk-whitelist/match-scope-expression.vue';
  import { INTERCEPT_ACTION_TEXT } from '@components/risk-whitelist/constants';
  import TdesignList from '@components/tdesign-list/index.vue';

  import EventDetailDialog from './event-detail-dialog.vue';

  interface SearchKey {
    id: string;
    name: string;
    values?: Array<{ id: string; name: string }>;
  }

  const { t } = useI18n();
  const isShow = ref(false);
  const ruleId = ref<number | string>('');
  const ruleCode = ref('');
  const searchValue = ref<SearchKey[]>([]);
  const listRef = ref<InstanceType<typeof TdesignList>>();
  const eventRef = ref<InstanceType<typeof EventDetailDialog>>();

  const searchData = [
    { id: 'action', name: t('拦截动作'), children: [
      { id: 'suppress_new', name: t('抑制新单产生') },
      { id: 'suppress_append', name: t('抑制追加事件') },
    ] },
    { id: 'match_scope', name: t('匹配范围') },
    { id: 'condition_keyword', name: t('包含条件') },
    { id: 'risk_id', name: t('关联风险单') },
  ];

  const columns = [
    { title: t('命中时间'), colKey: 'hit_time', width: 180 },
    {
      title: t('拦截动作'),
      colKey: 'action',
      width: 140,
      cell: (_: unknown, { row }: { row: HitRecord }) => t(INTERCEPT_ACTION_TEXT[row.action] || row.action),
    },
    {
      title: t('匹配范围'),
      colKey: 'match_scope',
      minWidth: 280,
      cell: (_: unknown, { row }: { row: HitRecord }) => (
        <div class="scope-cell">
          <MatchScopeExpression mode="tag" scope={row.match_scope} />
        </div>
      ),
    },
    {
      title: t('关联风险单'),
      colKey: 'risk_id',
      width: 160,
      cell: (_: unknown, { row }: { row: HitRecord }) => {
        if (row.action === 'suppress_new' || !row.risk_id) return '-';
        if (!row.risk_url) return row.risk_id;
        return (
          <span class="risk-cell">
            <span class="risk-text">{row.risk_id}</span>
            <a class="risk-link" href={row.risk_url} target="_blank" rel="noopener noreferrer">
              <audit-icon class="risk-link-icon" type="jump-link" />
            </a>
          </span>
        );
      },
    },
    {
      title: t('操作'),
      colKey: 'action_ops',
      width: 100,
      fixed: 'right',
      cell: (_: unknown, { row }: { row: HitRecord }) => (
        <bk-button text theme="primary" onClick={() => eventRef.value?.open(row.id)}>
          {t('事件详情')}
        </bk-button>
      ),
    },
  ];

  const buildParams = (values: SearchKey[]) => {
    const params: Record<string, string> = {};
    values.forEach((item) => {
      const value = item.values?.map(child => child.id).filter(Boolean).join(',');
      if (value) params[item.id] = value;
    });
    return params;
  };

  const dataSource = (params: Record<string, any>) => RiskWhitelistService.fetchHitRecords({
    ...params,
    ...buildParams(searchValue.value),
    id: ruleId.value,
  });

  const handleSearch = () => {
    listRef.value?.fetchData(buildParams(searchValue.value));
  };

  const open = (id: number | string, code: string) => {
    ruleId.value = id;
    ruleCode.value = code;
    searchValue.value = [];
    isShow.value = true;
  };

  defineExpose({ open });
</script>
<style lang="postcss" scoped>
  .hit-header {
    display: flex;
    gap: var(--bk-theme-space-8);
    align-items: center;
  }

  .hit-split {
    width: 1px;
    height: 14px;
    background: var(--bk-theme-border-default);
  }

  .hit-body {
    padding: var(--bk-theme-space-16) var(--bk-theme-space-24) var(--bk-theme-space-24);
  }

  .hit-search {
    display: block;
    width: 100%;
    margin-bottom: var(--bk-theme-space-16);
  }

  :deep(td:has(.scope-cell)) {
    height: auto;
    padding: var(--bk-theme-space-8);
  }

  :deep(.scope-cell) {
    max-width: 100%;
    min-width: 0;
    overflow: hidden;
  }

  :deep(.risk-cell) {
    display: inline-flex;
    gap: var(--bk-theme-space-4);
    align-items: center;
    max-width: 100%;
  }

  :deep(.risk-text) {
    color: var(--bk-theme-text-strong);
  }

  :deep(.risk-link) {
    display: inline-flex;
    color: var(--bk-theme-color-brand-2);
  }

  :deep(.risk-link-icon) {
    visibility: hidden;
  }

  :deep(tr:hover .risk-link-icon) {
    visibility: visible;
  }
</style>
