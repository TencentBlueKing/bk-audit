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
    class="audit-render-list">
    <bk-loading :loading="isLoading">
      <bk-table
        :key="tableRenderKey"
        ref="tableRef"
        :border="border"
        class="render-list"
        v-bind="$attrs"
        :columns="columns"
        :data="listData.results"
        :height="tableHeight"
        :max-height="tableMaxHeight"
        :min-height="300"
        :pagination="pagination"
        remote-pagination
        :scrollbar="false"
        :settings="settings"
        @column-sort="handleColumnSortChange"
        @page-limit-change="handlePageLimitChange"
        @page-value-change="handlePageValueChange"
        @setting-change="handleSettingChange">
        <template #expandRow="row">
          <slot
            name="expandRow"
            :row="row" />
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
      </bk-table>
    </bk-loading>
  </div>
</template>
<script lang="ts">
  export interface IPagination {
    count: number;
    current: number;
    limit: number;
    limitList: Array<number>;
    align: string,
    layout: Array<string>;
  }
</script>
<script setup lang="ts">
  import type { Table } from 'bkui-vue';
  import type { Settings } from 'bkui-vue/lib/table/props';
  import _ from 'lodash';
  import {
    nextTick,
    onBeforeUnmount,
    onMounted,
    reactive,
    type Ref,
    ref,
    useSlots,
    watch  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import useEventBus from '@hooks/use-event-bus';
  import useRecordPage from '@hooks/use-record-page';
  import useRequest from '@hooks/use-request';
  import useUrlSearch from '@hooks/use-url-search';

  import {
    getOffset,
  } from '@utils/assist';
  import type { IRequestResponsePaginationData } from '@utils/request';

  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  interface Props {
    columns: InstanceType<typeof Table>['$props']['columns'],
    reverseSortFields?:Array<string>, // 颠倒排序的字段数组
    dataSource: (params: any)=> Promise<IRequestResponsePaginationData<any>>,
    paginationValidator?: (pagination: IPagination) => boolean,
    isNeedHideClearSearchTip?: boolean,
    settings?: Settings,
    border?: string | ('col' | 'none' | 'row' | 'horizontal' | 'outer')[],
    needEmptySearchTip?:boolean,
    // 是否需要场景参数
    isNeedSceneParams?: boolean,
    // 是否需要场景ID
    isNeedSceneId?: boolean,
    sceneIdKey?: string
  }

  interface ISettings{
    checked: Array<string>,
    fields: Record<string, any>[],
    size: string
  }
  interface Emits {
    (e: 'requestSuccess', value: any): void,
    (e: 'clearSearch'): void,
    (e:'onSettingChange', setting: ISettings): void,
  }
  interface Exposes {
    fetchData: (params: Record<string, any>) => void,
    /** 清空筛选/排序等记忆参数后重新拉取（切换场景时使用） */
    resetFetchData: (params?: Record<string, any>) => void,
    loading: Ref<boolean>,
    refreshList: () => void,
    getListData:()=> Array<Record<string, any>>,
    getSelection:()=> void
    initTableHeight: () => void,
    listDataUnshift: (data: Record<string, any>) => void,
    initListData:(data: any, key: string) => void
    initData: () => void
  }

  const props = withDefaults(defineProps<Props>(), {
    border: () => ['outer'],
    reverseSortFields: () => [],
    needEmptySearchTip: true,
    paginationValidator: undefined,
    settings: undefined,
    cc: false,
    isNeedSceneParams: false,
    isNeedSceneId: false,
    sceneIdKey: 'scope_id',
  }) ;
  const emits = defineEmits<Emits>();
  const isUnload = ref(true);
  const { getRecordPageParams, removePageParams } = useRecordPage;
  const { on, off } = useEventBus();
  const slot = useSlots();
  const tableRef = ref();
  const rootRef = ref();
  // 切换场景重置排序时递增，强制表头按未排序态重新初始化
  const tableRenderKey = ref(0);
  const { t } = useI18n();
  const route = useRoute();
  const pagination = reactive<IPagination>({
    count: 0,
    current: 1,
    limit: 10,
    limitList: [10, 20, 50, 100, 500],
    align: 'right',
    layout: ['total', 'limit', 'list'],
  });
  const tableMaxHeight = ref(0);
  const tableHeight = ref<string | number>('auto');
  let paramsMemo: Record<string, any> = {};
  const isSearching = ref(false);

  let isReady = false;
  const isLoading = ref(false);
  // 新增：用户是否手动选择了分页大小的标志
  const isUserSelectedPageSize = ref(false);
  /** page 非法（NaN/≤0）时回退为 1，避免添加/编辑返回后出现 page=NaN */
  const normalizePage = (page: unknown, fallback = 1) => {
    const num = Number(page);
    if (!Number.isFinite(num) || num < 1) {
      return fallback;
    }
    return Math.floor(num);
  };
  const parseSortParam = (sort?: string | string[]) => {
    if (!sort) return undefined;
    if (Array.isArray(sort)) return sort;
    try {
      const parsedSort = JSON.parse(sort);
      return Array.isArray(parsedSort) ? parsedSort : undefined;
    } catch {
      // 兼容旧 URL：sort=-field 或 sort=field1,-field2
      return sort.split(',').filter(Boolean);
    }
  };
  const {
    getSearchParams,
    replaceSearchParams,
  } = useUrlSearch();

  // 刷新后根据 URL 恢复表头排序高亮：
  // bk-table 列的初始高亮由 column.sort.value 决定，页面里通常传 'custom'（无方向），
  // 这里把 URL 中的排序方向写回对应列，首屏渲染即可显示箭头高亮
  const restoreColumnSortActive = () => {
    const { sort } = getSearchParams();
    const sortArray = parseSortParam(sort);
    const primarySort = sortArray?.[0];
    if (!primarySort || typeof primarySort !== 'string') return;
    const isDesc = primarySort.startsWith('-');
    const field = isDesc ? primarySort.slice(1) : primarySort;
    // 与 handleColumnSortChange 的 reverse 逻辑对应：请求方向与图标方向互为反转
    let uiType: 'asc' | 'desc' = isDesc ? 'desc' : 'asc';
    if (props.reverseSortFields.includes(field)) {
      uiType = uiType === 'desc' ? 'asc' : 'desc';
    }
    const column = (props.columns || []).find((col: any) => {
      if (!col?.sort) return false;
      const colField = typeof col.field === 'function' ? col.field() : col.field;
      return colField === field;
    }) as Record<string, any> | undefined;
    if (column) {
      // sortFn 恒等：数据顺序以服务端返回为准，value 仅用于初始高亮
      column.sort = { value: uiType, sortFn: () => 0 };
    }
  };
  restoreColumnSortActive();

  const {
    run,
    data: listData,
    refresh: refreshList,
    cancel,
  // eslint-disable-next-line vue/no-setup-props-destructure
  } = useRequest(props.dataSource, {
    defaultValue: {
      results: [],
      page: 1,
      num_pages: 1,
      total: 1,
    },
    onSuccess(data) {
      emits('requestSuccess', data);
      isUnload.value = false;
      isLoading.value = false;
    },
  });

  watch(listData, (listData) => {
    pagination.count = listData.total;
  });

  const fetchListData = () => {
    isReady = true;
    Promise.resolve()
      .then(() => (props.paginationValidator ? props.paginationValidator(pagination) : true))
      .then((result: boolean) => {
        if (result) {
          // 如果存在 sort，则删除 order_field 和 order_type 字段
          const { isNeedSceneParams, isNeedSceneId } = props;
          const cleanedParams = { ...paramsMemo };
          if (cleanedParams.sort) {
            delete cleanedParams.order_field;
            delete cleanedParams.order_type;
          }
          const pageSize = Math.max(pagination.limit, 10);
          // 优先使用 URL query 中的场景参数，避免 sessionStorage 中 UUID 导致类型错误
          const sceneParams = isNeedSceneParams ? {
            scope_id: (route.query.scope_id as string) || getSceneSystemParams().scope_id,
            scope_type: (route.query.scope_type as string) || getSceneSystemParams().scope_type,
          } : {};
          const sceneIdParam = isNeedSceneId ? {
            [props.sceneIdKey]: (route.query[props.sceneIdKey] as string)
              || (route.query.scope_id as string)
              || getSceneSystemParams().scope_id,
          } : {};
          // 无论是否透传场景参数给接口，写回 URL 时都保留场景上下文，避免切换场景重置筛选后丢失 scene_id
          const sceneContextFromUrl = {
            ...(route.query.scene_id ? { scene_id: String(route.query.scene_id) } : {}),
            ...(route.query.scope_id ? { scope_id: String(route.query.scope_id) } : {}),
            ...(route.query.scope_type ? { scope_type: String(route.query.scope_type) } : {}),
          };
          if (!sceneContextFromUrl.scene_id && !sceneContextFromUrl.scope_id) {
            const sceneInfo = getSceneSystemParams();
            if (sceneInfo.scope_id) {
              sceneContextFromUrl.scene_id = sceneInfo.scope_id;
              sceneContextFromUrl.scope_id = sceneInfo.scope_id;
            }
            if (sceneInfo.scope_type) {
              sceneContextFromUrl.scope_type = sceneInfo.scope_type;
            }
          }
          const params = {
            ...cleanedParams,
            page: isUnload.value ? 1 : normalizePage(pagination.current),
            page_size: pageSize,
            ...sceneParams,
            ...sceneIdParam,
          };
          isSearching.value = Object.keys(cleanedParams).length > 0;
          cancel();
          run(params).finally(() => {
            isLoading.value = false;
          });
          replaceSearchParams({
            ...params,
            ...sceneContextFromUrl,
          });
        }
      });
  };
  // 解析 URL 上面的分页信息
  const parseURL = () => {
    const recordParams = getRecordPageParams();
    const {
      page,
      page_size: pageSize,
      order_field: orderField,
      order_type: orderType,
      sort,
    } = getSearchParams();

    // 从详情/编辑返回：优先恢复 sessionStorage 中记录的分页
    if (recordParams?.page_size) {
      pagination.current = normalizePage(recordParams.page);
      pagination.limit = Number(recordParams.page_size) < 10 ? 10 : Number(recordParams.page_size);
      pagination.limitList = [...new Set([...pagination.limitList, pagination.limit])].sort((a, b) => a - b);
      isUserSelectedPageSize.value = true;
    } else {
      const pageValue = isUnload.value ? 1 : page;
      if (pageValue && pageSize) {
        pagination.current = normalizePage(pageValue);
        pagination.limit = (~~pageSize) < 10 ? 10 : (~~pageSize);
        pagination.limitList = [...new Set([...pagination.limitList, pagination.limit])].sort((a, b) => a - b);
      } else {
        isUserSelectedPageSize.value = false;
      }
    }
    // 优先使用新的 sort 数组格式，向后兼容旧的 order_field + order_type
    if (sort) {
      const sortArray = parseSortParam(sort);
      if (sortArray?.length) {
        paramsMemo = {
          ...paramsMemo,
          sort: sortArray,
        };
      }
    } else if (orderField && orderType) {
      // 向后兼容：将旧的 order_field + order_type 转换为 sort 数组
      const sortField = orderType === 'desc' ? `-${orderField}` : orderField;
      paramsMemo = {
        ...paramsMemo,
        sort: [sortField],
      };
    }
    // 注意：默认排序应该在具体页面组件中设置，而不是在通用组件中
    // 从URL参数初始化时：有 page_size 则已在上方标记为用户分页状态
    isReady = false;
  };
  const handleSettingChange = (setting: ISettings) => {
    emits('onSettingChange', setting);
  };
  // 清除表头排序箭头高亮（bk-table 内部 sortType 不会随 column.sort 变更自动重置）
  const clearSortActiveUI = () => {
    if (!rootRef.value) return;
    const sortAr: Array<Element> = rootRef.value.getElementsByClassName('bk-head-cell-sort');
    Array.from(sortAr).forEach((item: Element) => {
      const sortIconAr = item.getElementsByClassName('sort-action');
      for (let i = 0; i < sortIconAr.length; i++) {
        sortIconAr[i].className = sortIconAr[i].className.replace(/\bactive\b/g, '').replace(/\s+/g, ' ')
          .trim();
      }
    });
  };
  const handleColumnSortChange = (sortPayload: any) => {
    let { type } = sortPayload;
    // 移除之前选中的排序样式
    clearSortActiveUI();
    // 颠倒排序
    if (props.reverseSortFields && sortPayload.type !== 'null'
      &&  props.reverseSortFields.includes(sortPayload.column.field)) {
      type = type === 'asc' ? 'desc' : 'asc';
    }
    const field = _.isString(sortPayload.column.field) ? sortPayload.column.field : sortPayload.column.field();
    // 使用新的 sort 数组格式：字段名前缀 - 表示倒序，无前缀为正序
    if (type === 'null') {
      // 清除排序
      paramsMemo = {
        ...paramsMemo,
        sort: undefined,
        order_field: undefined,
        order_type: undefined,
      };
    } else {
      const sortField = type === 'desc' ? `-${field}` : field;
      // 根据常规字段排序规则拼装 sort 数组
      const sortArray: string[] = [sortField];
      // 风险等级：需要附带 -event_time 作为次级排序字段
      if (field === 'risk_level') {
        sortArray.push('-event_time');
      }
      // 首次发现时间：只按 event_time 排序（不附加次级字段）
      // 最后处理时间：需要附带 -event_time 作为次级排序字段
      if (field === 'last_operate_time') {
        sortArray.push('-event_time');
      }
      // 展示状态：需要附带 -event_time 作为次级排序字段
      if (field === 'display_status') {
        sortArray.push('-event_time');
      }
      paramsMemo = {
        ...paramsMemo,
        sort: sortArray,
        // 如果存在 sort，则删除 order_field 和 order_type 字段
        order_field: undefined,
        order_type: undefined,
      };
    }
    isLoading.value = true;
    fetchListData();
  };
  // 切换每页条数
  const handlePageLimitChange = (pageLimit: number) => {
    // 用户手动选择分页大小，设置标志
    isUserSelectedPageSize.value = true;
    pagination.limit = pageLimit;
    isUnload.value = false;
    isLoading.value = true;
    fetchListData();
  };
  // 切换页码
  const handlePageValueChange = (pageValue:number) => {
    pagination.current = normalizePage(pageValue);
    isUnload.value = false;
    isLoading.value = true;
    fetchListData();
  };
  // 情况搜索条件
  const handleClearSearch  = () => {
    // 清空搜索条件时重置用户选择标志
    isUserSelectedPageSize.value = false;
    emits('clearSearch');
  };
  const applyHeightBasedPageSize = () => {
    if (isUserSelectedPageSize.value) {
      return;
    }
    const { page_size: urlPageSize } = getSearchParams();
    if (urlPageSize || getRecordPageParams()?.page_size) {
      return;
    }
    const dimensions = calculateTableDimensions();
    const nextLimit = dimensions.rowNum < 10 ? 10 : dimensions.rowNum;
    pagination.limit = nextLimit;
    if (nextLimit > 10) {
      pagination.limitList = [...new Set([...pagination.limitList, nextLimit])].sort((a, b) => a - b);
    }
  };

  onMounted(() => {
    parseURL();
    applyHeightBasedPageSize();
    calcTableHeight();
  });

  const handleResize = _.debounce(() => {
    calcTableHeight();
  }, 120);

  // 监听通知中心状态，重新计算表格高度
  on('show-notice', () => {
    calcTableHeight();
  });

  window.addEventListener('resize', handleResize);

  // 销毁组件时去除监听，防止多次绑定触发
  onBeforeUnmount(() => {
    off('show-notice');
    window.removeEventListener('resize', handleResize);
  });

  // 计算表格尺寸信息
  const calculateTableDimensions = () => {
    const { top } = getOffset(rootRef.value);
    const windowInnerHeight = window.innerHeight;
    const tableHeaderHeight = 42;
    const paginationHeight = 60;
    const pageOffsetBottom = 20;
    const tableRowHeight = 42;

    const tableRowTotalHeight = windowInnerHeight - top - tableHeaderHeight - paginationHeight - pageOffsetBottom;

    const rowNum = Math.floor(tableRowTotalHeight / tableRowHeight);
    return {
      tableHeaderHeight,
      paginationHeight,
      tableRowHeight,
      rowNum,
    };
  };

  // 初始化表格高度
  const initTableHeight = () => {
    nextTick(() => {
      const dimensions = calculateTableDimensions();
      const nextHeight = dimensions.tableHeaderHeight
        + dimensions.rowNum * dimensions.tableRowHeight
        + dimensions.paginationHeight
        + 8;
      // eslint-disable-next-line max-len
      tableMaxHeight.value = nextHeight < 300 ? 300 : nextHeight;
      tableHeight.value = tableMaxHeight.value;
    });
  };

  const calcTableHeight = () => {
    nextTick(() => {
      const dimensions = calculateTableDimensions();
      const nextLimit = dimensions.rowNum < 10 ? 10 : dimensions.rowNum;
      const isLimitChanged = nextLimit !== pagination.limit;
      const pageLimit = new Set([
        ...pagination.limitList,
        nextLimit,
      ]);

      // 如果用户已经手动选择了分页大小，则不再自动调整分页大小
      if (isUserSelectedPageSize.value) {
        // 只更新表格高度，不修改分页大小
        const nextHeight = dimensions.tableHeaderHeight
          + dimensions.rowNum * dimensions.tableRowHeight
          + dimensions.paginationHeight
          + 8;
        // eslint-disable-next-line max-len
        tableMaxHeight.value = nextHeight < 300 ? 300 : nextHeight;
        tableHeight.value = tableMaxHeight.value;
        return;
      }

      pagination.limit = nextLimit;
      if (pagination.limit > 10) {
        pagination.limitList = [...pageLimit].sort((a, b) => a - b);
      }
      const nextHeight = dimensions.tableHeaderHeight
        + dimensions.rowNum * dimensions.tableRowHeight
        + dimensions.paginationHeight
        + 8;
      // eslint-disable-next-line max-len
      tableMaxHeight.value = nextHeight < 300 ? 300 : nextHeight;
      tableHeight.value = tableMaxHeight.value;

      if (isLimitChanged && isReady) {
        pagination.current = 1;
        isUnload.value = false;
        isLoading.value = true;
        fetchListData();
      }
    });
  };

  defineExpose<Exposes>({
    fetchData(params = {} as Record<string, any>) {
      const {
        order_field: orderField,
        order_type: orderType,
        sort,
      } = getSearchParams();
      const normalizedParams = Object.keys(params).reduce((result, key) => {
        const value = params[key];
        if (value === undefined || value === null || value === '') {
          return result;
        }
        if (Array.isArray(value) && value.length === 0) {
          return result;
        }
        return {
          ...result,
          [key]: value,
        };
      }, {} as Record<string, any>);
      // 优先使用新的 sort 数组格式
      // 如果存在 sort，则删除 order_field 和 order_type 字段
      let sortParam: Record<string, any> = {};
      // 优先使用传入的 sort 参数
      if (normalizedParams.sort) {
        sortParam = {
          sort: normalizedParams.sort,
        };
      } else if (sort) {
        const sortArray = parseSortParam(sort);
        sortParam = sortArray?.length ? { sort: sortArray } : {};
      } else if (orderField && orderType) {
        sortParam = {
          sort: [orderType === 'desc' ? `-${orderField}` : orderField],
        };
      }
      paramsMemo = {
        ...sortParam,
        ...normalizedParams,
      };
      // 如果存在 sort，确保删除 order_field 和 order_type
      if (paramsMemo.sort) {
        delete paramsMemo.order_field;
        delete paramsMemo.order_type;
      }
      if (isReady) {
        pagination.current = 1;
      }
      const recordParams = getRecordPageParams();
      removePageParams();
      if (params.page) {
        pagination.current = normalizePage(params.page);
      }
      if (recordParams) {
        pagination.current = normalizePage(recordParams.page);
        pagination.limit = Number(recordParams.page_size) < 10 ? 10 : Number(recordParams.page_size);
        // 从详情/编辑返回时恢复离开前的分页大小，避免被 calcTableHeight 重置为 10
        isUserSelectedPageSize.value = true;
      } else {
        // 重置用户选择标志，允许重新计算分页大小
        isUserSelectedPageSize.value = false;
      }
      isLoading.value = true;
      fetchListData();
    },
    // 切换场景等场景：不继承 URL 上的 sort/筛选，只保留场景上下文后重新拉取
    resetFetchData(params = {} as Record<string, any>) {
      const normalizedParams = Object.keys(params).reduce((result, key) => {
        const value = params[key];
        if (value === undefined || value === null || value === '') {
          return result;
        }
        if (Array.isArray(value) && value.length === 0) {
          return result;
        }
        return {
          ...result,
          [key]: value,
        };
      }, {} as Record<string, any>);
      // 清空历史筛选/排序记忆，避免旧场景条件污染新场景
      paramsMemo = { ...normalizedParams };
      delete paramsMemo.sort;
      delete paramsMemo.order_field;
      delete paramsMemo.order_type;
      pagination.current = 1;
      isUserSelectedPageSize.value = false;
      removePageParams();
      // 恢复列配置，并强制表格重挂载以清除表头排序/筛选高亮
      (props.columns || []).forEach((col: any) => {
        if (col?.sort) {
          // eslint-disable-next-line no-param-reassign
          col.sort = 'custom';
        }
        if (col?.filter && Array.isArray(col.filter.checked)) {
          // eslint-disable-next-line no-param-reassign
          col.filter.checked.length = 0;
        }
      });
      tableRenderKey.value += 1;
      clearSortActiveUI();
      nextTick(() => {
        clearSortActiveUI();
      });
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
      return tableRef.value?.getSelection();
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
      emits('requestSuccess',  listData.value);
    },
    initData() {
      isLoading.value = false;
      // 初始化数据时重置用户选择标志
      isUserSelectedPageSize.value = false;
      fetchListData();
    },
  });
</script>

<style lang="postcss" scoped>
  .render-list {
    :deep(.new-row) {
      td {
        background-color: #e4faf0 !important;
      }
    }
  }
</style>
