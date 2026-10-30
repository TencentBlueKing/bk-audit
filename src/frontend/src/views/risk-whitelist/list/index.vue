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
  <div class="risk-whitelist-page">
    <div class="page-toolbar">
      <bk-button
        class="risk-whitelist-create"
        theme="primary"
        @click="openCreate">
        <audit-icon
          class="mr4"
          type="add" />
        {{ t('新建白名单') }}
      </bk-button>
      <bk-search-select
        v-model="searchValue"
        class="page-search"
        clearable
        :data="searchData"
        :placeholder="t('规则标识、匹配范围、包含条件、加白类型、加白原因、更新人')"
        unique-select
        @update:model-value="handleSearch" />
    </div>
    <tdesign-list
      ref="listRef"
      :columns="columns"
      :data-source="dataSource"
      is-need-scene-id
      row-key="id"
      scene-id-key="scene_id"
      @clear-search="handleClearSearch">
      <template #empty>
        <div
          class="list-empty"
          data-testid="risk-whitelist-empty">
          {{ t(hasSearch ? '搜索结果为空' : '暂无风险白名单') }}
        </div>
      </template>
    </tdesign-list>
    <create-edit-sideslider
      ref="editRef"
      @success="refresh" />
    <reject-dialog
      ref="rejectRef"
      @success="refresh" />
    <renew-dialog
      ref="renewRef"
      @success="refresh" />
    <toggle-dialog
      ref="toggleRef"
      @success="refresh" />
    <delete-dialog
      ref="deleteRef"
      @success="refresh" />
    <hit-record-sideslider ref="hitRef" />
  </div>
</template>
<script setup lang="tsx">
  import { onMounted, onUnmounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskWhitelistService from '@service/risk-whitelist';

  import type RiskWhitelist from '@model/risk-whitelist/whitelist';

  import useEventBus from '@hooks/use-event-bus';
  import useMessage from '@hooks/use-message';

  import MatchScopeExpression from '@components/risk-whitelist/match-scope-expression.vue';
  import { WHITELIST_STATUS_TEXT, WHITELIST_TYPE_TEXT } from '@components/risk-whitelist/constants';
  import TdesignList from '@components/tdesign-list/index.vue';

  import CreateEditSideslider from '../components/create-edit-sideslider.vue';
  import DeleteDialog from '../components/delete-dialog.vue';
  import HitRecordSideslider from '../components/hit-record-sideslider.vue';
  import RejectDialog from '../components/reject-dialog.vue';
  import RenewDialog from '../components/renew-dialog.vue';
  import StatusFlowPopover from '../components/status-flow-popover.vue';
  import ToggleDialog from '../components/toggle-dialog.vue';

  interface SearchKey {
    id: string;
    name: string;
    values?: Array<{ id: string; name: string }>;
  }

  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const { on: onEvent, off } = useEventBus();
  const listRef = ref<InstanceType<typeof TdesignList>>();
  const editRef = ref<InstanceType<typeof CreateEditSideslider>>();
  const rejectRef = ref<InstanceType<typeof RejectDialog>>();
  const renewRef = ref<InstanceType<typeof RenewDialog>>();
  const toggleRef = ref<InstanceType<typeof ToggleDialog>>();
  const deleteRef = ref<InstanceType<typeof DeleteDialog>>();
  const hitRef = ref<InstanceType<typeof HitRecordSideslider>>();
  const searchValue = ref<SearchKey[]>([]);
  const hasSearch = ref(false);

  const searchData = [
    { id: 'rule_code', name: t('规则标识') },
    { id: 'match_scope', name: t('匹配范围') },
    { id: 'condition_keyword', name: t('包含条件') },
    {
      id: 'whitelist_type',
      name: t('加白类型'),
      children: [
        { id: 'false_positive', name: t('误报加白') },
        { id: 'risk_acceptance', name: t('冒险加白') },
      ],
    },
    { id: 'reason', name: t('加白原因') },
    { id: 'updated_by', name: t('更新人') },
    {
      id: 'status',
      name: t('状态'),
      children: Object.entries(WHITELIST_STATUS_TEXT).map(([id, name]) => ({ id, name: t(name) })),
    },
  ];

  const filterList = (map: Record<string, string>) => Object.entries(map).map(([value, label]) => ({
    label: t(label),
    value,
  }));

  const openHit = (row: RiskWhitelist) => {
    if (!row.hit_count) return;
    hitRef.value?.open(row.id, row.rule_code);
  };

  const approvingIds = ref(new Set<number | string>());

  const approve = (row: RiskWhitelist) => {
    if (approvingIds.value.has(row.id)) return;
    approvingIds.value = new Set(approvingIds.value).add(row.id);
    RiskWhitelistService.approve({ id: row.id }).then(() => {
      messageSuccess(t('已通过，白名单生效并关闭关联风险单'));
      refresh();
    })
      .finally(() => {
        const next = new Set(approvingIds.value);
        next.delete(row.id);
        approvingIds.value = next;
      });
  };

  const renderMore = (items: Array<{ label: string; onClick: () => void }>) => (
    <bk-dropdown trigger="click">
      {{
        default: () => (
          <button
            class="more-trigger"
            title={t('更多')}
            type="button">
            <audit-icon type="more" />
          </button>
        ),
        content: () => (
          <bk-dropdown-menu>
            {items.map(item => (
              <bk-dropdown-item onClick={item.onClick}>{item.label}</bk-dropdown-item>
            ))}
          </bk-dropdown-menu>
        ),
      }}
    </bk-dropdown>
  );

  const renderActions = (row: RiskWhitelist) => {
    const edit = <bk-button text theme="primary" onClick={() => editRef.value?.open(row)}>{t('编辑')}</bk-button>;
    const renew = <bk-button text theme="primary" onClick={() => renewRef.value?.open(row)}>{t('续期')}</bk-button>;
    const hit = { label: t('命中记录'), onClick: () => hitRef.value?.open(row.id, row.rule_code) };
    const remove = { label: t('删除'), onClick: () => deleteRef.value?.open(row) };
    if (row.status === 'pending') {
      return (
        <div class="row-actions">
          <bk-button
            disabled={approvingIds.value.has(row.id)}
            loading={approvingIds.value.has(row.id)}
            text
            theme="primary"
            onClick={() => approve(row)}>
            {t('通过')}
          </bk-button>
          <bk-button text theme="primary" onClick={() => rejectRef.value?.open(row)}>{t('驳回')}</bk-button>
        </div>
      );
    }
    if (row.status === 'active') {
      const more = [hit];
      if (!row.is_permanent) more.unshift({ label: t('续期'), onClick: () => renewRef.value?.open(row) });
      return (
        <div class="row-actions">
          {edit}
          <bk-button text theme="primary" onClick={() => toggleRef.value?.open(row, false)}>{t('停用')}</bk-button>
          {renderMore(more)}
        </div>
      );
    }
    if (row.status === 'disabled') {
      return (
        <div class="row-actions">
          <bk-button text theme="primary" onClick={() => toggleRef.value?.open(row, true)}>{t('启用')}</bk-button>
          {renderMore([hit, remove])}
        </div>
      );
    }
    if (row.status === 'expired') {
      return (
        <div class="row-actions">
          {edit}
          {renew}
          {renderMore([hit, remove])}
        </div>
      );
    }
    return (
      <div class="row-actions">
        <bk-button text theme="primary" onClick={() => deleteRef.value?.open(row)}>{t('删除')}</bk-button>
      </div>
    );
  };

  const columns = [
    {
      title: t('规则标识'),
      colKey: 'rule_code',
      width: 128,
      minWidth: 128,
      sorter: true,
    },
    {
      title: t('匹配范围'),
      colKey: 'match_scope',
      width: 350,
      cell: (_: unknown, { row }: { row: RiskWhitelist }) => (
        <div class="scope-cell">
          <MatchScopeExpression mode="tag" scope={row.match_scope} />
        </div>
      ),
    },
    {
      title: t('加白类型'),
      colKey: 'whitelist_type',
      width: 124,
      minWidth: 124,
      filter: {
        type: 'multiple',
        resetValue: [],
        showConfirmAndReset: true,
        list: filterList(WHITELIST_TYPE_TEXT),
      },
      cell: (_: unknown, { row }: { row: RiskWhitelist }) => t(WHITELIST_TYPE_TEXT[row.whitelist_type]),
    },
    {
      title: t('到期时间'),
      colKey: 'expire_at',
      width: 180,
      minWidth: 180,
      sorter: true,
      cell: (_: unknown, { row }: { row: RiskWhitelist }) => (
        <span class="expire-cell">{row.is_permanent ? t('永久') : (row.expire_at || '--')}</span>
      ),
    },
    {
      title: t('状态'),
      colKey: 'status',
      width: 90,
      filter: {
        type: 'multiple',
        resetValue: [],
        showConfirmAndReset: true,
        list: filterList(WHITELIST_STATUS_TEXT),
      },
      cell: (_: unknown, { row }: { row: RiskWhitelist }) => (
        <StatusFlowPopover applicant={row.applicant} flow={row.flow} status={row.status} />
      ),
    },
    {
      title: t('加白原因'),
      colKey: 'reason',
      width: 161,
      ellipsis: true,
    },
    {
      title: t('命中次数'),
      colKey: 'hit_count',
      width: 115,
      sorter: true,
      cell: (_: unknown, { row }: { row: RiskWhitelist }) => (
        row.hit_count > 0
          ? <bk-button text theme="primary" onClick={() => openHit(row)}>{row.hit_count}</bk-button>
          : <span class="hit-zero">{row.hit_count}</span>
      ),
    },
    { title: t('更新人'), colKey: 'updated_by', width: 103, ellipsis: true },
    { title: t('更新时间'), colKey: 'updated_at', width: 180, minWidth: 180, sorter: true },
    {
      title: t('操作'),
      colKey: 'action',
      width: 136,
      fixed: 'right',
      cell: (_: unknown, { row }: { row: RiskWhitelist }) => renderActions(row),
    },
  ];

  const buildSearchParams = () => {
    const params: Record<string, string> = {};
    searchValue.value.forEach((item) => {
      const value = item.values?.map(child => child.id).filter(Boolean).join(',');
      if (value) params[item.id] = value;
    });
    return params;
  };

  const dataSource = (params: Record<string, any>) => {
    const search = buildSearchParams();
    hasSearch.value = Object.keys(search).length > 0 || Object.keys(params).some(key => (
      !['page', 'page_size', 'sort', 'scene_id', 'scope_id'].includes(key) && params[key]
    ));
    return RiskWhitelistService.fetchList({
      ...params,
      ...search,
    });
  };

  const handleSearch = () => {
    listRef.value?.fetchData(buildSearchParams());
  };

  const handleClearSearch = () => {
    searchValue.value = [];
    hasSearch.value = false;
    listRef.value?.fetchData({});
  };

  const refresh = () => {
    listRef.value?.fetchData(buildSearchParams());
  };

  const openCreate = () => editRef.value?.open();

  const handleSceneChange = () => refresh();

  onMounted(() => {
    setTimeout(() => {
      onEvent('scene:change', handleSceneChange);
    }, 1000);
  });

  onUnmounted(() => {
    off('scene:change', handleSceneChange);
  });
</script>
<style lang="postcss" scoped>
  .risk-whitelist-page {
    padding: 24px;
    background: var(--audit-neutral-bg-04);
  }

  .risk-whitelist-create {
    width: 124px;
    display:flex;
    gap: 6px;
    align-items: center;
    .audit-icon-add {
      margin-right: 4px;
    }
  }
  .page-toolbar {
    display: flex;
    margin-bottom: 16px;
  }

  .page-search {
    width: 800px;
    margin-left: auto;
  }

  .list-empty {
    padding: 80px 0;
    color: var(--audit-neutral-text-02);
    text-align: center;
  }

  :deep(.t-table__cell--title),
  :deep(th .t-table__th-cell-inner) {
    white-space: nowrap;
  }

  :deep(.expire-cell) {
    white-space: nowrap;
  }

  :deep(.scope-cell) {
    max-width: 100%;
    min-width: 0;
    overflow: hidden;
  }

  :deep(.row-actions) {
    display: flex;
    gap: 12px;
    align-items: center;
  }

  :deep(.more-trigger) {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    padding: 0;
    color: var(--audit-neutral-text-03);
    cursor: pointer;
    background: transparent;
    border: 0;
  }

  :deep(.more-trigger:hover),
  :deep(.more-trigger:focus),
  :deep(.more-trigger:active) {
    color: var(--audit-neutral-text-02);
  }

  :deep(.hit-zero) {
    color: var(--audit-neutral-text-03);
  }
</style>
