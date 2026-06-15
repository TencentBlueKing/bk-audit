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
    width="1200">
    <div
      v-if="show"
      class="history-report-drawer-content">
      <div class="search-row">
        <bk-input
          v-model="searchKeyword"
          clearable
          :placeholder="t('搜索报告标题、报告类型、分析范围、生成人')"
          style="width: 100%;"
          type="search"
          @clear="handleSearch"
          @enter="handleSearch" />
      </div>
      <tdesign-list
        ref="listRef"
        :columns="tableColumns"
        :data-source="dataSource"
        row-key="id"
        :settings="[]"
        table-max-height="calc(100vh - 210px)" />
    </div>
  </audit-sideslider>
</template>

<script setup lang="tsx">
  import {
    computed,
    nextTick,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import RiskManageService from '@service/risk-manage';

  import TdesignList from '@components/tdesign-list/index.vue';

  import RiskTablePopover from './risk-table-popover.vue';

  export interface HistoryReportItem {
    analysis_scope: string;
    title: string;
    created_at: string;
    created_by: string;
    error_message?: string;
    report_id: string | number;
    report_type: string;
    risk_count: number;
    status: string;
  }

  interface Props {
    isShow: boolean;
  }

  interface Emits {
    (e: 'update:isShow', val: boolean): void;
    (e: 'open-report', row: HistoryReportItem): void;
    (e: 'view-risks', row: HistoryReportItem): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const router = useRouter();

  const show = computed({
    get: () => props.isShow,
    set: (val: boolean) => emit('update:isShow', val),
  });

  const searchKeyword = ref('');
  const listRef = ref<InstanceType<typeof TdesignList>>();
  const originalQuery = ref<Record<string, any>>({});

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
    if (normalizedStatus === 'failed' && errorMessage) {
      return (
        <span
          class="report-status-failed"
          v-bk-tooltips={{
            content: errorMessage,
            maxWidth: 480,
          }}>
          {statusCell}
        </span>
      );
    }
    return statusCell;
  };

  const tableColumns = [
    {
      title: t('报告标题'),
      colKey: 'title',
      minWidth: 180,
      ellipsis: true,
      cell: (h: any, { row }: { row: HistoryReportItem }) => (
        canOpenReport(row.status)
          ? (
            <span
              class="report-title-link"
              onClick={() => emit('open-report', row)}>
              {row.title}
            </span>
          )
          : <span class="report-title-text">{row.title}</span>
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
         <bk-tag>{row.report_type ===  'system' ? t('系统分析') : t('自定义分析')}</bk-tag>
    )    },
    {
      title: t('分析范围'),
      colKey: 'analysisScope',
      minWidth: 200,
      ellipsis: true,
      cell: (h: any, { row }: { row: HistoryReportItem }) => {
        try {
          const scopeArray = JSON.parse(row.analysis_scope);
          const formattedText = scopeArray.map((item: any) => {
            if (item.label === '首次发现时间') {
              return `${item.label}=${Array.isArray(item.value) ? item.value.join('-') : item.value}`;
            }
            return `${item.label}=${Array.isArray(item.value) ? item.value.join(',') : item.value
            }`;
          }).join('，');
          return <span>{formattedText}</span>;
        } catch {
          return <span>{row.analysis_scope}</span>;
        }
      },
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
          reportId={row.report_id}
          status={row.status} />
      ),
    },
    {
      title: t('状态'),
      colKey: 'status',
      width: 120,
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
    },
    {
      title: t('生成时间'),
      colKey: 'created_at',
      width: 180,
      sortType: 'all',
      sorter: true,
    },
  ];

  // 获取历史报告列表占位
  const dataSource = RiskManageService.getHistoryReportList;


  const handleSearch = () => {
    listRef.value?.fetchData({ keyword: searchKeyword.value });
  };

  watch(show, (val) => {
    if (val) {
      // 记录当前URL参数
      originalQuery.value = { ...router.currentRoute.value.query };
      searchKeyword.value = '';
      nextTick(() => {
        // 避免复用外层页面 URL 中的 sort（如 -event_time）导致历史报告接口排序字段非法
        listRef.value?.fetchData({ keyword: '', sort: ['-created_at'] });
      });
    } else {
      // 恢复原始URL参数
      router.replace({
        query: originalQuery.value,
      });
    }
  });

  defineExpose({
    listRef,
  });
</script>

<style lang="postcss" scoped>
.history-report-drawer-content {
  max-height: calc(100vh - 150px);
  margin-top: 16px;
  margin-right: 50px;
  margin-left: 50px;
}

.search-row {
  margin-bottom: 16px;
}

.search-icon {
  font-size: 14px;
  color: #979ba5;
  cursor: pointer;

  &:hover {
    color: #3a84ff;
  }
}

:deep(.report-title-link) {
  color: #3a84ff;
  cursor: pointer;

  &:hover {
    color: #699df4;
    text-decoration: underline;
  }
}

:deep(.report-title-text) {
  color: #313238;
}

:deep(.report-status-failed) {
  display: inline-flex;
  cursor: help;
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
