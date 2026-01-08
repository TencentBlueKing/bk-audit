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
    class="audit-tdesign-list">
    <bk-loading :loading="isLoading">
      <primary-table
        ref="tableRef"
        :border="border"
        class="tdesign-list"
        :columns="columns"
        :data="listData.results"
        :height="height"
        :max-height="maxHeight"
        v-bind="$attrs"
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
          @change="handlePageChange"
          @limit-change="handlePageLimitChange" />
      </div>
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
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
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

  interface Props {
    columns: any[],
    reverseSortFields?:Array<string>, // 颠倒排序的字段数组
    dataSource: (params: any)=> Promise<IRequestResponsePaginationData<any>>,
    paginationValidator?: (pagination: IPagination) => boolean,
    isNeedHideClearSearchTip?: boolean,
    border?: boolean,
    needEmptySearchTip?:boolean,
    height?: number | string,
    maxHeight?: number | string
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
    reverseSortFields: () => [],
    needEmptySearchTip: true,
    paginationValidator: undefined,
    border: true,
    isNeedHideClearSearchTip: false,
    height: 'auto',
    maxHeight: 'auto',
  }) ;
  const emits = defineEmits<Emits>();
  const isUnload = ref(true);
  const { getRecordPageParams, removePageParams } = useRecordPage;
  const { on, off } = useEventBus();
  const slot = useSlots();
  const tableRef = ref();
  const rootRef = ref();
  const { t } = useI18n();
  const tableMaxHeight = ref<number | string>('auto');
  const pagination = reactive<IPagination>({
    count: 0,
    current: 1,
    limit: 10,
    limitList: [10, 20, 50, 100, 500],
    align: 'right',
    layout: ['total', 'limit', 'list'],
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

  watch(listData, (newData) => {
    if (newData && typeof newData.total === 'number') {
      pagination.count = newData.total;
    }
  }, { deep: true, immediate: true });

  const fetchListData = () => {
    isReady = true;
    Promise.resolve()
      .then(() => (props.paginationValidator ? props.paginationValidator(pagination) : true))
      .then((result: boolean) => {
        if (result) {
          // 确保使用当前的 pagination.limit 值
          const currentLimit = pagination.limit;
          const params = {
            ...paramsMemo,
            page: isUnload.value ? 1 :  pagination.current,
            page_size: currentLimit < 10 ? 10 : currentLimit,
          };
          isSearching.value = Object.keys(paramsMemo).length > 0;
          cancel();
          run(params);
          replaceSearchParams(params);
        }
      });
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
      pagination.limitList = [...new Set([...pagination.limitList, pagination.limit])].sort((a, b) => a - b);
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

  const handleSortChange = (sort: any, options?: any) => {
    // TDesign 的 sort-change 事件可能传递不同的数据结构
    // 处理数组格式的排序信息
    let sortInfo: Array<{ sortBy: string; descending: boolean }> = [];

    if (Array.isArray(sort)) {
      sortInfo = sort;
    } else if (sort && typeof sort === 'object') {
      // 如果是对象格式，转换为数组格式
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
      };
    } else {
      const firstSort = sortInfo[0];
      let orderType = firstSort.descending ? 'desc' : 'asc';

      // 颠倒排序
      if (props.reverseSortFields && props.reverseSortFields.includes(firstSort.sortBy)) {
        orderType = orderType === 'asc' ? 'desc' : 'asc';
      }

      paramsMemo = {
        ...paramsMemo,
        order_field: firstSort.sortBy,
        order_type: orderType,
      };
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
  const handleClearSearch  = () => {
    emits('clearSearch');
  };
  onMounted(() => {
    parseURL();
    calcTableHeight();
    // 初始化时加载数据
    nextTick(() => {
      fetchListData();
    });
  });

  // 监听通知中心状态，重新计算表格高度
  on('show-notice', () => {
    calcTableHeight();
  });

  // 销毁组件时去除监听，防止多次绑定触发
  onBeforeUnmount(() => {
    off('show-notice');
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
      // eslint-disable-next-line max-len
      tableMaxHeight.value = dimensions.tableHeaderHeight + dimensions.rowNum * dimensions.tableRowHeight + dimensions.paginationHeight + 8;
    });
  };

  const calcTableHeight = () => {
    nextTick(() => {
      const dimensions = calculateTableDimensions();
      // 不再自动设置 pagination.limit，保持用户选择的默认值 10
      // 只更新 limitList 以包含计算出的行数（如果大于 10）
      if (dimensions.rowNum > 10) {
        const pageLimit = new Set([
          ...pagination.limitList,
          dimensions.rowNum,
        ]);
        pagination.limitList = [...pageLimit].sort((a, b) => a - b);
      }
      // eslint-disable-next-line max-len
      tableMaxHeight.value = dimensions.tableHeaderHeight + dimensions.rowNum * dimensions.tableRowHeight + dimensions.paginationHeight + 8;
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
      return tableRef.value?.getSelectedRowData?.() || [];
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
      fetchListData();
    },
  });
</script>

<style lang="postcss" scoped>
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
    border-top: 1px solid #dcdee5;

    :deep(.bk-pagination) {
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: 100%;
      min-height: 32px;

      .bk-pagination-info {
        margin-right: 16px;
        font-size: 12px;
        color: #63656e;
        white-space: nowrap;
        flex: 0 0 auto;
      }

      .bk-pagination-limit {
        margin: 0 16px;
        font-size: 12px;
        color: #63656e;
        white-space: nowrap;
        flex: 0 0 auto;
      }

      .bk-pagination-list {
        flex: 0 0 auto;
        display: flex;
        align-items: center;
        margin-left: auto;
        gap: 4px;
      }
    }
  }
</style>
