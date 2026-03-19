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
  <div
    ref="rootRef"
    class="audit-tdesign-list"
    :class="[{ 'is-loading': isLoading }]">
    <bk-loading
      :loading="isLoading"
      style="z-index: 9999;">
      <div
        v-if="settings.length > 0"
        class="setings">
        <bk-popover
          ref="popoverRef"
          placement="bottom-end"
          theme="light"
          trigger="click"
          width="500"
          @show="handlePopoverShow">
          <template #content>
            <div class="column-popover">
              <div class="column-popover-header">
                <div class="column-popover-title">
                  {{ t('表格设置') }}
                </div>
                <bk-button
                  class="column-popover-close"
                  text
                  @click="closeColumnPopover">
                  <audit-icon type="close" />
                </bk-button>
              </div>
              <div class="column-popover-section">
                <div class="column-popover-section-header">
                  <div class="column-popover-section-title">
                    {{ t('字段显示设置') }}
                  </div>
                  <bk-checkbox
                    :model-value="isCheckAll"
                    @change="handleCheckAllChange">
                    {{ t('全选') }}
                  </bk-checkbox>
                </div>
                <bk-checkbox-group
                  :model-value="tempVisibleColumnKeys"
                  @change="handleTempKeysChange">
                  <div class="column-popover-grid">
                    <bk-checkbox
                      v-for="col in allColumnKeys"
                      :key="col"
                      class="column-popover-grid-item"
                      :label="col">
                      {{ columnTitleForKey(col) }}
                    </bk-checkbox>
                  </div>
                </bk-checkbox-group>
              </div>
              <div class="column-popover-footer">
                <bk-button
                  size="small"
                  theme="primary"
                  @click="handleColumnConfirm">
                  {{ t('确认') }}
                </bk-button>
                <bk-button
                  class="ml16"
                  size="small"
                  @click="handleColumnCancel">
                  {{ t('取消') }}
                </bk-button>
              </div>
            </div>
          </template>
          <audit-icon
            class="setting-btn-icon"
            type="setting" />
        </bk-popover>
      </div>
      <primary-table
        ref="tableRef"
        v-model:selected-row-keys="selectedRowKeys"
        :bordered="border"
        class="tdesign-list"
        :columns="tableColumns"
        :data="tableData"
        :height="height"
        :max-height="effectiveTableMaxHeight"
        :row-key="rowKey as any"
        v-bind="$attrs"
        @filter-change="handleFilterChange"
        @select-change="handleSelectChange"
        @sort-change="handleSortChange">
        <template
          v-for="(slotData, name) in $slots"
          #[name]="slotProps">
          <slot
            :name="name"
            v-bind="slotProps" />
        </template>
        <template #empty>
          <slot
            v-if="slot.empty"
            name="empty" />
          <bk-exception
            v-else-if="isSearching && needEmptySearchTip"
            scene="part"
            style="height: 280px;padding-top: 40px;"
            type="search-empty">
            <div>
              <div style="color: #63656e;">
                {{ t('搜索结果为空') }}
              </div>
              <div
                v-if="!isNeedHideClearSearchTip"
                style="margin-top: 8px; color: #979ba5;">
                {{ t('可以尝试调整关键词') }} {{ t('或') }}
                <bk-button
                  text
                  theme="primary"
                  @click="handleClearSearch">
                  {{ t('清空搜索条件') }}
                </bk-button>
              </div>
            </div>
          </bk-exception>
          <bk-exception
            v-else
            scene="part"
            style="height: 280px;padding-top: 40px;color: #63656e;"
            type="empty">
            {{ t('暂无数据') }}
          </bk-exception>
        </template>
      </primary-table>
      <div
        v-if="pagination.count > 0"
        class="tdesign-list-pagination">
        <bk-pagination
          v-model="pagination.current"
          :align="pagination.align"
          :count="pagination.count"
          :layout="pagination.layout"
          :limit="pagination.limit"
          :limit-list="pagination.limitList"
          location="left"
          @change="handlePageChange"
          @limit-change="handlePageLimitChange" />
      </div>
    </bk-loading>
  </div>
</template>
<script setup lang='tsx'>
  import {
    computed,
    nextTick,
    onBeforeUnmount,
    onMounted,
    reactive,
    type Ref,
    ref,
    useAttrs,
    useSlots,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import useEventBus from '@hooks/use-event-bus';
  import useRecordPage from '@hooks/use-record-page';
  import useRequest from '@hooks/use-request';
  import useUrlSearch from '@hooks/use-url-search';

  import { PrimaryTable } from '@blueking/tdesign-ui';

  import {
    getOffset,
  } from '@utils/assist';
  import type { IRequestResponsePaginationData } from '@utils/request';

  import '@blueking/tdesign-ui/vue3/index.css';

  export interface IPagination {
    count: number;
    current: number;
    limit: number;
    limitList: Array<number>;
    align: string,
    layout: Array<string>;
    location: string;
  }

  interface Props {
    columns: any[],
    reverseSortFields?: Array<string>, // 颠倒排序的字段数组
    secondarySortField?: string, // 次级排序字段
    dataSource: (params: any) => Promise<IRequestResponsePaginationData<any>>,
    paginationValidator?: (pagination: IPagination) => boolean,
    isNeedHideClearSearchTip?: boolean,
    border?: boolean,
    needEmptySearchTip?: boolean,
    height?: number | string,
    noUseRresults?: boolean;
    settings?: any[];
    rowKey?: string | ((row: any) => string | number);
    /** 表格最大高度，传入时优先使用，不传则使用内部计算值 */
    tableMaxHeight?: number | string;
    /** 搜索参数（含 event_filters 等），排序时合并以保留其他参数 */
    searchParams?: Record<string, any>;
  }

  interface Emits {
    (e: 'requestSuccess', value: any): void,
    (e: 'clearSearch'): void,
    (e: 'on-setting-change', value: any): void,
  }
  interface Exposes {
    fetchData: (params: Record<string, any>) => void,
    loading: Ref<boolean>,
    refreshList: () => void,
    getListData: () => Array<Record<string, any>>,
    getSelection: () => void
    initTableHeight: () => void,
    listDataUnshift: (data: Record<string, any>) => void,
    initListData: (data: any, key: string) => void
    initData: () => void
  }

  const props = withDefaults(defineProps<Props>(), {
    reverseSortFields: () => [],
    secondarySortField: '',
    needEmptySearchTip: true,
    paginationValidator: undefined,
    border: false,
    isNeedHideClearSearchTip: false,
    height: 'auto',
    noUseRresults: false,
    settings: () => [],
    rowKey: 'id',
    tableMaxHeight: undefined,
    searchParams: undefined,
  });
  const emits = defineEmits<Emits>();
  const attrs = useAttrs();

  // 从 $attrs 中获取 row-key（kebab-case），如果没有则使用 props.rowKey
  const rowKey = computed(() => (attrs['row-key'] as string | ((row: any) => string | number)) || props.rowKey);

  // 管理选中的行键
  const selectedRowKeys = ref<(string | number)[]>([]);

  // 处理选择变更事件
  const handleSelectChange = (value: (string | number)[]) => {
    selectedRowKeys.value = value || [];
  };

  // 列控制相关状态
  // 排除：选择列、操作列（操作列固定显示，不可配置）
  const allColumnKeys = computed(() => props.columns
    .filter(column => column.colKey
      && column.colKey !== 'row-select'
      && column.colKey !== 'action')
    .map(column => column.colKey));

  // 从 localStorage 读取保存的设置
  const getSavedSettings = () => {
    // 如果父组件传入了 settings，使用 settings 作为默认可见列
    if (props.settings && props.settings.length > 0) {
      return [...props.settings];
    }
    // 否则默认显示所有列
    return [...allColumnKeys.value];
  };

  const visibleColumnKeys = ref<string[]>([]);
  // 弹窗中的临时选择
  const tempVisibleColumnKeys = ref<string[]>([]);

  // 初始化可见列
  const initVisibleColumns = () => {
    const savedSettings = getSavedSettings();
    visibleColumnKeys.value = savedSettings;
    tempVisibleColumnKeys.value = [...savedSettings];
  };

  // 监听 settings 变化，更新可见列
  watch(() => props.settings, () => {
    initVisibleColumns();
  }, { immediate: true, deep: true });

  // 监听 allColumnKeys 变化：新增列（如 event_data.xxx）默认勾选
  watch(allColumnKeys, (newKeys) => {
    if (visibleColumnKeys.value.length === 0) {
      initVisibleColumns();
    } else {
      // 将新增的列（如 event_filters 动态列）合并进可见列，默认勾选
      const currentKeys = new Set(visibleColumnKeys.value);
      const addedKeys = newKeys.filter((key: string) => !currentKeys.has(key));
      if (addedKeys.length > 0) {
        visibleColumnKeys.value = [...visibleColumnKeys.value, ...addedKeys];
        tempVisibleColumnKeys.value = [...visibleColumnKeys.value];
      }
    }
  }, { immediate: true });
  // 控制popover显示
  const popoverRef = ref();
  const columnTitleForKey = (col: string) => {
    const column = props.columns.find((item: any) => item.colKey === col);
    if (typeof column?.title === 'function') {
      return column.title();
    }
    return column?.title || col;
  };
  const closeColumnPopover = () => {
    popoverRef.value?.hide?.();
  };

  const isCheckAll = computed(() => tempVisibleColumnKeys.value.length === allColumnKeys.value.length);

  // 移除列的 fixed 属性（loading 时使用）
  const removeFixed = (col: any) => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { fixed, ...rest } = col;
    return rest;
  };

  // 实际传给表格的列：选择列 + 当前勾选的列 + 固定的操作列
  const tableColumns = computed(() => {
    if (props.settings.length === 0) {
      // loading 时移除所有列的 fixed 属性，避免固定列 z-index 穿透 loading 遮罩
      if (isLoading.value) {
        return props.columns.map(removeFixed);
      }
      return props.columns;
    }

    // 过滤显示的列
    const filteredColumns = props.columns.filter((column) => {
      // 选择列 / 操作列 / event_filters 动态列 始终显示
      if (!column.colKey || column.colKey === 'row-select' || column.colKey === 'action') {
        return true;
      }
      if (column.colKey.startsWith('event_data.')) {
        return true;
      }
      return visibleColumnKeys.value.includes(column.colKey);
    });

    // loading 时移除所有列的 fixed 属性，避免固定列 z-index 穿透 loading 遮罩
    if (isLoading.value) {
      return filteredColumns.map(removeFixed);
    }
    return filteredColumns;
  });

  const handlePopoverShow = () => {
    // 打开 popover 时，初始化临时选择为当前选择
    tempVisibleColumnKeys.value = [...visibleColumnKeys.value];
  };

  const handleColumnConfirm = () => {
    visibleColumnKeys.value = [...tempVisibleColumnKeys.value];
    // 触发设置变更事件，让父组件保存设置
    emits('on-setting-change', {
      checked: visibleColumnKeys.value,
      fields: allColumnKeys.value.map(key => ({
        field: key,
        label: columnTitleForKey(key),
      })),
      size: 'medium',
    });
    popoverRef.value?.hide();
  };

  const handleColumnCancel = () => {
    // 取消时，恢复临时选择为当前选择
    tempVisibleColumnKeys.value = [...visibleColumnKeys.value];
    popoverRef.value?.hide();
  };

  const handleCheckAllChange = (checked: boolean) => {
    tempVisibleColumnKeys.value = checked ? [...allColumnKeys.value] : [];
  };

  const handleTempKeysChange = (keys: string[]) => {
    tempVisibleColumnKeys.value = keys;
  };
  const isUnload = ref(true);
  const { getRecordPageParams, removePageParams } = useRecordPage;
  const { on, off } = useEventBus();
  const slot = useSlots();
  const tableRef = ref();
  const rootRef = ref();
  const { t } = useI18n();
  const internalTableMaxHeight = ref<number | string>('auto');
  const effectiveTableMaxHeight = computed(() => (
    props.tableMaxHeight !== undefined && props.tableMaxHeight !== null
      ? props.tableMaxHeight
      : internalTableMaxHeight.value
  ));
  const pagination = reactive<IPagination>({
    count: 0,
    current: 1,
    limit: 10,
    limitList: [10, 20, 50, 100, 500],
    align: 'left',
    layout: ['total', 'limit', 'list'],
    location: 'left',
  });

  let paramsMemo: Record<string, any> = {};
  const isSearching = ref(false);

  let isReady = false;
  const {
    getSearchParams,
    replaceSearchParams,
  } = useUrlSearch();

  const {
    run,
    data: listData,
    refresh: refreshList,
    loading: isLoading,
    cancel,
  // eslint-disable-next-line vue/no-setup-props-destructure
  } = useRequest(props.dataSource, {
    defaultValue: {
      results: [],
      page: 1,
      num_pages: 1,
      total: 0,
    },
    onSuccess(data) {
      emits('requestSuccess', data);
      isUnload.value = false;
      isLoading.value = false;
      // 确保分页总数正确更新
      if (data && typeof data.total === 'number') {
        pagination.count = data.total;
      }
    },
  });

  // 计算表格数据，处理 noUseRresults 的情况
  const tableData = computed(() => {
    if (props.noUseRresults) {
      // 当 noUseRresults 为 true 时，如果 listData 是数组则直接返回，否则返回空数组
      return Array.isArray(listData.value) ? listData.value : [];
    }
    // 当 noUseRresults 为 false 时，返回 listData.results
    return listData.value?.results || [];
  });

  watch(listData, (newData) => {
    if (newData && typeof newData.total === 'number') {
      pagination.count = newData.total;
    }
  }, { deep: true, immediate: true });

  const fetchListData = () => {
    isReady = true;
    isLoading.value = true;
    Promise.resolve()
      .then(() => (props.paginationValidator ? props.paginationValidator(pagination) : true))
      .then((result: boolean) => {
        if (result) {
          // 确保使用当前的 pagination.limit 值
          const currentLimit = pagination.limit;
          const params: Record<string, any> = {
            ...paramsMemo,
            page: isUnload.value ? 1 : pagination.current,
            page_size: currentLimit < 10 ? 10 : currentLimit,
          };
          isSearching.value = Object.keys(paramsMemo).length > 0;
          cancel();
          isLoading.value = true;
          run(params);
          replaceSearchParams(params);
        }
      });
  };

  // 处理筛选变更
  const handleFilterChange = (filters: Record<string, any>) => {
    // TDesign 会返回 { colKey: value | value[] }
    const nextParams: Record<string, any> = { ...paramsMemo };

    Object.keys(filters || {}).forEach((key) => {
      const value = filters[key];

      // 数组：多选或单选但返回数组
      if (Array.isArray(value)) {
        if (!value.length) {
          delete nextParams[key];
        } else {
          // 后端大多接受逗号分隔的字符串；如果只选一个就是单值
          nextParams[key] = value.length === 1 ? value[0] : value.join(',');
        }
      } else if (value === undefined || value === null || value === '') {
        delete nextParams[key];
      } else {
        nextParams[key] = value;
      }
    });

    paramsMemo = nextParams;
    isLoading.value = true;
    fetchListData();
  };
  // 解析 URL 上面的分页信息
  const parseURL = () => {
    const {
      page,
      page_size: pageSize,
      order_field: orderField,
      order_type: orderType,
    } = getSearchParams();
    const pageValue = isUnload.value ? 1 : page;
    // 非首次加载时，才从 URL 读取 page_size
    if (pageValue && pageSize) {
      pagination.current = ~~pageValue;
      if (isUnload.value) {
        // 首次加载时，强制使用默认值 10，忽略 URL 中的 page_size
        pagination.limit = 10;
      } else {
        // 非首次加载时，从 URL 读取 page_size
        pagination.limit = (~~pageSize) < 10 ? 10 : (~~pageSize);
      }
      pagination.limitList = Array.from(new Set([...pagination.limitList, pagination.limit])).sort((a, b) => a - b);
    }
    if (orderField && orderType) {
      paramsMemo = {
        ...paramsMemo,
        order_field: orderField,
        order_type: orderType,
      };
    }
    isReady = false;
  };

  const handleSortChange = (sort: any) => {
    let sortInfo: Array<{ sortBy: string; descending: boolean }> = [];

    if (Array.isArray(sort)) {
      sortInfo = sort;
    } else if (sort && typeof sort === 'object') {
      if (sort.sortBy !== undefined) {
        sortInfo = [{
          sortBy: sort.sortBy,
          descending: sort.descending || false,
        }];
      }
    }

    if (sortInfo.length === 0) {
      // 清除排序
      paramsMemo = {
        ...paramsMemo,
        order_field: undefined,
        order_type: undefined,
        sort: undefined,
      };
    } else {
      const firstSort = sortInfo[0];
      let orderType = firstSort.descending ? 'desc' : 'asc';

      // 颠倒排序（兼容旧逻辑）
      if (props.reverseSortFields && props.reverseSortFields.includes(firstSort.sortBy)) {
        orderType = orderType === 'asc' ? 'desc' : 'asc';
      }

      // 同时兼容两种后端参数形式：order_field/order_type 和 sort 数组
      const sortPrefix = orderType === 'desc' ? '-' : '';
      const sortArray = [`${sortPrefix}${firstSort.sortBy}`];

      // 合并 searchParams 以保留 event_filters 等搜索参数，避免排序时丢失
      const baseParams = { ...(props.searchParams || {}), ...paramsMemo };
      const nextParams = { ...baseParams };

      // event_data.xxx 列排序时 sort 只保留该字段，不追加 secondarySortField
      const isEventDataSort = firstSort.sortBy.startsWith('event_data.');
      if (props.secondarySortField && !isEventDataSort) {
        if (firstSort.sortBy !== props.secondarySortField.replace(/^-/, '')) {
          sortArray.push(props.secondarySortField);
        }
      }
      if (props.secondarySortField || isEventDataSort) {
        delete nextParams.order_field;
        delete nextParams.order_type;
        nextParams.sort = sortArray;
      } else {
        nextParams.order_field = firstSort.sortBy;
        nextParams.order_type = orderType;
        nextParams.sort = sortArray;
      }

      paramsMemo = nextParams;
    }
    isLoading.value = true;
    fetchListData();
  };

  // 切换页码
  const handlePageChange = (pageValue: number) => {
    pagination.current = pageValue;
    isUnload.value = false;
    isLoading.value = true;
    fetchListData();
  };

  // 切换每页条数
  const handlePageLimitChange = (pageLimit: number) => {
    pagination.limit = pageLimit;
    pagination.current = 1; // 切换每页条数时重置到第一页
    // 确保新的 pageLimit 在 limitList 中
    if (!pagination.limitList.includes(pageLimit)) {
      pagination.limitList = [...pagination.limitList, pageLimit].sort((a, b) => a - b);
    }
    isUnload.value = false;
    isLoading.value = true;
    // 确保响应式更新完成后再调用 fetchListData
    nextTick(() => {
      fetchListData();
    });
  };

  // 清空搜索条件
  const handleClearSearch = () => {
    emits('clearSearch');
  };

  // 监听窗口尺寸变化：动态重算表格可显示行数/最大高度
  let resizeTimer: ReturnType<typeof setTimeout> | null = null;
  const handleWindowResize = () => {
    if (resizeTimer) clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      calcTableHeight();
    }, 120);
  };
  onMounted(() => {
    parseURL();
    calcTableHeight();
    window.addEventListener('resize', handleWindowResize);
    // 初始化时加载数据
    nextTick(() => {
      fetchListData();
    });
    setTimeout(() => {
      isLoading.value = true;
    }, 0);
  });

  // 监听通知中心状态，重新计算表格高度
  on('show-notice', () => {
    calcTableHeight();
  });

  // 传入的 tableMaxHeight 变化时，重新计算每页条数
  watch(() => props.tableMaxHeight, () => {
    calcTableHeight();
  });

  // 销毁组件时去除监听，防止多次绑定触发
  onBeforeUnmount(() => {
    off('show-notice');
    window.removeEventListener('resize', handleWindowResize);
    if (resizeTimer) clearTimeout(resizeTimer);
  });

  const TABLE_HEADER_HEIGHT = 44;
  const TABLE_ROW_HEIGHT = 44;
  const TABLE_PADDING = 8;

  /** 根据传入的表格高度计算可显示行数 */
  const getRowNumFromHeight = (height: number | string): number => {
    let pixelHeight: number;
    if (typeof height === 'number') {
      pixelHeight = height;
    } else if (typeof height === 'string' && height !== 'auto') {
      // 支持 calc(100vh - 210px) 等表达式
      const calcMatch = height.match(/calc\s*\(\s*100vh\s*-\s*(\d+)px\s*\)/);
      if (calcMatch) {
        pixelHeight = window.innerHeight - parseInt(calcMatch[1], 10);
      } else {
        const num = parseInt(height, 10);
        pixelHeight = Number.isNaN(num) ? 0 : num;
      }
    } else {
      return 0;
    }
    return Math.max(0, Math.floor((pixelHeight - TABLE_HEADER_HEIGHT - TABLE_PADDING) / TABLE_ROW_HEIGHT) - 1);
  };

  // 计算表格尺寸信息
  const calculateTableDimensions = () => {
    const { top } = getOffset(rootRef.value);
    const windowInnerHeight = window.innerHeight;
    const paginationHeight = 60;
    const pageOffsetBottom = 20;

    const tableRowTotalHeight = windowInnerHeight - top - TABLE_HEADER_HEIGHT - paginationHeight - pageOffsetBottom;

    const rawRowNum = Math.floor(tableRowTotalHeight / TABLE_ROW_HEIGHT);
    const rowNum = Math.max(0, rawRowNum - 2); // -2 避免多一行导致出现滚动条
    return {
      tableHeaderHeight: TABLE_HEADER_HEIGHT,
      paginationHeight,
      tableRowHeight: TABLE_ROW_HEIGHT,
      rowNum,
    };
  };

  // 初始化表格高度（增高一行避免出现滚动条）
  const initTableHeight = () => {
    nextTick(() => {
      const dimensions = calculateTableDimensions();
      internalTableMaxHeight.value = dimensions.tableHeaderHeight
        + dimensions.rowNum * dimensions.tableRowHeight + TABLE_PADDING + TABLE_ROW_HEIGHT;
    });
  };

  const calcTableHeight = () => {
    nextTick(() => {
      const dimensions = calculateTableDimensions();
      // 传入 tableMaxHeight 时，根据传入高度计算行数；默认时也 -1（已在 calculateTableDimensions 中处理）
      const rowNum = (props.tableMaxHeight !== undefined && props.tableMaxHeight !== null)
        ? getRowNumFromHeight(props.tableMaxHeight)
        : dimensions.rowNum;

      // 当计算出的行数大于 10 时，更新 limitList；传入 tableMaxHeight 时无论行数多少都更新
      const shouldUpdateLimit = rowNum > 10
        || (props.tableMaxHeight !== undefined && props.tableMaxHeight !== null && rowNum >= 1);
      if (shouldUpdateLimit) {
        const pageLimit = new Set([
          ...pagination.limitList,
          rowNum,
        ]);
        pagination.limitList = Array.from(pageLimit).sort((a, b) => a - b);
        // 首次加载时，自动将每页条数设置为根据表格高度计算出的行数
        if (isUnload.value) {
          pagination.limit = rowNum;
        }
      }

      // 未传入 tableMaxHeight 时，使用内部计算值（增高一行避免出现滚动条）
      if (props.tableMaxHeight === undefined || props.tableMaxHeight === null) {
        internalTableMaxHeight.value = dimensions.tableHeaderHeight
          + dimensions.rowNum * dimensions.tableRowHeight + TABLE_PADDING + TABLE_ROW_HEIGHT;
      }
    });
  };

  defineExpose<Exposes>({
    fetchData(params = {} as Record<string, any>) {
      const {
        order_field: orderField,
        order_type: orderType,
      } = getSearchParams();
      paramsMemo = {
        ...paramsMemo,
        order_field: orderField,
        order_type: orderType,
        ...params,
      };
      if (isReady) {
        pagination.current = 1;
      }
      const recordParams = getRecordPageParams();
      removePageParams();
      if (params.page) {
        pagination.current = params.page;
      }
      if (recordParams) {
        pagination.current = Number(recordParams.page);
        pagination.limit = Number(recordParams.page_size) < 10 ? 10 : Number(recordParams.page_size);
      }
      isLoading.value = true;
      fetchListData();
    },
    loading: isLoading,
    refreshList() {
      isLoading.value = true;
      refreshList();
    },
    getListData() {
      return listData.value.results;
    },
    getSelection() {
      if (!selectedRowKeys.value || selectedRowKeys.value.length === 0) {
        return [];
      }
      // 通过 selectedRowKeys 和 tableData 获取选中的行数据
      const data = tableData.value || [];
      const currentRowKey = rowKey.value;
      return data.filter((row: any) => {
        const key = typeof currentRowKey === 'function' ? currentRowKey(row) : row[currentRowKey];
        return selectedRowKeys.value.includes(key);
      });
    },
    initTableHeight() {
      initTableHeight();
    },
    listDataUnshift(data: Record<string, any>) {
      listData.value.results.unshift(data);
    },
    initListData(data: any, key: string) {
      isLoading.value = false;
      const initData = JSON.parse(JSON.stringify(listData.value));
      listData.value.results = initData.results.map((item: Record<string, any>) => {
        const newItem = data.find((findItem: Record<string, any>) => item[key] === findItem[key]);
        if (newItem) {
          return newItem;
        }
        return item;
      });
      emits('requestSuccess', listData.value);
    },
    initData() {
      fetchListData();
    },
  });
</script>

<style lang="postcss">

.audit-tdesign-list {
  position: relative;
  border: 1px solid #e1e6f0;
}

.setings {
  position: absolute;
  top: 0;
  right: 5px;
  z-index: 1000;
  height: 42px;
  border-radius: 4px;

  .setting-btn-icon {
    display: block;
    padding: 0;
    font-size: 16px;
    line-height: 42px;
    color: #c4c6cc;
    cursor: pointer;

    &:hover {
      color: #979ba5;
    }
  }
}

.tdesign-list {
  :deep(.new-row) {
    td {
      background-color: #e4faf0 !important;
    }
  }
}

.tdesign-list-pagination {
  width: 100%;
  padding: 12px 16px;
  margin-top: 16px;
  background-color: #fff;

  .bk-pagination {
    .is-last {
      margin-left: auto;
    }
  }
}

.operation-column-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;

  .setting-btn-icon {
    padding: 0;
    margin-left: auto;
    font-size: 16px;
    color: #c4c6cc;
    cursor: pointer;

    &:hover {
      color: #979ba5;
    }
  }
}

.column-popover {
  min-width: 480px;
  padding: 0;
}

.column-popover-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;

  .column-popover-title {
    font-size: 18px;
    font-weight: 500;
    color: #313238;
  }

  .column-popover-close {
    display: flex;
    width: 24px;
    height: 24px;
    padding: 0;
    font-size: 16px;
    color: #979ba5;
    cursor: pointer;
    align-items: center;
    justify-content: center;

    &:hover {
      color: #63656e;
    }
  }
}

.column-popover-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;

  .column-popover-section-title {
    font-size: 14px;
    color: #313238;
  }
}

.column-popover-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 5px 0;
  overflow-y: auto;
  align-items: start;

  .bk-checkbox~.bk-checkbox {
    margin-left: 0 !important;
  }
}


.column-popover-footer {
  display: flex;
  width: 100%;
  padding: 12px 16px 0;
  margin-top: 16px;
  border-top: 1px solid #dcdee5;
  justify-content: end;
}

.column-popover-grid-item {
  display: block;
  width: 150px;
  margin: 0;
  justify-content: start;

}


</style>
