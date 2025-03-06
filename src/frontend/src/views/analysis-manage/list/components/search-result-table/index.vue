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
    class="search-result-list">
    <render-table
      v-if="isInit"
      ref="listRef"
      :columns="tableColumn"
      :data-source="dataSource"
      @clear-search="handleClearSearch"
      @request-success="handleRequestSuccess"
      @row-click="handleRowClick">
      <template #expandRow="{ row }">
        <row-expand-content
          :data="row"
          :filter="filter" />
      </template>
    </render-table>
    <setting-filed @update-field="handleUpdateField" />
  </div>
</template>
<script setup lang="tsx">
  import type { Table } from 'bkui-vue';
  import _ from 'lodash';
  import {
    computed,
    nextTick,
    type Ref,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
  } from 'vue-router';

  import MetaManageService from '@service/meta-manage';

  import type SearchModel from '@model/es-query/search';
  import type StandardFieldModel from '@model/meta/standard-field';

  import useRequest from '@hooks/use-request';

  import filedConfig from '@views/analysis-manage/list/components/search-box/components/render-field-config/config';

  import RenderAction from './components/render-field/action.vue';
  import RenderAuthInstanceButton from './components/render-field/auth-instance-button.vue';
  import RenderInstance from './components/render-field/instance.vue';
  import RenderResource from './components/render-field/resource.vue';
  import RenderResult from './components/render-field/result.vue';
  import RenderSystem from './components/render-field/system.vue';
  import RenderUser from './components/render-field/user.vue';
  import RenderTable from './components/render-table.vue';
  import DiffDetail from './components/row-diff-detail/index.vue';
  import RowExpandContent from './components/row-expand-content/index.vue';
  import SettingFiled from './components/setting-field/index.vue';

  import type { IRequestResponsePaginationData } from '@/utils/request';

  interface Props {
    filter: Record<string, any>,
    dataSource: (params: any)=> Promise<IRequestResponsePaginationData<any>>,
    isDoris: {
      enabled: boolean
    }
  }
  interface Emits {
    (e: 'clearSearch'): void
  }
  interface Exposes {
    loading: Ref<boolean>,
  }
  interface ResultFilter {
    filters: Array<{
      field_name: string,
      operator: string,
      filters: Array<string | number>
    }>
    [key: string]: any
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const initColumn: InstanceType<typeof Table>['$props']['columns'] = [
    {
      label: () => '',
      type: 'expand',
      width: '40px',
      fixed: true,
    },
    {
      label: () => t('操作起始时间'),
      render: ({ data }: {data: SearchModel}) => (
        data.start_time || '--'
      ),
      width: '180px',
      showOverflowTooltip: true,
    },
    {
      label: () => t('操作人'),
      field: 'username',
      render: ({ data }: {data: SearchModel}) => (
        data.username
          ? <RenderUser key={data.bk_receive_time} data={data}/>
          : '--'
      ),
      width: '100px',
      filter: {
        list: [],
      },
    },
    {
      label: () => t('来源系统(ID)'),
      field: 'system_info.name',
      render: ({ data }: {data: SearchModel}) => (
        data.system_id
          ? <RenderSystem data={data}/>
          : '--'
      ),
      minWidth: 140,
      filter: {
        list: [],
      },
    },
    {
      label: () => t('操作事件名(ID)'),
      field: 'snapshot_action_info.name',
      render: ({ data }: {data: SearchModel}) => {
        if (data.action_id) {
          if (!_.isEmpty(data.snapshot_action_info)) {
            return  <RenderAction key={data.bk_receive_time} data={data}/>;
          }
          return `-- (${data.action_id})`;
        }
        return '--';
      },
      minWidth: 160,
      filter: {
        list: [],
      },
    },
    {
      label: () => t('资源类型(ID)'),
      field: 'snapshot_resource_type_info.name',
      render: ({ data }: {data: SearchModel}) => {
        if (data.resource_type_id) {
          if (!_.isEmpty(data.snapshot_resource_type_info)) {
            return <RenderResource key={data.bk_receive_time} data={data}/>;
          }
          return `-- (${data.resource_type_id})`;
        }
        return '--';
      },
      minWidth: 150,
      filter: {
        list: [],
      },
    },
    {
      label: () => t('资源实例(ID)'),
      render: ({ data }: {data: SearchModel}) => {
        if (data.instance_name || data.instance_id) {
          if (!_.isEmpty(data.instance_data)) {
            return (data.instance_origin_data === '******' || data.instance_data === '******')
              ? (
              <span style="position:relative">
                <RenderAuthInstanceButton data={data} />
              </span>)
              : (
              <span style="position:relative">
                <DiffDetail data={data} v-show={!_.isEmpty(data.instance_origin_data)}/>
                <RenderInstance data={data}/>
              </span>
            );
          }
          return (<span>{data.instance_name || '--'} ({data.instance_id || '--'})</span>);
        }
        return '--';
      },
      minWidth: 160,
    },
    {
      label: () => t('操作结果(Code)'),
      field: 'result_code',
      minWidth: 160,
      render: ({ data }: {data: SearchModel}) => (
        data.result_code
          ? <RenderResult key={data.bk_receive_time} data={data}/>
          : '--'
      ),
      filter: {
        list: [],
      },
    },
    {
      label: () => t('操作途径'),
      field: 'access_type',
      render: ({ data }: {data: SearchModel}) => (
        <span>
          {data.access_type || '--'}
        </span>
      ),
      minWidth: 120,
      filter: {
        list: [],
      },
    },
  ];
  const rootRef = ref();
  const listRef = ref();
  const route = useRoute();
  const targetList = ref<Array<StandardFieldModel>>([]);
  const tableColumn = ref(initColumn);
  const isExpand = ref<Record<number, boolean>>({});
  const isInit = ref(false);
  const isLoading = computed(() => (listRef.value ? listRef.value.loading : true));

  watch(() => props.filter, () => {
    if (!isInit.value) {
      return;
    }
    listRef.value.fetchData(getFilter(props.filter));
  });

  watch(() => props.dataSource, () => {
    isInit.value = true;
    nextTick(() => {
      listRef.value.fetchData(getFilter(props.filter));
    });
  });

  const getFilter = (filter: Record<string, any>) => {
    if (!props.isDoris.enabled) {
      return filter;
    }
    const resultFilter: ResultFilter = {
      filters: [],
    };
    // 将查询参数添加到 filters 数组中
    Object.entries(filter).forEach(([k, v]) => {
      if (Object.keys(filedConfig).includes(k)) {
        resultFilter.filters.push({
          field_name: k,
          operator: 'include', // 一期暂时写死include
          filters: [v],
        });
      } else {
        resultFilter[k] = v;
      }
    });
    return resultFilter;
  };

  /**
   * 获取用户自定义字段
   */
  const {
    run: fetchCustomFields,
  } = useRequest(MetaManageService.fetchCustomFields, {
    defaultParams: {
      route_path: route.name,
    },
    defaultValue: [],
    onSuccess: (data) => {
      targetList.value = data || [];
      const customList = formatFields();
      tableColumn.value  = initColumn.concat(customList as []);
      // tableColumn.value = tableColumn.value.concat(fixedColum);
    },
    manual: true,
  });

  const getValueFromPath = (obj: any, path: string) => {
    // 将路径按点拆分成数组
    const keys = path.split('.');

    // 遍历路径数组，逐层获取对象的值
    return keys.reduce((acc, key) => {
      // 如果acc为空或undefined，直接返回undefined
      if (acc === undefined) {
        return undefined;
      }
      // 获取当前层级的值
      return acc[key];
    }, obj);
  };

  // 根据返回内容生成列筛选项
  const handleRequestSuccess = (data: Array<SearchModel>) => {
    tableColumn.value = tableColumn.value?.map((item) => {
      if (item.filter) {
        const values = data.map(obj => getValueFromPath(obj, item.field as string));
        const lists = [...new Set(values)].map(value => ({
          text: value === undefined ? '--' : value,
          value,
        }));
        // eslint-disable-next-line no-param-reassign
        item.filter = {
          list: lists,
          height: lists.length * 32,
          maxHeight: 192,
        };
      }
      return item;
    });
  };

  const handleUpdateField = () => {
    fetchCustomFields({
      route_path: route.name,
    });
  };
  /**
   * 合并新设置的列
   */
  const formatFields = () => {
    if (targetList.value.length) {
      const lists = targetList.value.map(item => ({
        label: () => t(item.description),
        resizable: true,
        field: item.field_name,
        minWidth: 140,
        showOverflowTooltip: true,
        render: ({ data }: {data: SearchModel}) =>  (data[item.field_name as keyof SearchModel] || '--'),
      }));
      return lists;
    }
    return [];
  };

  // 点击整行
  const handleRowClick = (event: Event, row: any, index: number) => {
    const tableRef = listRef.value.getTableRef();
    if (isExpand.value[index]) {
      tableRef.value.setRowExpand(row, false);
      isExpand.value[index] = false;
      return;
    }
    tableRef.value.setRowExpand(row, true);
    isExpand.value[index] = true;
  };
  const handleClearSearch = () => {
    emits('clearSearch');
  };

  defineExpose<Exposes>({
    loading: isLoading,
  });

</script>
<style lang="postcss">
.search-result-list {
  position: relative;
  padding: 24px;
  margin-top: 4px;
  background: #fff;
  border-radius: 2px;
  box-shadow: 0 2px 4px 0 rgb(25 25 41 / 5%);

  .bk-table .bk-table-fixed .column_fixed.column_fixed_left,
  .bk-table .bk-table-fixed .column_fixed.column_fixed_right {
    bottom: 71px !important;
  }
}

.highlight-cell {
  background: #fafbfd;

  .cell {
    color: #979ba5 !important;
  }
}

</style>

