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
  <div ref="rootRef">
    <bk-loading :loading="isLoading">
      <bk-table
        ref="tableRef"
        :border="['outer']"
        :columns="columns"
        :data="listData.results"
        :max-height="tableMaxHeight"
        :pagination="pagination"
        :pagination-heihgt="60"
        remote-pagination
        v-bind="$attrs"
        @page-limit-change="handlePageLimitChange"
        @page-value-change="handlePageValueChange">
        <template #expandRow="row">
          <slot
            name="expandRow"
            :row="row" />
        </template>
        <template #empty>
          <bk-exception
            v-if="isSearching"
            scene="part"
            style="height: 280px;padding-top: 40px;"
            type="search-empty">
            <div>
              <div style="color: #63656e;">
                {{ t('搜索结果为空') }}
              </div>
              <div style="margin-top: 8px; color: #979ba5;">
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
    layout: Array<string>
  }
</script>
<script setup lang="ts">
  import type { Table } from 'bkui-vue';
  import _ from 'lodash';
  import {
    onBeforeUnmount,
    onMounted,
    reactive,
    type Ref,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import useRequest from '@hooks/use-request';
  import useUrlSearch from '@hooks/use-url-search';

  import type {
    IRequestResponsePaginationData,
  } from '@utils/request';

  interface Props {
    columns: InstanceType<typeof Table>['$props']['columns'],
    dataSource: (params: any)=> Promise<IRequestResponsePaginationData<any>>,
    paginationValidator?: (pagination: IPagination) => boolean
  }
  interface Emits {
    (e: 'requestSuccess', value: any, total: number): void,
    (e: 'clearSearch'): void,
  }
  interface Exposes {
    fetchData: (params: Record<string, any>) => void,
    loading: Ref<boolean>,
    getTableRef: () => Ref<any>
    getParamsMemo: () => Ref<Record<string, any>>
  }

  const props = defineProps<Props>();

  const emits = defineEmits<Emits>();

  const { t } = useI18n();

  const rootRef = ref();
  const tableRef = ref();
  const pagination = reactive<IPagination>({
    count: 0,
    current: 1,
    limit: 50,
    limitList: [10, 20, 50, 100],
    align: 'right',
    layout: ['total', 'limit', 'list'],
  });
  const tableMaxHeight = ref(0);

  const paramsMemo = ref<Record<string, any>>({});
  const params = ref<Record<string, any>>({});
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
      emits('requestSuccess', data.results, data.total);
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
          params.value = {
            ...paramsMemo.value,
            page: pagination.current,
            page_size: pagination.limit,
          };
          isSearching.value = Object.keys(paramsMemo).length > 0;
          cancel();
          run(params.value);
          replaceSearchParams(params.value);
        }
      });
  };
  // 解析 URL 上面的分页信息
  const parseURL = () => {
    const {
      page,
      page_size: pageSize,
    } = getSearchParams();
    if (page && pageSize) {
      pagination.current = ~~page;
      pagination.limit = ~~pageSize;
      pagination.limitList = [...new Set([...pagination.limitList, pagination.limit])].sort((a, b) => a - b);
    }
    isReady = false;
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

  const calcTableHeight = _.throttle(() => {
    const windowInnerHeight = window.innerHeight;
    tableMaxHeight.value = windowInnerHeight - 500;
  }, 100);

  onMounted(() => {
    parseURL();
    calcTableHeight();
    window.addEventListener('resize', calcTableHeight);
    const observer = new MutationObserver(() => {
      calcTableHeight();
    });
    observer.observe(document.querySelector('body') as Node, {
      subtree: true,
      childList: true,
      characterData: true,
    });
    onBeforeUnmount(() => {
      observer.takeRecords();
      observer.disconnect();
      window.removeEventListener('resize', calcTableHeight);
    });
  });

  defineExpose<Exposes>({
    fetchData(params: Record<string, any>) {
      paramsMemo.value = params || {};
      if (isReady) {
        pagination.current = 1;
      }
      fetchListData();
    },
    loading: isLoading,
    getTableRef() {
      return tableRef;
    },
    getParamsMemo() {
      return params;
    },
  });
</script>
