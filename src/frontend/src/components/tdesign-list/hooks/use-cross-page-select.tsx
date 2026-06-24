import {
  computed,
  type ComputedRef,
  nextTick,
  type Ref,
  ref,
  watch,
} from 'vue';
import type { ComposerTranslation } from 'vue-i18n';

import { RISK_EXPORT_ASYNC_THRESHOLD } from '@hooks/use-risk-export-limit';

import CrossPageSelectHeader from '../components/cross-page-select-header.vue';
import SelectCheckboxLoading from '../components/select-checkbox-loading.vue';

const renderSelectSlotContent = (loading: boolean, checkboxNode: any) => (
  loading ? <SelectCheckboxLoading /> : checkboxNode
);

export type SelectCheckMode = '' | 'page' | 'all';

export interface CrossPageSelectPagination {
  count: number;
}

export interface UseCrossPageSelectOptions {
  enabled: ComputedRef<boolean>;
  selectedRowKeys: Ref<Array<string | number>>;
  tableData: ComputedRef<Array<Record<string, any>>>;
  getRowKeyValue: (row: Record<string, any>) => string | number;
  pagination: CrossPageSelectPagination;
  dataSource: (params: Record<string, any>) => Promise<{ results?: Array<Record<string, any>> }>;
  buildFetchParams: () => Record<string, any> | null;
  t: ComposerTranslation;
}

export function useCrossPageSelect(options: UseCrossPageSelectOptions) {
  const {
    enabled,
    selectedRowKeys,
    tableData,
    getRowKeyValue,
    pagination,
    dataSource,
    buildFetchParams,
    t,
  } = options;

  const selectCheckMode = ref<SelectCheckMode>('');
  const isSelectAllLoading = ref(false);
  const selectAllLoadingMode = ref<'select' | 'cancel'>('select');
  const selectBannerTop = ref(44);
  const selectBannerHeight = ref(32);
  const tableAreaRef = ref<HTMLElement>();
  let bannerPositionTimer: ReturnType<typeof setTimeout> | null = null;

  const currentPageKeys = computed(() => tableData.value.map(row => getRowKeyValue(row)));

  const isCurrentPageAllSelected = computed(() => {
    const keys = currentPageKeys.value;
    if (!keys.length) {
      return false;
    }
    return keys.every(key => selectedRowKeys.value.includes(key));
  });

  const listCheckValue = computed(() => {
    if (selectCheckMode.value === 'all') {
      return 'all';
    }
    if (selectCheckMode.value === 'page' || isCurrentPageAllSelected.value) {
      return 'page';
    }
    return '';
  });

  const resetCrossPageSelection = () => {
    selectCheckMode.value = '';
    selectedRowKeys.value = [];
  };

  const mergeSelectedKeys = (keys: Array<string | number>) => {
    selectedRowKeys.value = Array.from(new Set([...selectedRowKeys.value, ...keys]));
  };

  const removeSelectedKeys = (keys: Array<string | number>) => {
    const removeKeySet = new Set(keys);
    selectedRowKeys.value = selectedRowKeys.value.filter(key => !removeKeySet.has(key));
  };

  const syncCurrentPageSelectionForAllMode = () => {
    if (!enabled.value || isSelectAllLoading.value || selectCheckMode.value !== 'all' || !currentPageKeys.value.length) {
      return;
    }
    mergeSelectedKeys(currentPageKeys.value);
  };

  const syncCurrentPageSelectionForPageMode = () => {
    if (!enabled.value || isSelectAllLoading.value || selectCheckMode.value !== 'page' || !currentPageKeys.value.length) {
      return;
    }
    mergeSelectedKeys(currentPageKeys.value);
  };

  const preservePageSelectionForPageSizeChange = () => {
    if (!enabled.value) {
      return;
    }
    if (selectCheckMode.value === 'page' || isCurrentPageAllSelected.value) {
      selectCheckMode.value = 'page';
    }
  };

  const waitForSelectAllLoadingPaint = async () => {
    await nextTick();
    await new Promise<void>((resolve) => {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => resolve());
      });
    });
  };

  const runSelectColumnLoading = async (task: () => void | Promise<void>, mode: 'select' | 'cancel' = 'select') => {
    isSelectAllLoading.value = true;
    selectAllLoadingMode.value = mode;
    await waitForSelectAllLoadingPaint();
    try {
      await task();
      await nextTick();
    } finally {
      isSelectAllLoading.value = false;
    }
  };

  const isRowSelectLoading = (key: string | number) => (
    isSelectAllLoading.value && currentPageKeys.value.includes(key)
  );

  const renderRowSelectCell = (row: Record<string, any>) => {
    const key = getRowKeyValue(row);
    const loading = isRowSelectLoading(key);
    const checked = selectedRowKeys.value.includes(key);
    return (
      <span class="tdesign-list-select-slot">
        {renderSelectSlotContent(
          loading, (
          <bk-checkbox
            modelValue={checked}
            onChange={(val: boolean | string | number) => {
              handleRowCheckboxChange(row, Boolean(val));
            }}
          />
          ),
        )}
      </span>
    );
  };

  const handleListCheckChange = async (type: string) => {
    if (!enabled.value || isSelectAllLoading.value) {
      return;
    }
    if (type === 'page') {
      await runSelectColumnLoading(() => {
        mergeSelectedKeys(currentPageKeys.value);
        selectCheckMode.value = 'page';
      }, 'select');
      return;
    }
    if (type === 'pageCancel') {
      await runSelectColumnLoading(() => {
        removeSelectedKeys(currentPageKeys.value);
        selectCheckMode.value = '';
      }, 'cancel');
      return;
    }
    if (type === 'all') {
      await runSelectColumnLoading(async () => {
        if (pagination.count > 0 && pagination.count <= RISK_EXPORT_ASYNC_THRESHOLD) {
          const keys = await fetchSelectAllRowKeys();
          selectedRowKeys.value = keys;
        } else {
          mergeSelectedKeys(currentPageKeys.value);
        }
        selectCheckMode.value = 'all';
      }, 'select');
      return;
    }
    if (type === 'allCancel') {
      await runSelectColumnLoading(() => {
        resetCrossPageSelection();
      }, 'cancel');
    }
  };

  const handleRowCheckboxChange = (row: Record<string, any>, checked: boolean) => {
    if (!enabled.value || isSelectAllLoading.value) {
      return;
    }
    const key = getRowKeyValue(row);
    if (checked) {
      mergeSelectedKeys([key]);
      return;
    }
    removeSelectedKeys([key]);
    if (selectCheckMode.value === 'all' || selectCheckMode.value === 'page') {
      selectCheckMode.value = '';
    }
  };

  const handleCrossPageSelectChange = () => {
    if (!enabled.value) {
      return;
    }
    if (selectCheckMode.value === 'all' && !isCurrentPageAllSelected.value) {
      selectCheckMode.value = '';
      return;
    }
    if (selectCheckMode.value === 'page' && !isCurrentPageAllSelected.value) {
      selectCheckMode.value = '';
    }
  };

  const getEffectiveSelectedCount = () => {
    if (enabled.value && selectCheckMode.value === 'all') {
      return pagination.count;
    }
    return selectedRowKeys.value.length;
  };

  const selectBannerSelectedCount = computed(() => getEffectiveSelectedCount());

  const showSelectAllBanner = computed(() => {
    if (!enabled.value || !pagination.count) {
      return false;
    }
    if (isSelectAllLoading.value) {
      return true;
    }
    return selectedRowKeys.value.length > 0 || selectCheckMode.value === 'all';
  });

  const selectBannerText = computed(() => {
    if (isSelectAllLoading.value) {
      return selectAllLoadingMode.value === 'cancel'
        ? t('正在取消选择...')
        : t('正在全选...');
    }
    return t('已选中{count}条数据，共有{total}条数据', {
      count: selectBannerSelectedCount.value,
      total: pagination.count,
    });
  });

  const selectAllBanner = computed(() => {
    if (!showSelectAllBanner.value) {
      return undefined;
    }
    return () => <div class="tdesign-list-select-banner-placeholder" />;
  });

  const enhanceSelectColumn = (cols: any[]) => {
    if (!enabled.value) {
      return cols;
    }
    return cols.map((column) => {
      if (column.colKey !== 'row-select' || column.type !== 'multiple') {
        return column;
      }
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { type, ...restColumn } = column;
      return {
        ...restColumn,
        width: column.width || 80,
        align: 'left',
        className: 'tdesign-list-select-col',
        thClassName: 'tdesign-list-select-col',
        cellClassName: 'tdesign-list-select-col',
        title: () => (
          <CrossPageSelectHeader
            disabled={!tableData.value.length}
            loading={isSelectAllLoading.value}
            value={listCheckValue.value}
            onChange={handleListCheckChange}
          />
        ),
        cell: (_h: unknown, { row }: { row: Record<string, any> }) => renderRowSelectCell(row),
      };
    });
  };

  /** 按表头 + 筛选行高度计算，避免随每页条数/滚动导致 getBoundingClientRect 偏移 */
  const getBannerTopInArea = (area: HTMLElement) => {
    const table = area.querySelector('.t-table');
    const scrollContent = table?.querySelector('.t-table__content--scrollable')
      || table?.querySelector('.t-table__content');
    if (!scrollContent) {
      return { top: 44, height: 32 };
    }

    const areaRect = area.getBoundingClientRect();
    const contentRect = scrollContent.getBoundingClientRect();
    let top = Math.round(contentRect.top - areaRect.top);

    const header = scrollContent.querySelector('.t-table__header') as HTMLElement | null;
    const filterRow = scrollContent.querySelector('.t-table__filter-row') as HTMLElement | null;
    if (header) {
      top += header.offsetHeight;
    }
    if (filterRow?.offsetHeight) {
      top += filterRow.offsetHeight;
    }

    const fullRow = scrollContent.querySelector('.t-table__body tr.t-table__first-full-row') as HTMLElement | null;
    const height = fullRow?.offsetHeight || 32;

    return { top, height };
  };

  const applySelectBannerPosition = (retries = 0) => {
    const area = tableAreaRef.value;
    if (!enabled.value || !showSelectAllBanner.value || !area) {
      return;
    }
    const { top, height } = getBannerTopInArea(area);
    if (top > 0) {
      selectBannerTop.value = top;
      selectBannerHeight.value = height;
      return;
    }
    if (retries > 0) {
      bannerPositionTimer = setTimeout(() => applySelectBannerPosition(retries - 1), 60);
    }
  };

  const updateSelectBannerPosition = (retries = 4) => {
    if (!enabled.value || !showSelectAllBanner.value || !tableAreaRef.value) {
      return;
    }
    if (bannerPositionTimer) {
      clearTimeout(bannerPositionTimer);
      bannerPositionTimer = null;
    }
    nextTick(() => {
      requestAnimationFrame(() => {
        applySelectBannerPosition(retries);
      });
    });
  };

  const fetchSelectAllRowKeys = async (maxCount?: number) => {
    const total = pagination.count;
    if (!total) {
      return [];
    }
    const params = buildFetchParams();
    if (!params) {
      return [];
    }

    const targetCount = maxCount === undefined ? total : Math.min(total, maxCount);
    const data = await dataSource({
      ...params,
      page: 1,
      page_size: targetCount,
    });
    const results = data?.results || [];
    return results
      .map((row: Record<string, any>) => getRowKeyValue(row))
      .slice(0, targetCount);
  };

  const resolveSelectedRowKeys = async (options?: { maxCount?: number }) => {
    if (!enabled.value || selectCheckMode.value !== 'all') {
      return [...selectedRowKeys.value];
    }
    return fetchSelectAllRowKeys(options?.maxCount);
  };

  const resolveExportSelection = async () => {
    const keys = await resolveSelectedRowKeys();
    const isSelectAll = enabled.value && selectCheckMode.value === 'all';
    return {
      keys,
      truncated: false,
      total: pagination.count,
      isSelectAll,
    };
  };

  const getSelectionMeta = () => ({
    mode: enabled.value ? selectCheckMode.value : '' as SelectCheckMode,
    count: getEffectiveSelectedCount(),
    total: pagination.count,
    isSelectAll: enabled.value && selectCheckMode.value === 'all',
  });

  watch(tableData, () => {
    syncCurrentPageSelectionForAllMode();
    syncCurrentPageSelectionForPageMode();
    if (showSelectAllBanner.value) {
      updateSelectBannerPosition();
    }
  });

  watch(showSelectAllBanner, (visible) => {
    if (visible) {
      updateSelectBannerPosition();
    }
  });

  watch(isSelectAllLoading, (loading) => {
    if (loading || showSelectAllBanner.value) {
      updateSelectBannerPosition();
    }
  });

  return {
    tableAreaRef,
    selectBannerTop,
    selectBannerHeight,
    isSelectAllLoading,
    showSelectAllBanner,
    selectBannerText,
    selectAllBanner,
    enhanceSelectColumn,
    resetCrossPageSelection,
    preservePageSelectionForPageSizeChange,
    handleCrossPageSelectChange,
    updateSelectBannerPosition,
    resolveSelectedRowKeys,
    resolveExportSelection,
    getSelectionMeta,
  };
}
