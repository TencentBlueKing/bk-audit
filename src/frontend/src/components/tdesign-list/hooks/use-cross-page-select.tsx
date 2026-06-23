import {
  computed,
  type ComputedRef,
  nextTick,
  type Ref,
  ref,
  watch,
} from 'vue';
import type { ComposerTranslation } from 'vue-i18n';

import CrossPageSelectHeader from '../components/cross-page-select-header.vue';

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
    if (!enabled.value || selectCheckMode.value !== 'all' || !currentPageKeys.value.length) {
      return;
    }
    mergeSelectedKeys(currentPageKeys.value);
  };

  const syncCurrentPageSelectionForPageMode = () => {
    if (!enabled.value || selectCheckMode.value !== 'page' || !currentPageKeys.value.length) {
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

  const handleListCheckChange = (type: string) => {
    if (!enabled.value) {
      return;
    }
    if (type === 'page') {
      selectCheckMode.value = 'page';
      mergeSelectedKeys(currentPageKeys.value);
      return;
    }
    if (type === 'pageCancel') {
      selectCheckMode.value = '';
      removeSelectedKeys(currentPageKeys.value);
      return;
    }
    if (type === 'all') {
      selectCheckMode.value = 'all';
      mergeSelectedKeys(currentPageKeys.value);
      return;
    }
    if (type === 'allCancel') {
      resetCrossPageSelection();
    }
  };

  const handleRowCheckboxChange = (row: Record<string, any>, checked: boolean) => {
    if (!enabled.value) {
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
    return selectedRowKeys.value.length > 0 || selectCheckMode.value === 'all';
  });

  const selectBannerText = computed(() => t('已选中{count}条数据，共有{total}条数据', {
    count: selectBannerSelectedCount.value,
    total: pagination.count,
  }));

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
        title: () => (
          <CrossPageSelectHeader
            disabled={!tableData.value.length}
            value={listCheckValue.value}
            onChange={handleListCheckChange}
          />
        ),
        cell: (_h: unknown, { row }: { row: Record<string, any> }) => {
          const key = getRowKeyValue(row);
          const checked = selectedRowKeys.value.includes(key);
          return (
            <bk-checkbox
              modelValue={checked}
              onChange={(val: boolean | string | number) => {
                handleRowCheckboxChange(row, Boolean(val));
              }}
            />
          );
        },
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

  return {
    tableAreaRef,
    selectBannerTop,
    selectBannerHeight,
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
