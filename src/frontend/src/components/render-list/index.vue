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
        :border="border"
        v-bind="$attrs"
        :columns="columns"
        :data="listData.results"
        :max-height="tableMaxHeight"
        :pagination="pagination"
        :pagination-heihgt="60"
        remote-pagination
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

  import useEventBus from '@hooks/use-event-bus';
  import useRecordPage from '@hooks/use-record-page';
  import useRequest from '@hooks/use-request';
  import useUrlSearch from '@hooks/use-url-search';

  import {
    getOffset,
  } from '@utils/assist';
  import type { IRequestResponsePaginationData } from '@utils/request';

  interface Props {
    columns: InstanceType<typeof Table>['$props']['columns'],
    reverseSortFields?:Array<string>, // 颠倒排序的字段数组
    dataSource: (params: any)=> Promise<IRequestResponsePaginationData<any>>,
    paginationValidator?: (pagination: IPagination) => boolean,
    isNeedHideClearSearchTip?: boolean,
    settings?: Settings,
    border?: string | ('col' | 'none' | 'row' | 'horizontal' | 'outer')[],
    needEmptySearchTip?:boolean,
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
    getListData:()=>Array<Record<string, any>>
  }

  const props = withDefaults(defineProps<Props>(), {
    border: () => ['outer'],
    reverseSortFields: () => [],
    needEmptySearchTip: true,
    paginationValidator: undefined,
    settings: undefined,
  }) ;
  const emits = defineEmits<Emits>();
  const { getRecordPageParams, removePageParams } = useRecordPage;
  const { on, off } = useEventBus();
  const slot = useSlots();

  const rootRef = ref();
  const { t } = useI18n();
  const pagination = reactive<IPagination>({
    count: 0,
    current: 1,
    limit: 10,
    limitList: [10, 20, 50, 100],
    align: 'right',
    layout: ['total', 'limit', 'list'],
  });
  const tableMaxHeight = ref(0);

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
    loading: isLoading,
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
          const params = {
            ...paramsMemo,
            page: pagination.current,
            page_size: Math.max(pagination.limit, 1),
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
    if (page && pageSize) {
      pagination.current = ~~page;
      pagination.limit = ~~pageSize;
      pagination.limitList = [...new Set([...pagination.limitList, pagination.limit])].sort((a, b) => a - b);
    }
    if (orderField && orderType) {
      paramsMemo = {
        order_field: orderField,
        order_type: orderType,
      };
    }
    isReady = false;
  };
  const handleSettingChange = (setting: ISettings) => {
    emits('onSettingChange', setting);
  };
  const handleColumnSortChange = (sortPayload: any) => {
    let { type } = sortPayload;
    // 移除之前选中的排序样式
    const sortAr:Array<Element> = rootRef.value.getElementsByClassName('bk-head-cell-sort');
    Array.from(sortAr).forEach((item:Element) => {
      const sortIconAr =  item.getElementsByClassName('sort-action');
      for (let i = 0; i < sortIconAr.length; i++) {
        sortIconAr[i].className =  sortIconAr[i].className.replace('active', '');
      }
    });
    // 颠倒排序
    if (props.reverseSortFields && sortPayload.type !== 'null'
      &&  props.reverseSortFields.includes(sortPayload.column.field)) {
      type = type === 'asc' ? 'desc' : 'asc';
    }
    paramsMemo = {
      ...paramsMemo,
      order_field: _.isString(sortPayload.column.field) ? sortPayload.column.field : sortPayload.column.field(),
      order_type: type === 'null' ? undefined : type,
    };
    fetchListData();
  };
  // 切换每页条数
  const handlePageLimitChange = (pageLimit: number) => {
    pagination.limit = pageLimit;
    fetchListData();
  };
  // 切换页码
  const handlePageValueChange = (pageValue:number) => {
    pagination.current = pageValue;
    fetchListData();
  };
  // 情况搜索条件
  const handleClearSearch  = () => {
    emits('clearSearch');
  };

  onMounted(() => {
    parseURL();
    calcTableHeight();
  });

  // 监听通知中心状态，重新计算表格高度
  on('show-notice', () => {
    calcTableHeight();
  });

  // 销毁组件时去除监听，防止多次绑定触发
  onBeforeUnmount(() => {
    off('show-notice');
  });

  const calcTableHeight = () => {
    nextTick(() => {
      const { top } = getOffset(rootRef.value);
      const windowInnerHeight = window.innerHeight;
      const tableHeaderHeight = 42;
      const paginationHeight = 60;
      const pageOffsetBottom = 20;
      const tableRowHeight = 42;

      const tableRowTotalHeight = windowInnerHeight - top - tableHeaderHeight - paginationHeight - pageOffsetBottom;

      const rowNum = Math.floor(tableRowTotalHeight / tableRowHeight);
      const pageLimit = new Set([
        ...pagination.limitList,
        rowNum,
      ]);
      pagination.limit = rowNum;
      pagination.limitList = [...pageLimit].sort((a, b) => a - b);

      tableMaxHeight.value = tableHeaderHeight + rowNum * tableRowHeight + paginationHeight + 8;
    });
  };

  defineExpose<Exposes>({
    fetchData(params = {} as Record<string, any>) {
      paramsMemo = {
        ...paramsMemo,
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
        pagination.limit = Number(recordParams.page_size);
      }
      fetchListData();
    },
    loading: isLoading,
    refreshList() {
      refreshList();
    },
    getListData() {
      return listData.value.results;
    },
  });
</script>
