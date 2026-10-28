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
    :title="t('执行记录')"
    :width="1280">
    <div
      ref="panelRef"
      class="execution-records"
      data-testid="execution-records-panel">
      <bk-search-select
        ref="searchRef"
        v-model="searchKey"
        class="execution-search"
        clearable
        :data="searchData"
        :defaut-using-item="{ inputHtml: t('请选择') }"
        :placeholder="t('搜索 任务名称、任务ID、套餐名称（ID）、风险ID、状态、执行人')"
        unique-select
        @update:model-value="search" />
      <tdesign-list
        v-if="isShow"
        ref="listRef"
        class="execution-table"
        :columns="columns"
        :data-source="dataSource"
        :hide-filter-row-when-empty="true"
        :persist-table-filters="false"
        :table-max-height="tableMaxHeight"
        row-key="task_id"
        :search-params="linkedSearchParams"
        use-skeleton
        @clear-search="handleClearFilter"
        @filter-change="handleTableFilterChange" />
    </div>
  </audit-sideslider>
  <execution-detail
    v-model:is-show="showDetail"
    :risk-id="activeRiskId"
    :scene-id="sceneId"
    :task-id="activeTaskId"
    @retried="search" />
  <execution-retry-dialog
    v-model:is-show="showRetry"
    :detail="retryDetail"
    :loading="retrying"
    @confirm="confirmRetry" />
</template>
<script setup lang="tsx">
  import { computed, defineComponent, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import ProcessApplicationManageService from '@service/process-application-manage';

  import type ExecutionDetailModel from '@model/application/execution-detail';
  import { resolveExecutionDuration } from '@model/application/execution-protocol';
  import type ExecutionRecord from '@model/application/execution-record';

  import useMessage from '@hooks/use-message';

  import ExecutionDetail from './execution-detail.vue';
  import { openRiskDetail, openSopsTask } from './execution-links';
  import { executionErrorTip } from './execution-tips';
  import ExecutionRetryDialog from './execution-retry-dialog.vue';
  import { packageFilterOptions } from './package-filter-state';
  import PackageNameFilter from './package-name-filter.vue';
  import { useNow } from './use-now';

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
  const router = useRouter();
  const { messageSuccess } = useMessage();
  interface SearchValue {
    id: string;
    name: string;
  }
  interface SearchKey {
    id: string;
    name: string;
    type?: string;
    values?: SearchValue[];
  }

  const now = useNow(() => props.isShow);
  const listRef = ref();
  const panelRef = ref<HTMLElement | null>(null);
  const searchRef = ref<{ $el?: HTMLElement } | HTMLElement | null>(null);
  const tableMaxHeight = ref(360);
  let layoutObserver: ResizeObserver | undefined;
  let layoutRetry = 0;
  const watchedLayoutNodes = new WeakSet<Element>();
  const searchKey = ref<SearchKey[]>([]);
  const packageOptions = ref<Array<{ id: string | number; name: string }>>([]);
  const packageFilterList = computed(() => packageOptions.value.map(item => ({
    label: `${item.name}(${item.id})`,
    value: String(item.id),
  })));
  watch(packageFilterList, (list) => {
    packageFilterOptions.value = list;
  }, { immediate: true });
  const showDetail = ref(false);
  const activeTaskId = ref('');
  const activeRiskId = ref('');
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

  const statusText = (status: ExecutionRecord['status']) => ({
    success: t('执行成功'),
    failed: t('执行失败'),
    running: t('执行中'),
  }[status] || status);

  const triggerText = (trigger: ExecutionRecord['trigger_type']) => {
    const text: Record<string, string> = {
      manual: t('手动'),
      auto: t('自动'),
      test: t('测试'),
      retry: t('重试'),
    };
    return text[trigger] || '--';
  };

  const openDetail = (row: ExecutionRecord) => {
    activeTaskId.value = row.task_id;
    activeRiskId.value = row.risk_id;
    showDetail.value = true;
  };

  const openRetry = async (row: ExecutionRecord) => {
    retryDetail.value = await ProcessApplicationManageService.fetchExecutionDetail({
      task_id: row.task_id,
    });
    if (retryDetail.value && !retryDetail.value.risk_id) {
      retryDetail.value.risk_id = row.risk_id;
    }
    showRetry.value = true;
  };

  const searchData = computed(() => [
    { id: 'task_name', name: t('任务名称') },
    { id: 'task_id', name: t('任务ID') },
    {
      id: 'application_name',
      name: t('套餐名称（ID）'),
      multiple: true,
      children: packageOptions.value.map(item => ({
        id: String(item.id),
        name: `${item.name}(${item.id})`,
      })),
    },
    { id: 'risk_id', name: t('风险ID') },
    {
      id: 'trigger_type',
      name: t('触发方式'),
      multiple: true,
      children: [
        { id: 'manual', name: t('手动') },
        { id: 'auto', name: t('自动') },
        { id: 'test', name: t('测试') },
      ],
    },
    {
      id: 'status',
      name: t('状态'),
      multiple: true,
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

  const keywordValue = () => {
    const knownIds = new Set(searchData.value.map(item => item.id));
    return searchKey.value
      .filter(item => item.type === 'text' || !knownIds.has(item.id))
      .map(item => (item.name || item.id || '').trim())
      .filter(Boolean)
      .join(',');
  };

  const linkedFilterIds = ['application_name', 'trigger_type', 'status'];
  const linkedSearchParams = computed(() => ({
    application_name: fieldValue('application_name'),
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

  const confirmRetry = async () => {
    if (!retryDetail.value) return;
    retrying.value = true;
    try {
      await ProcessApplicationManageService.retryExecution({
        task_id: retryDetail.value.task_id,
        risk_id: retryDetail.value.risk_id,
      });
      messageSuccess(t('已发起重试'));
      showRetry.value = false;
      search();
    } finally {
      retrying.value = false;
    }
  };

  const enumFilter = (label: string, list: Array<{ label: string; value: string }>) => ({
    type: 'multiple' as const,
    label,
    showConfirmAndReset: true,
    resetValue: [],
    list,
  });

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
            v-bk-tooltips={row.error ? executionErrorTip(row.error) : undefined}
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
            v-bk-tooltips={{ content: t('重试') }}
            onClick={() => openRetry(row)}>
            <audit-icon type="redo" />
          </button>
        )
        : null}
    </span>
  );

  const overflowed = reactive<Record<string, boolean>>({});
  const syncOverflow = (event: MouseEvent, key: string) => {
    const el = event.currentTarget as HTMLElement;
    overflowed[key] = el.scrollWidth > el.clientWidth;
  };
  const OverflowText = defineComponent({
    name: 'OverflowText',
    props: {
      text: { type: String, default: '' },
      tipKey: { type: String, required: true },
      textClass: { type: String, default: 'cell-ellipsis' },
      link: { type: Boolean, default: false },
    },
    emits: ['pick'],
    setup(props, { emit }) {
      return () => {
        const content = props.text || '';
        const tip = {
          content,
          disabled: !content || !overflowed[props.tipKey],
          delay: 80,
          extCls: 'execution-attempt-tip',
        };
        const onEnter = (event: MouseEvent) => syncOverflow(event, props.tipKey);
        if (props.link) {
          return (
            <a
              class={props.textClass}
              v-bk-tooltips={tip}
              onMouseenter={onEnter}
              onClick={() => emit('pick')}>
              {content}
            </a>
          );
        }
        return (
          <span class={props.textClass} v-bk-tooltips={tip} onMouseenter={onEnter}>
            {content || '--'}
          </span>
        );
      };
    },
  });

  const LiveDuration = defineComponent({
    name: 'LiveDuration',
    props: {
      status: { type: String, default: '' },
      startedAt: { type: String, default: '' },
      fallback: { type: String, default: '' },
    },
    setup(props) {
      return () => resolveExecutionDuration(props.status, props.startedAt, props.fallback, now.value);
    },
  });

  const columns = computed(() => [
    {
      title: () => t('任务名称'),
      colKey: 'task_name',
      width: 281,
      minWidth: 281,
      ellipsis: true,
      cell: (_h: unknown, { row }: { row: ExecutionRecord }) => (
        <span class="copy-cell is-follow">
          <OverflowText
            text={row.task_name}
            tipKey={`name-${row.task_id}`}
            textClass="task-link copy-text"
            link
            onPick={() => openDetail(row)} />
          <button
            class="jump-btn"
            type="button"
            v-bk-tooltips={{ content: t('打开标准运维任务'), delay: 80 }}
            onClick={(event: Event) => {
              event.stopPropagation();
              openSopsTask(row.sops_task_url);
            }}>
            <audit-icon type="jump-link" />
          </button>
        </span>
      ),
    },
    {
      title: () => t('套餐名称（ID）'),
      colKey: 'application_name',
      width: 164,
      minWidth: 164,
      ellipsis: true,
      filter: (() => {
        const list = packageOptions.value.map(item => ({
          label: `${item.name}(${item.id})`,
          value: String(item.id),
        }));
        return {
          component: PackageNameFilter,
          label: t('套餐名称（ID）'),
          showConfirmAndReset: true,
          resetValue: [],
          list,
          props: { list },
        };
      })(),
      cell: (_h: unknown, { row }: { row: ExecutionRecord }) => (
        <OverflowText
          text={row.application_name ? `${row.application_name}(${row.application_id})` : ''}
          tipKey={`package-${row.task_id}`} />
      ),
    },
    {
      title: () => t('风险ID'),
      colKey: 'risk_id',
      width: 183,
      minWidth: 183,
      ellipsis: true,
      className: 'risk-id-cell',
      cell: (_h: unknown, { row }: { row: ExecutionRecord }) => (
        row.risk_id
          ? <OverflowText
              text={row.risk_id}
              tipKey={`risk-${row.task_id}`}
              textClass="task-link cell-ellipsis"
              link
              onPick={() => openRiskDetail(router, row.risk_id, props.sceneId)} />
          : '--'
      ),
    },
    {
      title: () => t('触发方式'),
      colKey: 'trigger_type',
      width: 104,
      minWidth: 104,
      filter: enumFilter(t('触发方式'), [
        { label: t('手动'), value: 'manual' },
        { label: t('自动'), value: 'auto' },
        { label: t('测试'), value: 'test' },
      ]),
      cell: (_h: unknown, { row }: { row: ExecutionRecord }) => triggerText(row.trigger_type),
    },
    {
      title: () => t('开始时间'),
      colKey: 'started_at',
      width: 156,
      minWidth: 156,
      className: 'started-at-cell',
      sorter: true,
      cell: (_h: unknown, { row }: { row: ExecutionRecord }) => (
        <span class="started-at-text">{row.started_at || '--'}</span>
      ),
    },
    {
      title: () => t('耗时'),
      colKey: 'duration',
      width: 95,
      minWidth: 95,
      className: 'duration-cell',
      sorter: true,
      cell: (_h: unknown, { row }: { row: ExecutionRecord }) => (
        <LiveDuration status={row.status} startedAt={row.started_at} fallback={row.duration} />
      ),
    },
    {
      title: () => t('状态'),
      colKey: 'status',
      width: 132,
      minWidth: 132,
      filter: enumFilter(t('状态'), [
        { label: t('执行成功'), value: 'success' },
        { label: t('执行失败'), value: 'failed' },
        { label: t('执行中'), value: 'running' },
      ]),
      cell: (_h: unknown, { row }: { row: ExecutionRecord }) => renderStatus(row),
    },
    {
      title: () => t('执行人'),
      colKey: 'executor',
      width: 117,
      minWidth: 117,
      ellipsis: true,
      cell: (_h: unknown, { row }: { row: ExecutionRecord }) => (
        <OverflowText text={row.executor} tipKey={`executor-${row.task_id}`} />
      ),
    },
  ]);

  const packageNameOf = (id: string) => {
    const matched = packageOptions.value.find(item => String(item.id) === id);
    if (matched?.name) return matched.name;
    if (props.applicationId && id === String(props.applicationId)) return props.applicationName || '';
    return '';
  };

  const dataSource = (params: Record<string, any>) => {
    const packageNames = fieldValue('application_name')
      .split(',')
      .map(id => packageNameOf(id))
      .filter(Boolean);
    return ProcessApplicationManageService.fetchExecutionRecords({
      page: params.page,
      page_size: params.page_size,
      sort: params.sort,
      task_id: fieldValue('task_id') || undefined,
      task_name: fieldValue('task_name') || undefined,
      application_name: packageNames.length ? packageNames.join(',') : undefined,
      risk_id: fieldValue('risk_id') || undefined,
      executor: fieldValue('executor') || undefined,
      keyword: keywordValue() || undefined,
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
    if (props.applicationId) {
      searchKey.value = [{
        id: 'application_name',
        name: t('套餐名称（ID）'),
        values: [{ id: String(props.applicationId), name: presetLabel.value }],
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

  const syncTableMaxHeight = () => {
    const panel = panelRef.value;
    if (!panel) return;
    const searchTarget = searchRef.value;
    const searchEl = (searchTarget instanceof HTMLElement ? searchTarget : searchTarget?.$el)
      || panel.querySelector('.execution-search');
    if (!searchEl) return;
    const panelRect = panel.getBoundingClientRect();
    if (panelRect.width < 1 || panelRect.height < 1) return;
    const tableRoot = panel.querySelector('.execution-table');
    if (tableRoot && layoutObserver && !watchedLayoutNodes.has(tableRoot)) {
      watchedLayoutNodes.add(tableRoot);
      layoutObserver.observe(tableRoot);
    }
    const tableEl = panel.querySelector('.t-table__content');
    const tableTop = tableEl?.getBoundingClientRect().top ?? 0;
    if (!tableEl || tableTop < panelRect.top) {
      if (layoutRetry < 40) {
        layoutRetry += 1;
        window.setTimeout(syncTableMaxHeight, 50);
      }
      return;
    }
    layoutRetry = 0;
    const paddingBottom = Number.parseFloat(getComputedStyle(panel).paddingBottom) || 0;
    const paginationEl = panel.querySelector('.tdesign-list-pagination');
    const paginationHeight = paginationEl?.getBoundingClientRect().height || 56;
    const paginationMargin = paginationEl
      ? (Number.parseFloat(getComputedStyle(paginationEl).marginTop) || 0)
      : 16;
    const available = panelRect.bottom - tableTop - paginationHeight - paginationMargin - paddingBottom;
    if (available > 0 && Math.abs(available - tableMaxHeight.value) > 1) {
      tableMaxHeight.value = Math.floor(available);
    }
    panel.style.setProperty('--execution-table-height', `${tableMaxHeight.value}px`);
  };

  const watchPanelLayout = () => {
    layoutObserver?.disconnect();
    layoutObserver = undefined;
    const panel = panelRef.value;
    if (!panel) return;
    layoutObserver = new ResizeObserver(() => syncTableMaxHeight());
    layoutObserver.observe(panel);
    const table = panel.querySelector('.execution-table');
    if (table) layoutObserver.observe(table);
  };

  const loadPackageOptions = () => {
    ProcessApplicationManageService.fetchApplicationsAll({
      scene_id: props.sceneId || undefined,
      has_execution_records: true,
    }).then((data) => {
      const list = Array.isArray(data) ? data : [];
      if (
        props.applicationId
        && props.applicationName
        && !list.some(item => String(item.id) === String(props.applicationId))
      ) {
        list.unshift({
          id: props.applicationId,
          name: props.applicationName,
          sops_template_id: 0,
          is_enabled: true,
        });
      }
      packageOptions.value = list;
    })
      .catch(() => {
        packageOptions.value = [];
      });
  };

  watch(() => props.isShow, (visible) => {
    if (!visible) return;
    loadPackageOptions();
    applyEntryFilter();
    nextTick(() => {
      watchPanelLayout();
      syncTableMaxHeight();
      listRef.value?.fetchData({ page: 1 }, { resetSearch: true });
    });
  });

  watch(panelRef, () => {
    watchPanelLayout();
    syncTableMaxHeight();
  });

  onMounted(() => {
    window.addEventListener('resize', syncTableMaxHeight);
  });

  onBeforeUnmount(() => {
    layoutObserver?.disconnect();
    window.removeEventListener('resize', syncTableMaxHeight);
  });
</script>
<style lang="postcss" scoped>
.execution-records {
  display: flex;
  flex: none;
  flex-direction: column;
  height: calc(100vh - 52px);
  max-height: calc(100vh - 52px);
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
  margin-top: var(--audit-space-16);
  overflow: hidden;
  border: 0;

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
    flex: none;
    width: 100%;
    min-height: 0;
    overflow: hidden;
  }

  :deep(.t-table__content) {
    height: var(--execution-table-height, 360px);
    max-height: var(--execution-table-height, 360px);
    overflow: auto;
  }

  :deep(.t-table table) {
    width: 100% !important;
    min-width: 100% !important;
    table-layout: fixed;
  }

  :deep(.t-table__empty-row) {
    height: calc(var(--execution-table-height, 360px) - 43px);
  }

  :deep(.t-table__empty-row > td) {
    padding: 0;
  }

  :deep(.t-table__empty) {
    height: 100%;
  }

  :deep(.t-table__empty .bk-exception) {
    display: flex !important;
    width: 100% !important;
    height: 100% !important;
    min-height: 0 !important;
    padding-top: 0 !important;
    box-sizing: border-box;
    align-items: center;
    justify-content: center;
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
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-width: 0;
}

:deep(.copy-cell.is-follow) {
  display: inline-flex;
  width: auto;
  max-width: 100%;
}

:deep(.copy-cell.is-follow .copy-text) {
  flex: 0 1 auto;
}

:deep(.risk-id-cell .task-link) {
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.duration-cell) {
  white-space: nowrap;
}

:deep(.copy-text),
:deep(.cell-ellipsis) {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.cell-ellipsis) {
  display: block;
}

:deep(.task-link) {
  color: var(--audit-brand-02);
  cursor: pointer;
}

:deep(.jump-btn) {
  display: inline-flex;
  flex: 0 0 auto;
  padding: 0;
  font-size: 16px;
  color: var(--audit-brand-02);
  cursor: pointer;
  background: transparent;
  border: 0;
  visibility: hidden;
}

:deep(tr:hover .jump-btn) {
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

:deep(.started-at-cell),
:deep(.started-at-text) {
  white-space: nowrap;
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

.execution-error-tip-body {
  max-height: 240px;
  margin-right: -10px;
  padding-right: 8px;
  overflow-x: hidden;
  overflow-y: auto;
  word-break: break-all;
  white-space: normal;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.45) transparent;
}

.execution-error-tip-body::-webkit-scrollbar {
  width: 6px;
}

.execution-error-tip-body::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.45);
  border-radius: 3px;
}

.execution-error-tip-body::-webkit-scrollbar-track {
  background: transparent;
}
</style>
