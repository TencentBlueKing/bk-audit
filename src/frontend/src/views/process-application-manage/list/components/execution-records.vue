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
    v-model:is-show="isShow"
    :show-footer="false"
    show-header-slot
    :title="t('执行记录')"
    :width="1280">
    <template #header>
      <div>
        <span>{{ t('执行记录') }}</span>
        <span
          v-if="headerExtra"
          class="execution-header-extra">
          {{ headerExtra }}
        </span>
      </div>
    </template>
    <div
      class="execution-records"
      data-testid="execution-records-panel">
      <bk-search-select
        v-model="searchKey"
        class="execution-search"
        clearable
        :data="searchData"
        :defaut-using-item="{ inputHtml: t('请选择') }"
        :placeholder="t('搜索 任务ID、任务名称、套餐名称（ID）、风险ID、状态、执行人')"
        unique-select
        @update:model-value="search" />
      <tdesign-list
        v-if="isShow"
        ref="listRef"
        class="execution-table mt16"
        :columns="columns"
        :data-source="dataSource"
        :fit-viewport-height="false"
        :persist-table-filters="false"
        row-key="task_id"
        :search-params="linkedSearchParams"
        use-skeleton
        @clear-search="handleClearFilter"
        @filter-change="handleTableFilterChange" />
    </div>
  </audit-sideslider>
  <execution-detail
    v-model:is-show="showDetail"
    :task-id="activeTaskId"
    @retried="search" />
  <execution-retry-dialog
    v-model:is-show="showRetry"
    :detail="retryDetail"
    :loading="retrying"
    @confirm="confirmRetry" />
</template>
<script setup lang="tsx">
  import { computed, nextTick, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ProcessApplicationManageService from '@service/process-application-manage';

  import type ExecutionDetailModel from '@model/application/execution-detail';
  import type ExecutionRecord from '@model/application/execution-record';

  import useMessage from '@hooks/use-message';

  import ExecutionDetail from './execution-detail.vue';
  import ExecutionRetryDialog from './execution-retry-dialog.vue';

  interface Props {
    isShow: boolean;
    applicationId?: string;
    applicationName?: string;
    riskId?: string;
    sceneId?: string;
  }
  interface Emits {
    (e: 'update:isShow', value: boolean): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  interface SearchValue {
    id: string;
    name: string;
  }
  interface SearchKey {
    id: string;
    name: string;
    values: SearchValue[];
  }

  const listRef = ref();
  const searchKey = ref<SearchKey[]>([]);
  const showDetail = ref(false);
  const activeTaskId = ref('');
  const showRetry = ref(false);
  const retrying = ref(false);
  const retryDetail = ref<ExecutionDetailModel | null>(null);

  const isShow = computed({
    get: () => props.isShow,
    set: (value: boolean) => emit('update:isShow', value),
  });

  const presetLabel = computed(() => (
    props.applicationId ? `${props.applicationName || ''}(${props.applicationId})` : ''
  ));
  const headerExtra = computed(() => {
    if (presetLabel.value) return presetLabel.value;
    if (props.riskId) return `${t('风险ID')}：${props.riskId}`;
    return '';
  });

  const statusText = (status: ExecutionRecord['status']) => ({
    success: t('执行成功'),
    failed: t('执行失败'),
    running: t('执行中'),
  }[status] || status);

  const triggerText = (trigger: ExecutionRecord['trigger_type']) => ({
    manual: t('手动'),
    auto: t('自动'),
    retry: t('重试'),
  }[trigger] || trigger);

  const openDetail = (row: ExecutionRecord) => {
    activeTaskId.value = row.task_id;
    showDetail.value = true;
  };

  const openRetry = async (row: ExecutionRecord) => {
    retryDetail.value = await ProcessApplicationManageService.fetchExecutionDetail({
      task_id: row.task_id,
    });
    showRetry.value = true;
  };

  const searchData = computed(() => [
    { id: 'task_id', name: t('任务ID') },
    { id: 'task_name', name: t('任务名称') },
    { id: 'application_name', name: t('套餐名称（ID）') },
    { id: 'risk_id', name: t('风险ID') },
    {
      id: 'trigger_type',
      name: t('触发方式'),
      children: [
        { id: 'manual', name: t('手动') },
        { id: 'auto', name: t('自动') },
        { id: 'retry', name: t('重试') },
      ],
    },
    {
      id: 'status',
      name: t('状态'),
      children: [
        { id: 'success', name: t('执行成功') },
        { id: 'failed', name: t('执行失败') },
        { id: 'running', name: t('执行中') },
      ],
    },
    { id: 'executor', name: t('执行人') },
  ]);

  const fieldValue = (id: string) => {
    const item = searchKey.value.find(key => key.id === id);
    return (item?.values || []).map(value => value.id).filter(Boolean).join(',');
  };

  const linkedFilterIds = ['trigger_type', 'status'];
  const linkedSearchParams = computed(() => ({
    trigger_type: fieldValue('trigger_type'),
    status: fieldValue('status'),
  }));
  let syncingTableFilter = false;

  const optionName = (fieldId: string, valueId: string) => {
    const field = searchData.value.find(item => item.id === fieldId);
    return field?.children?.find(item => item.id === valueId)?.name || valueId;
  };

  const upsertChip = (id: string, values: SearchValue[]) => {
    const index = searchKey.value.findIndex(item => item.id === id);
    if (!values.length) {
      if (index >= 0) searchKey.value.splice(index, 1);
      return;
    }
    const name = searchData.value.find(item => item.id === id)?.name || id;
    const chip = { id, name, values };
    if (index >= 0) {
      searchKey.value[index] = chip;
      return;
    }
    searchKey.value.push(chip);
  };

  const copyText = async (value: string, event: Event) => {
    event.stopPropagation();
    await navigator.clipboard.writeText(value);
    messageSuccess(t('已复制'));
  };

  const confirmRetry = async () => {
    if (!retryDetail.value) return;
    retrying.value = true;
    try {
      await ProcessApplicationManageService.retryExecution({
        task_id: retryDetail.value.task_id,
        reason: '',
      });
      messageSuccess(t('已发起重试'));
      showRetry.value = false;
      search();
    } finally {
      retrying.value = false;
    }
  };

  const enumFilter = (list: Array<{ label: string; value: string }>) => ({
    type: 'multiple' as const,
    showConfirmAndReset: true,
    resetValue: [],
    list,
  });

  const renderCopy = (value: string) => (
    value
      ? <button class="copy-btn" type="button" onClick={(event: Event) => copyText(value, event)}>
          <audit-icon type="copy" />
        </button>
      : null
  );

  const renderStatusMark = (status: ExecutionRecord['status']) => (
    status === 'running'
      ? <audit-icon class="rotate-loading status-loading" type="loading" />
      : (
        <span class={`status-dot is-${status}`}>
          <i class="status-dot-outer" />
          <i class="status-dot-inner" />
        </span>
      )
  );

  const renderStatus = (row: ExecutionRecord) => (
    <span class="record-status">
      {renderStatusMark(row.status)}
      {row.status === 'failed'
        ? (
          <span
            class="status-failed-text"
            v-bk-tooltips={row.error ? { content: row.error, extCls: 'execution-attempt-tip' } : undefined}
            onClick={() => openRetry(row)}>
            {statusText(row.status)}
          </span>
        )
        : <span>{statusText(row.status)}</span>}
      {row.status === 'failed'
        ? (
          <button
            class="status-retry"
            data-testid="execution-status-retry"
            type="button"
            onClick={() => openRetry(row)}>
            <audit-icon type="redo" />
          </button>
        )
        : null}
    </span>
  );

  const columns = computed(() => [
    {
      title: () => t('任务ID'),
      colKey: 'task_id',
      width: 150,
      cell: (_h: unknown, { row }: { row: ExecutionRecord }) => (
        <span class="copy-cell">
          <a class="task-link" onClick={() => openDetail(row)}>{row.task_id}</a>
          {renderCopy(row.task_id)}
        </span>
      ),
    },
    {
      title: () => t('任务名称'),
      colKey: 'task_name',
      ellipsis: true,
      cell: (_h: unknown, { row }: { row: ExecutionRecord }) => row.task_name || '--',
    },
    {
      title: () => t('套餐名称（ID）'),
      colKey: 'application_name',
      ellipsis: true,
      cell: (_h: unknown, { row }: { row: ExecutionRecord }) => `${row.application_name}(${row.application_id})`,
    },
    {
      title: () => t('风险ID'),
      colKey: 'risk_id',
      width: 170,
      cell: (_h: unknown, { row }: { row: ExecutionRecord }) => (
        <span class="copy-cell">
          <span>{row.risk_id || '--'}</span>
          {renderCopy(row.risk_id)}
        </span>
      ),
    },
    {
      title: () => t('触发方式'),
      colKey: 'trigger_type',
      width: 120,
      filter: enumFilter([
        { label: t('手动'), value: 'manual' },
        { label: t('自动'), value: 'auto' },
        { label: t('重试'), value: 'retry' },
      ]),
      cell: (_h: unknown, { row }: { row: ExecutionRecord }) => triggerText(row.trigger_type),
    },
    {
      title: () => t('开始时间'),
      colKey: 'started_at',
      width: 180,
      sorter: true,
      cell: (_h: unknown, { row }: { row: ExecutionRecord }) => row.started_at || '--',
    },
    {
      title: () => t('耗时'),
      colKey: 'duration',
      width: 120,
      sorter: true,
      cell: (_h: unknown, { row }: { row: ExecutionRecord }) => row.duration || '--',
    },
    {
      title: () => t('状态'),
      colKey: 'status',
      width: 160,
      filter: enumFilter([
        { label: t('执行成功'), value: 'success' },
        { label: t('执行失败'), value: 'failed' },
        { label: t('执行中'), value: 'running' },
      ]),
      cell: (_h: unknown, { row }: { row: ExecutionRecord }) => renderStatus(row),
    },
    {
      title: () => t('执行人'),
      colKey: 'executor',
      width: 120,
      ellipsis: true,
      cell: (_h: unknown, { row }: { row: ExecutionRecord }) => row.executor || '--',
    },
  ]);

  const dataSource = (params: Record<string, any>) => {
    const packageValue = fieldValue('application_name');
    const lockedApplicationId = packageValue && packageValue === presetLabel.value
      ? props.applicationId
      : '';
    return ProcessApplicationManageService.fetchExecutionRecords({
      page: params.page,
      page_size: params.page_size,
      sort: params.sort,
      task_id: fieldValue('task_id') || undefined,
      task_name: fieldValue('task_name') || undefined,
      application_id: lockedApplicationId || undefined,
      application_name: lockedApplicationId ? undefined : (packageValue || undefined),
      risk_id: fieldValue('risk_id') || undefined,
      executor: fieldValue('executor') || undefined,
      trigger_type: params.trigger_type || fieldValue('trigger_type') || undefined,
      status: params.status || fieldValue('status') || undefined,
      scene_id: props.sceneId || undefined,
    });
  };

  const search = () => {
    if (syncingTableFilter) return;
    nextTick(() => {
      listRef.value?.fetchData({
        page: 1,
        ...linkedSearchParams.value,
      });
    });
  };

  const handleTableFilterChange = (filters: Record<string, any>) => {
    syncingTableFilter = true;
    linkedFilterIds.forEach((id) => {
      if (!Object.prototype.hasOwnProperty.call(filters, id)) return;
      const raw = filters[id];
      const ids = (Array.isArray(raw) ? raw : (raw ? [raw] : []))
        .map(value => String(value))
        .filter(Boolean);
      upsertChip(id, ids.map(valueId => ({ id: valueId, name: optionName(id, valueId) })));
    });
    nextTick(() => {
      syncingTableFilter = false;
    });
  };

  const handleClearFilter = () => {
    searchKey.value = [];
    nextTick(() => {
      listRef.value?.fetchData({ page: 1 }, { resetSearch: true });
    });
  };

  const applyEntryFilter = () => {
    if (presetLabel.value) {
      searchKey.value = [{
        id: 'application_name',
        name: t('套餐名称（ID）'),
        values: [{ id: presetLabel.value, name: presetLabel.value }],
      }];
      return;
    }
    if (props.riskId) {
      searchKey.value = [{
        id: 'risk_id',
        name: t('风险ID'),
        values: [{ id: props.riskId, name: props.riskId }],
      }];
      return;
    }
    searchKey.value = [];
  };

  watch(() => props.isShow, (visible) => {
    if (!visible) return;
    applyEntryFilter();
    nextTick(() => {
      listRef.value?.fetchData({ page: 1 }, { resetSearch: true });
    });
  });
</script>
<style lang="postcss" scoped>
.execution-header-extra {
  padding-left: var(--audit-space-8);
  margin-left: var(--audit-space-8);
  font-size: var(--audit-font-size-sm);
  color: var(--audit-neutral-text-03);
  border-left: 1px solid var(--audit-neutral-border-01);
}

.execution-records {
  display: flex;
  flex: 1;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  padding: var(--audit-space-24);
  overflow: hidden;
  box-sizing: border-box;
}

.execution-search {
  flex-shrink: 0;
  width: 100%;
}

.execution-table {
  flex: 1;
  width: 100%;
  min-height: 0;
  overflow: hidden;

  :deep(.audit-tdesign-list),
  :deep(.bk-nested-loading) {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    overflow: hidden;
  }

  :deep(.audit-table-skeleton) {
    flex: 1;
    min-height: 0;
  }

  :deep(.audit-table-skeleton__body) {
    flex: 1 1 auto;
    min-height: 0;
  }

  :deep(.t-table) {
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  :deep(.t-table__content) {
    max-height: 100% !important;
    overflow: auto;
  }

  :deep(.tdesign-list-pagination) {
    flex-shrink: 0;
  }

  :deep(.t-table__affixed-header-wrap) {
    display: none;
    height: 0 !important;
    min-height: 0 !important;
    padding: 0;
    margin: 0;
    overflow: hidden;
  }

  :deep(.t-table thead tr),
  :deep(.t-table thead th) {
    background-color: var(--audit-neutral-bg-02);
  }

  :deep(.t-table thead th) {
    height: 42px;
    padding-top: 0;
    padding-bottom: 0;
    line-height: 42px;
  }
}

:deep(.copy-cell) {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: 100%;
}

:deep(.task-link) {
  color: var(--audit-brand-02);
  cursor: pointer;
}

:deep(.copy-btn) {
  display: inline-flex;
  padding: 0;
  font-size: 16px;
  color: var(--audit-brand-02);
  cursor: pointer;
  background: transparent;
  border: 0;
  visibility: hidden;
}

:deep(tr:hover .copy-btn) {
  visibility: visible;
}

:deep(.status-failed-text) {
  border-bottom: 1px dashed var(--audit-neutral-text-02);
  cursor: pointer;
}

:deep(.status-retry) {
  display: inline-flex;
  padding: 0;
  font-size: 16px;
  line-height: 1;
  color: var(--audit-brand-02);
  cursor: pointer;
  background: transparent;
  border: 0;
}

:deep(.record-status) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--audit-font-size-sm);
  line-height: 20px;
  color: var(--audit-neutral-text-02);
  white-space: nowrap;
}

:deep(.status-dot) {
  position: relative;
  display: inline-flex;
  width: 12px;
  height: 12px;
  flex: none;
  align-items: center;
  justify-content: center;
}

:deep(.status-dot-outer),
:deep(.status-dot-inner) {
  border-radius: 50%;
}

:deep(.status-dot-outer) {
  width: 12px;
  height: 12px;
  opacity: 0.2;
}

:deep(.status-dot-inner) {
  position: absolute;
  width: 6px;
  height: 6px;
}

:deep(.status-dot.is-failed .status-dot-outer) {
  background: rgba(234, 54, 54, 0.6);
}

:deep(.status-dot.is-failed .status-dot-inner) {
  background: var(--audit-danger-02);
}

:deep(.status-dot.is-success .status-dot-outer) {
  background: rgba(44, 175, 94, 0.6);
}

:deep(.status-dot.is-success .status-dot-inner) {
  background: var(--audit-success-02);
}

:deep(.status-loading) {
  font-size: 16px;
}
</style>
<style lang="postcss">
.execution-attempt-tip {
  max-width: 320px;
  line-height: 20px;
  word-break: break-all;
  white-space: normal;
}
</style>
