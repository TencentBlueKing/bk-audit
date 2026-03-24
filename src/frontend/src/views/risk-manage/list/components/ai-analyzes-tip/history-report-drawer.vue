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
    width="1100">
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
    report_id: string;
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

  const tableColumns = [
    {
      title: t('报告标题'),
      colKey: 'title',
      minWidth: 180,
      ellipsis: true,
      cell: (h: any, { row }: { row: HistoryReportItem }) => (
        <span
          class="report-title-link"
          onClick={() => emit('open-report', row)}>
          {row.title}
        </span>
      ),
    },
    {
      title: t('报告类型'),
      colKey: 'reportTypeLabel',
      width: 120,
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
      colKey: 'riskCount',
      width: 140,
      align: 'center',
      cell: (h: any, { row }: { row: HistoryReportItem }) => (
        <RiskTablePopover
          count={row.risk_count}
          report-id={row.report_id} />
      ),
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
        listRef.value?.fetchData({ keyword: '' });
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

:deep(.risk-count-cell) {
  display: inline-flex;
  align-items: center;
  gap: 4px;

  .info-icon {
    font-size: 14px;
    color: #979ba5;
  }

  .risk-count-link {
    color: #3a84ff;
    cursor: pointer;

    &:hover {
      text-decoration: underline;
    }
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
