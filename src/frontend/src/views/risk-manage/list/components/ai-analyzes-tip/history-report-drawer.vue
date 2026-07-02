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
    v-model:isShow="show"
    :show-footer="false"
    :title="t('历史分析报告')"
    :width="drawerWidth">
    <div
      v-if="show"
      class="history-report-drawer-content">
      <div class="search-row">
        <bk-search-select
          v-model="searchValue"
          class="search-input"
          clearable
          :data="searchSelectData"
          :defaut-using-item="{ inputHtml: t('请选择') }"
          :get-menu-list="getMenuList"
          :placeholder="t('搜索报告标题、报告类型、分析范围、生成人')"
          unique-select
          @update:model-value="handleSearch" />
      </div>
      <tdesign-list
        ref="listRef"
        :columns="tableColumns"
        :data-source="dataSource"
        :row-class-name="getRowClassName"
        row-key="id"
        :settings="[]"
        table-max-height="calc(100vh - 210px)"
        @request-success="handleRequestSuccess" />
    </div>
  </audit-sideslider>
</template>

<script setup lang="tsx">
  import {
    computed,
    nextTick,
    onBeforeUnmount,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import RiskManageService from '@service/risk-manage';
  import MetaManageService from '@service/meta-manage';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import TdesignList from '@components/tdesign-list/index.vue';
  import Tooltips from '@components/show-tooltips-text/index.vue';

  import ReportTitleCell from './report-title-cell.vue';
  import RiskTablePopover from './risk-table-popover.vue';

  export interface AnalyzeWatchPayload {
    title: string;
    reportId: string | number;
  }

  export interface HistoryReportItem {
    analysis_scope: string;
    title: string;
    created_at: string;
    created_by: string;
    error_message?: string;
    id?: string | number;
    report_id: string | number;
    report_type: string;
    risk_count: number;
    status: string;
    title_generating?: boolean;
  }

  interface Props {
    isShow: boolean;
  }

  interface Emits {
    (e: 'update:isShow', val: boolean): void;
    (e: 'open-report', row: HistoryReportItem): void;
    (e: 'view-risks', row: HistoryReportItem): void;
    (e: 'analyze-finished', data: string): void;
  }

  interface SearchKey {
    id: string;
    name: string;
    values: Array<{ id: string; name: string }>;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const router = useRouter();

  const drawerWidth = ref('1200');
  const titleColumnMinWidth = ref(240);

  const updateDrawerLayout = () => {
    const viewportWidth = window.innerWidth;
    if (viewportWidth >= 1920) {
      drawerWidth.value = '1440';
      titleColumnMinWidth.value = 320;
    } else if (viewportWidth >= 1600) {
      drawerWidth.value = '1320';
      titleColumnMinWidth.value = 280;
    } else {
      drawerWidth.value = '1200';
      titleColumnMinWidth.value = 240;
    }
  };

  const show = computed({
    get: () => props.isShow,
    set: (val: boolean) => emit('update:isShow', val),
  });

  const searchValue = ref<SearchKey[]>([]);
  const listRef = ref<InstanceType<typeof TdesignList>>();
  const originalQuery = ref<Record<string, any>>({});
  const pendingReportIds = ref<Array<string | number>>([]);
  const retryingReportIds = ref<Array<string | number>>([]);
  const listPollingTimer = ref<ReturnType<typeof setTimeout> | null>(null);
  const LIST_POLL_INTERVAL = 3000;

  const getRowReportId = (row: HistoryReportItem) => row.report_id ?? row.id;

  const getListData = () => (listRef.value?.getListData?.() || []) as HistoryReportItem[];

  const hasGeneratingInList = () => getListData().some(row => String(row.status || '').toLowerCase() === 'generating' || row.title_generating);

  const shouldPollList = () => show.value && (hasGeneratingInList() || pendingReportIds.value.length > 0);

  const isSameReportId = (left: string | number, right: string | number) => String(left) === String(right);

  const resolveRowData = (row: Record<string, any>) => (row?.row || row) as HistoryReportItem;

  const getRowClassName = (row: Record<string, any>) => {
    const rowData = resolveRowData(row);
    const reportId = getRowReportId(rowData);
    if (!reportId) {
      return '';
    }
    if (!pendingReportIds.value.some(id => isSameReportId(id, reportId))) {
      return '';
    }
    const status = String(rowData.status || '').toLowerCase();
    if (status === 'generating' || rowData.title_generating) {
      return 'new-row';
    }
    return '';
  };

  const removePendingReportId = (reportId: string | number) => {
    pendingReportIds.value = pendingReportIds.value.filter(id => !isSameReportId(id, reportId));
  };

  const stopListPolling = () => {
    if (listPollingTimer.value) {
      clearTimeout(listPollingTimer.value);
      listPollingTimer.value = null;
    }
  };

  const scheduleNextListPoll = () => {
    stopListPolling();
    if (!shouldPollList()) {
      return;
    }
    listPollingTimer.value = setTimeout(() => {
      if (shouldPollList()) {
        listRef.value?.silentRefreshList();
      }
    }, LIST_POLL_INTERVAL);
  };

  const resumeListPolling = () => {
    if (!shouldPollList()) {
      return;
    }
    scheduleNextListPoll();
  };

  const {
    run: getAiAnalyseReportDetail,
  } = useRequest(RiskManageService.getAiAnalyseReportDetail, {
    defaultValue: [],
    onSuccess(data) {
      emit('analyze-finished', JSON.stringify(data));
    },
  });

  const {
    run: retryAiAnalyseReport,
  } = useRequest(RiskManageService.retryAiAnalyseReport, {
    defaultValue: null,
    onSuccess() {
      messageSuccess(t('已重新提交生成'));
    },
  });

  const isRetryingReport = (reportId: string | number) => (
    retryingReportIds.value.some(id => isSameReportId(id, reportId))
  );

  const handleRetryReport = async (row: HistoryReportItem) => {
    const reportId = getRowReportId(row);
    if (!reportId || isRetryingReport(reportId)) {
      return;
    }
    retryingReportIds.value = [...retryingReportIds.value, reportId];
    try {
      const result = await retryAiAnalyseReport({ report_id: reportId });
      const listData = getListData();
      const target = listData.find(item => isSameReportId(getRowReportId(item), reportId));
      if (target) {
        target.status = result?.status || 'generating';
        target.error_message = '';
        target.title_generating = false;
      }
      beginAnalyzeWatch({ title: row.title, reportId });
      listRef.value?.refreshList();
    } finally {
      retryingReportIds.value = retryingReportIds.value.filter(id => !isSameReportId(id, reportId));
    }
  };

  const checkPendingReports = () => {
    const listData = getListData();

    [...pendingReportIds.value].forEach((reportId) => {
      const matched = listData.find(item => isSameReportId(getRowReportId(item), reportId));
      if (!matched) {
        return;
      }

      const status = String(matched.status || '').toLowerCase();
      if (status === 'generating' || matched.title_generating) {
        return;
      }

      removePendingReportId(reportId);
      if (status === 'success') {
        const matchedReportId = getRowReportId(matched);
        if (matchedReportId) {
          getAiAnalyseReportDetail({
            report_id: matchedReportId,
          });
        }
      }
    });
  };

  const handleRequestSuccess = () => {
    checkPendingReports();
    scheduleNextListPoll();
  };

  const beginAnalyzeWatch = (payload: AnalyzeWatchPayload) => {
    if (!payload.reportId) {
      return;
    }
    if (!pendingReportIds.value.some(id => isSameReportId(id, payload.reportId))) {
      pendingReportIds.value = [...pendingReportIds.value, payload.reportId];
    }
    scheduleNextListPoll();
  };

  const markAnalyzeFailed = (reportId: string | number) => {
    removePendingReportId(reportId);
    scheduleNextListPoll();
  };

  const searchSelectData = ref([
    {
      name: t('报告标题'),
      id: 'title',
      placeholder: t('请输入'),
    },
    {
      name: t('报告类型'),
      id: 'report_type',
      placeholder: t('请选择'),
      children: [
        { id: 'system', name: t('系统分析') },
        { id: 'custom', name: t('自定义分析') },
      ],
    },
    {
      name: t('分析范围'),
      id: 'analysis_scope',
      placeholder: t('请输入'),
    },
    {
      name: t('生成人'),
      id: 'created_by',
      placeholder: t('请选择'),
      children: [] as Array<{ id: string; name: string }>,
    },
  ]);

  const {
    run: fetchUserList,
  } = useRequest(MetaManageService.fetchUserList, {
    defaultParams: { page: 1, page_size: 30 },
    defaultValue: { count: 0, results: [] } as { count: number; results: any[] },
  });

  const getMenuList = async (item: any, keyword: string) => {
    if (!item) return searchSelectData.value;
    const searchItem = searchSelectData.value.find(s => s.id === item?.id);
    if (searchItem && item.id === 'created_by') {
      if (keyword) {
        const userList = await fetchUserList({ fuzzy_lookups: keyword });
        searchItem.children = userList.results.map((user: any) => ({
          id: user.username,
          name: `${user.username}(${user.display_name})`,
        }));
      } else {
        searchItem.children = [];
      }
    }
    return (searchSelectData.value.find(s => s.id === item?.id)?.children) || [];
  };

  const reportStatusTextMap: Record<string, string> = {
    generating: t('生成中'),
    success: t('已完成'),
    failed: t('生成失败'),
  };
  const reportStatusIconMap: Record<string, { icon: string; color: string; spin?: boolean }> = {
    generating: {
      icon: 'loading',
      color: '#3a84ff',
      spin: true,
    },
    success: {
      icon: 'success',
      color: '#2dcb56',
    },
    failed: {
      icon: 'failed',
      color: '#ea3636',
    },
  };

  const canOpenReport = (status: string) => String(status || '').toLowerCase() === 'success';

  const handleTitleUpdated = (reportId: string | number, title: string) => {
    const listData = listRef.value?.getListData?.() as HistoryReportItem[] | undefined;
    if (!listData?.length) {
      listRef.value?.refreshList();
      return;
    }
    const target = listData.find(item => String(getRowReportId(item)) === String(reportId));
    if (target) {
      target.title = title;
    }
  };

  const getAnalysisScopeText = (row: HistoryReportItem) => {
    try {
      const scopeArray = JSON.parse(row.analysis_scope);
      return scopeArray.map((item: any) => {
        if (item.label === '首次发现时间') {
          return `${item.label}=${Array.isArray(item.value) ? item.value.join('-') : item.value}`;
        }
        return `${item.label}=${Array.isArray(item.value) ? item.value.join(',') : item.value}`;
      }).join('，');
    } catch {
      return row.analysis_scope || '--';
    }
  };

  const getReportStatusText = (status: string) => reportStatusTextMap[String(status || '').toLowerCase()] || status;
  const renderReportStatus = (row: HistoryReportItem) => {
    const { status, error_message: errorMessage } = row;
    const normalizedStatus = String(status || '').toLowerCase();
    const config = reportStatusIconMap[normalizedStatus];
    if (!config) {
      return <span>{getReportStatusText(status)}</span>;
    }
    const statusCell = (
      <span class="report-status-cell">
        <span class="report-status-icon-wrap">
          <audit-icon
            class={config.spin ? 'report-status-icon rotate-loading' : 'report-status-icon'}
            style={{ color: config.color }}
            svg
            type={config.icon} />
        </span>
        <span class="report-status-text">{getReportStatusText(status)}</span>
      </span>
    );
    if (normalizedStatus === 'failed') {
      const statusContent = errorMessage ? (
        <span
          class="report-status-failed"
          v-bk-tooltips={{
            content: errorMessage,
            maxWidth: 480,
          }}>
          {statusCell}
        </span>
        ) : statusCell;
      const reportId = getRowReportId(row);
      return (
        <span class="report-status-cell-wrap">
          {statusContent}
          <bk-button
            class="report-retry-btn"
            disabled={isRetryingReport(reportId)}
            text
            v-bk-tooltips={{
              content: t('重试'),
            }}
            onClick={(event: MouseEvent) => {
              event.stopPropagation();
              handleRetryReport(row);
            }}>
            <audit-icon
              class={isRetryingReport(reportId) ? 'rotate-loading' : ''}
              type="refresh" />
          </bk-button>
        </span>
      );
    }
    return statusCell;
  };

  const tableColumns = computed(() => [
    {
      title: t('报告标题'),
      colKey: 'title',
      minWidth: titleColumnMinWidth.value,
      ellipsis: true,
      cell: (h: any, { row }: { row: HistoryReportItem }) => (
        <ReportTitleCell
          canEdit={canOpenReport(row.status) && !row.title_generating}
          canOpen={canOpenReport(row.status)}
          reportId={getRowReportId(row)}
          title={row.title}
          titleGenerating={!!row.title_generating}
          onOpen={() => emit('open-report', row)}
          onUpdated={(title: string) => handleTitleUpdated(getRowReportId(row), title)} />
      ),
    },
    {
      title: t('报告类型'),
      colKey: 'report_type',
      width: 120,
      filter: {
        type: 'single',
        showConfirmAndReset: true,
        resetValue: undefined,
        list: [
          {
            label: t('系统分析'),
            value: 'system',
          },
          {
            label: t('自定义分析'),
            value: 'custom',
          },
        ],
      },
      cell: (h: any, { row }: { row: HistoryReportItem }) => (
        <bk-tag>{row.report_type === 'system' ? t('系统分析') : t('自定义分析')}</bk-tag>
      ),
    },
    {
      title: t('分析范围'),
      colKey: 'analysisScope',
      minWidth: 200,
      ellipsis: true,
      cell: (h: any, { row }: { row: HistoryReportItem }) => (
        <Tooltips
          data={getAnalysisScopeText(row)}
          maxWidth={480} />
      ),
    },
    {
      title: t('关联风险数量'),
      colKey: 'risk_count',
      width: 140,
      align: 'center',
      sortType: 'all',
      sorter: true,
      cell: (h: any, { row }: { row: HistoryReportItem }) => (
        <RiskTablePopover
          count={row.risk_count}
          reportId={getRowReportId(row)}
          status={row.status} />
      ),
    },
    {
      title: t('状态'),
      colKey: 'status',
      width: 160,
      filter: {
        type: 'single',
        showConfirmAndReset: true,
        resetValue: undefined,
        list: [
          {
            label: t('生成中'),
            value: 'generating',
          },
          {
            label: t('已完成'),
            value: 'success',
          },
          {
            label: t('生成失败'),
            value: 'failed',
          },
        ],
      },
      cell: (h: any, { row }: { row: HistoryReportItem }) => renderReportStatus(row),
    },
    {
      title: t('生成人'),
      colKey: 'created_by',
      width: 120,
      ellipsis: true,
      cell: (h: any, { row }: { row: HistoryReportItem }) => (
        <Tooltips data={row.created_by || '--'} />
      ),
    },
    {
      title: t('生成时间'),
      colKey: 'created_at',
      width: 180,
      sortType: 'all',
      sorter: true,
      ellipsis: true,
      cell: (h: any, { row }: { row: HistoryReportItem }) => (
        <Tooltips data={row.created_at || '--'} />
      ),
    },
  ]);

  // 获取历史报告列表占位
  const dataSource = RiskManageService.getHistoryReportList;


  const buildHistoryReportSearchParams = (searchKeys: SearchKey[]) => {
    const search: Record<string, string | undefined> = {
      keyword: undefined,
      title: undefined,
      analysis_scope: undefined,
      report_type: undefined,
    };

    searchKeys.forEach((item) => {
      if (!item.values?.length) return;
      const value = item.values.map(v => v.id).join(',');
      if (!value) return;
      if (item.id === 'report_type') {
        search.report_type = value;
      } else if (item.id === 'title') {
        search.title = value;
      } else if (item.id === 'analysis_scope') {
        search.analysis_scope = value;
      } else {
        search.keyword = value;
      }
    });

    return search;
  };

  const handleSearch = (keyword: SearchKey[]) => {
    listRef.value?.fetchData({
      ...buildHistoryReportSearchParams(keyword),
      sort: ['-created_at'],
    });
  };

  watch(show, (val) => {
    if (val) {
      updateDrawerLayout();
      // 记录当前URL参数
      originalQuery.value = { ...router.currentRoute.value.query };
      searchValue.value = [];
      nextTick(() => {
        // 避免复用外层页面 URL 中的 sort（如 -event_time）导致历史报告接口排序字段非法
        listRef.value?.fetchData({
          keyword: undefined,
          title: undefined,
          analysis_scope: undefined,
          sort: ['-created_at'],
        });
        resumeListPolling();
      });
    } else {
      stopListPolling();
      // 恢复原始URL参数
      router.replace({
        query: originalQuery.value,
      });
    }
  });

  defineExpose({
    listRef,
    beginAnalyzeWatch,
    markAnalyzeFailed,
  });

  onBeforeUnmount(() => {
    stopListPolling();
  });
</script>

<style lang="postcss" scoped>
.history-report-drawer-content {
  max-height: calc(100vh - 150px);
  margin-top: 16px;
  margin-right: 50px;
  margin-left: 50px;

  :deep(.audit-tdesign-list) {
    background-color: #fff;

    .show-tooltips-text {
      max-width: 100%;
    }

    .t-table,
    .t-table__content,
    .t-table__header,
    .t-table__body,
    .t-table__header--fixed > tr > th,
    .t-table th,
    .t-table td {
      background-color: #fff !important;
    }
  }
}

:deep(.audit-tdesign-list .tdesign-list tr.new-row) {
  td,
  th {
    background-color: #e4faf0 !important;
  }

  &:hover td,
  &:hover th {
    background-color: #d8f5e6 !important;
  }
}

.search-row {
  margin-bottom: 16px;
}

.search-input {
  width: 100%;
}

:deep(.hover-show-icon) {
  visibility: hidden;
}

:deep(.audit-tdesign-list tr:hover .hover-show-icon),
:deep(.audit-tdesign-list .t-table__body tr:hover .hover-show-icon) {
  visibility: visible;
}

@media (width >= 1600px) {
  .history-report-drawer-content {
    margin-right: 32px;
    margin-left: 32px;
  }
}

:deep(.report-status-cell-wrap) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

:deep(.report-status-failed) {
  display: inline-flex;
  cursor: help;
}

:deep(.report-retry-btn) {
  display: inline-flex;
  width: 20px;
  height: 20px;
  min-width: 20px;
  padding: 0;
  color: #3a84ff;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;

  .audit-icon {
    font-size: 14px;
  }
}

:deep(.report-status-cell) {
  display: inline-flex;
  line-height: 20px;
  color: #313238;
  align-items: center;

  .report-status-icon-wrap {
    display: inline-flex;
    flex-shrink: 0;
    align-items: center;
    justify-content: center;
    width: 14px;
    height: 14px;
    margin-right: 6px;
  }

  .report-status-icon {
    font-size: 14px;
    line-height: 1;
  }

  .report-status-text {
    line-height: 20px;
  }
}

:deep(.risk-count-cell) {
  display: inline-flex;
  align-items: center;
  gap: 4px;

  .info-icon {
    font-size: 14px;
    color: #979ba5;
  }

  .risk-count-link {
    color: #313238;
    text-decoration: underline;
    cursor: pointer;
    text-underline-offset: 2px;
  }

  .link-icon {
    font-size: 12px;
    color: #3a84ff;
    cursor: pointer;
    visibility: hidden;
  }
}

/* 鼠标悬停行时显示 jump-link */
:deep(.audit-tdesign-list tr:hover .risk-count-cell .link-icon),
:deep(.audit-tdesign-list .t-table__body tr:hover .risk-count-cell .link-icon) {
  visibility: visible;
}
</style>
