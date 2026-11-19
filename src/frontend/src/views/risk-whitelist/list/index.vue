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
      use-skeleton
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
  import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import RiskWhitelistService from '@service/risk-whitelist';

  import type RiskWhitelist from '@model/risk-whitelist/whitelist';

  import useEventBus from '@hooks/use-event-bus';
  import useMessage from '@hooks/use-message';

  import MatchScopeExpression from '@components/risk-whitelist/match-scope-expression.vue';
  import { WHITELIST_STATUS_TEXT, WHITELIST_TYPE_TEXT } from '@components/risk-whitelist/constants';
  import TdesignList from '@components/tdesign-list/index.vue';

  import {
    getSceneSystemParams,
    SCENE_SELECTOR_STORAGE_KEY,
    setActiveSceneSelection,
  } from '@/utils/assist/scene-system-params';

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

  interface CachedSceneItem {
    id: string;
    permission?: {
      manage_scene?: boolean;
      view_scene?: boolean;
    };
  }

  const EMPTY_LIST = { results: [] as RiskWhitelist[], total: 0, count: 0 };

  const { t } = useI18n();
  const router = useRouter();
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

  const readCachedSceneList = (): CachedSceneItem[] => {
    try {
      const list = JSON.parse(localStorage.getItem('scene-system-selector:sceneList') || '[]');
      return Array.isArray(list) ? list : [];
    } catch {
      return [];
    }
  };

  const readManagePlatform = () => {
    try {
      const permission = JSON.parse(sessionStorage.getItem('userScenePermission') || '{}');
      return permission.manage_platform === true;
    } catch {
      return false;
    }
  };

  /** 当前场景是否具备白名单管理权限；列表未就绪时返回 null，避免误请求 */
  const getCurrentSceneManageAccess = (): boolean | null => {
    if (readManagePlatform()) return true;
    const sceneId = String(getSceneSystemParams().scope_id || '');
    if (!sceneId) return false;
    const list = readCachedSceneList();
    if (!list.length) return null;
    const current = list.find(item => String(item.id) === sceneId);
    if (!current) return false;
    return current.permission?.manage_scene === true;
  };

  /**
   * 与场景配置路由分流一致：无当前场景管理权时切到可管理场景 / 引导申请，不打白名单接口。
   * @returns true 表示可继续请求列表
   */
  const ensureManageAccessBeforeFetch = (): boolean => {
    const access = getCurrentSceneManageAccess();
    if (access === true) return true;
    if (access === null) return false;

    const sceneId = String(getSceneSystemParams().scope_id || '');
    const list = readCachedSceneList();
    const firstManageable = list.find(item => item.permission?.manage_scene === true);
    if (firstManageable) {
      const manageableSceneId = String(firstManageable.id);
      const selection = { id: manageableSceneId, type: 'scene' as const };
      setActiveSceneSelection(selection);
      localStorage.setItem(SCENE_SELECTOR_STORAGE_KEY, JSON.stringify(selection));
      router.replace({
        name: 'riskWhitelistList',
        query: {
          scene_id: manageableSceneId,
          scope_id: manageableSceneId,
          scope_type: 'scene',
        },
      });
      return false;
    }

    const hasViewOnly = list.some(item => item.permission?.view_scene === true);
    router.replace({
      name: hasViewOnly || list.length > 0 ? 'userLandingPage' : 'permissionsPage',
      query: hasViewOnly || list.length > 0
        ? (sceneId ? { scene_id: sceneId } : {})
        : { role: 'manager', ...(sceneId ? { scene_id: sceneId } : {}) },
    });
    return false;
  };

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
    RiskWhitelistService.approve({ id: row.id }).then((data) => {
      const status = data?.status;
      if (status === 'pending') {
        messageSuccess(t('审批已提交，工单仍在处理中'));
      } else if (status === 'active') {
        messageSuccess(t('已通过，白名单生效并关闭关联风险单'));
      } else {
        messageSuccess(t('操作成功'));
      }
      refresh();
    })
      .finally(() => {
        const next = new Set(approvingIds.value);
        next.delete(row.id);
        approvingIds.value = next;
      });
  };

  /** bk-dropdown 的 isShow 仅在 trigger=manual 时生效；columns 需依赖 moreOpenId 才能重渲染 */
  const moreOpenId = ref<number | string | null>(null);

  const closeMoreMenu = () => {
    moreOpenId.value = null;
  };

  const runMoreAction = (action: () => void) => {
    closeMoreMenu();
    nextTick(() => {
      action();
    });
  };

  const renderMore = (
    rowId: number | string,
    items: Array<{ label: string; onClick: () => void }>,
  ) => (
    <bk-dropdown
      isShow={moreOpenId.value === rowId}
      placement="bottom-end"
      trigger="manual"
      onShowChange={(show: boolean) => {
        if (!show && moreOpenId.value === rowId) {
          moreOpenId.value = null;
        }
      }}>
      {{
        default: () => (
          <button
            class="more-trigger"
            title={t('更多')}
            type="button"
            onClick={(event: MouseEvent) => {
              event.stopPropagation();
              moreOpenId.value = moreOpenId.value === rowId ? null : rowId;
            }}>
            <audit-icon type="more" />
          </button>
        ),
        content: () => (
          <bk-dropdown-menu>
            {items.map(item => (
              <bk-dropdown-item onClick={() => runMoreAction(item.onClick)}>
                {item.label}
              </bk-dropdown-item>
            ))}
          </bk-dropdown-menu>
        ),
      }}
    </bk-dropdown>
  );

  /**
   * 操作列布局对齐设计稿（仍以 actions 决定能否展示）：
   * - 已停用：启用；更多：命中记录、删除（不展示续期/编辑）
   * - 已到期：编辑、续期；更多：命中记录、删除
   * - 生效中：编辑、停用；更多：续期、命中记录（及删除若有）
   */
  const renderActions = (row: RiskWhitelist) => {
    const set = new Set(row.actions || []);
    const isDisabled = row.status === 'disabled';
    const isExpired = row.status === 'expired';
    const primary: any[] = [];
    const more: Array<{ label: string; onClick: () => void }> = [];

    if (set.has('approve')) {
      primary.push(
        <bk-button
          disabled={approvingIds.value.has(row.id)}
          loading={approvingIds.value.has(row.id)}
          text
          theme="primary"
          onClick={() => approve(row)}>
          {t('通过')}
        </bk-button>,
      );
    }
    if (set.has('reject')) {
      primary.push(
        <bk-button text theme="primary" onClick={() => rejectRef.value?.open(row)}>{t('驳回')}</bk-button>,
      );
    }
    // 已停用不展示编辑
    if (set.has('edit') && !isDisabled) {
      primary.push(
        <bk-button text theme="primary" onClick={() => editRef.value?.open(row)}>{t('编辑')}</bk-button>,
      );
    }
    if (set.has('disable')) {
      primary.push(
        <bk-button text theme="primary" onClick={() => toggleRef.value?.open(row, false)}>{t('停用')}</bk-button>,
      );
    }
    if (set.has('enable')) {
      primary.push(
        <bk-button text theme="primary" onClick={() => toggleRef.value?.open(row, true)}>{t('启用')}</bk-button>,
      );
    }
    if (set.has('renew') && !isDisabled) {
      // 已停用：先启用再续期，不展示续期
      // 生效中：续期进更多；已到期：续期与编辑并列
      if (set.has('disable') && !isExpired) {
        more.push({ label: t('续期'), onClick: () => renewRef.value?.open(row) });
      } else {
        primary.push(
          <bk-button text theme="primary" onClick={() => renewRef.value?.open(row)}>{t('续期')}</bk-button>,
        );
      }
    }
    if (set.has('hits')) {
      more.push({ label: t('命中记录'), onClick: () => hitRef.value?.open(row.id, row.rule_code) });
    }
    if (set.has('delete')) {
      if (!primary.length && !more.length) {
        primary.push(
          <bk-button text theme="primary" onClick={() => deleteRef.value?.open(row)}>{t('删除')}</bk-button>,
        );
      } else {
        more.push({ label: t('删除'), onClick: () => deleteRef.value?.open(row) });
      }
    }

    if (!primary.length && !more.length) return null;
    return (
      <div class="row-actions">
        {primary}
        {more.length ? renderMore(row.id, more) : null}
      </div>
    );
  };

  const columns = computed(() => {
    // 依赖 moreOpenId，保证菜单开关时操作列重渲染
    void moreOpenId.value;
    return [
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
      {
        title: t('更新人'),
        colKey: 'updated_by',
        width: 103,
        ellipsis: true,
        cell: (_: unknown, { row }: { row: RiskWhitelist }) => row.updated_by || '--',
      },
      { title: t('更新时间'), colKey: 'updated_at', width: 180, minWidth: 180, sorter: true },
      {
        title: t('操作'),
        colKey: 'action',
        width: 136,
        fixed: 'right',
        cell: (_: unknown, { row }: { row: RiskWhitelist }) => renderActions(row),
      },
    ];
  });

  const buildSearchParams = () => {
    const params: Record<string, string> = {};
    searchValue.value.forEach((item) => {
      const value = item.values?.map(child => child.id).filter(Boolean).join(',');
      if (value) params[item.id] = value;
    });
    return params;
  };

  const dataSource = (params: Record<string, any>) => {
    if (!ensureManageAccessBeforeFetch()) {
      return Promise.resolve(EMPTY_LIST);
    }
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
    if (!ensureManageAccessBeforeFetch()) return;
    listRef.value?.fetchData(buildSearchParams());
  };

  const handleClearSearch = () => {
    searchValue.value = [];
    hasSearch.value = false;
    if (!ensureManageAccessBeforeFetch()) return;
    listRef.value?.fetchData({});
  };

  const refresh = () => {
    if (!ensureManageAccessBeforeFetch()) return;
    listRef.value?.fetchData(buildSearchParams());
  };

  const openCreate = () => {
    if (!ensureManageAccessBeforeFetch()) return;
    editRef.value?.open();
  };

  const handleSceneChange = () => refresh();

  const handleSceneListReady = () => {
    // 场景列表就绪后再判定权限，避免首屏用旧 scene_id 打出裸 toast
    refresh();
  };

  onMounted(() => {
    onEvent('scene:change', handleSceneChange);
    onEvent('scene-list-ready', handleSceneListReady);
  });

  onUnmounted(() => {
    off('scene:change', handleSceneChange);
    off('scene-list-ready', handleSceneListReady);
  });
</script>
<style lang="postcss" scoped>
  .risk-whitelist-page {
    padding: var(--bk-theme-space-24);
    background: var(--bk-theme-surface-default);
  }

  .risk-whitelist-create {
    width: 124px;
    display:flex;
    gap: var(--bk-theme-space-6);
    align-items: center;
    .audit-icon-add {
      margin-right: var(--bk-theme-space-4);
    }
  }
  .page-toolbar {
    display: flex;
    margin-bottom: var(--bk-theme-space-16);
  }

  .page-search {
    width: 800px;
    margin-left: auto;
  }

  .list-empty {
    padding: 80px 0;
    color: var(--bk-theme-text-default);
    text-align: center;
  }

  :deep(.t-table__cell--title),
  :deep(th .t-table__th-cell-inner) {
    white-space: nowrap;
  }

  :deep(.expire-cell) {
    white-space: nowrap;
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

  :deep(.row-actions) {
    display: flex;
    gap: var(--bk-theme-space-12);
    align-items: center;
  }

  :deep(.more-trigger) {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    padding: 0;
    color: var(--bk-theme-text-weak);
    cursor: pointer;
    background: transparent;
    border: 0;
  }

  :deep(.more-trigger:hover),
  :deep(.more-trigger:focus),
  :deep(.more-trigger:active) {
    color: var(--bk-theme-text-default);
  }

  :deep(.hit-zero) {
    color: var(--bk-theme-text-weak);
  }
</style>
