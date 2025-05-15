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
      ref="listRef"
      :columns="tableColumn"
      :data-source="dataSource"
      :settings="settings"
      @clear-search="handleClearSearch"
      @request-success="handleRequestSuccess"
      @row-click="handleRowClick">
      <!-- <template #expandRow="{ row }">
        <row-expand-content
          :data="row"
          :filter="filter" />
      </template> -->
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

  import FieldStatisticPopover from './components/field-statistic-popover/index.vue';
  import RenderAction from './components/render-field/action.vue';
  import RenderAuthInstanceButton from './components/render-field/auth-instance-button.vue';
  import RenderInstance from './components/render-field/instance.vue';
  import RenderResource from './components/render-field/resource.vue';
  import RenderResult from './components/render-field/result.vue';
  import RenderSystem from './components/render-field/system.vue';
  import RenderUser from './components/render-field/user.vue';
  import RenderTable from './components/render-table.vue';
  import DiffDetail from './components/row-diff-detail/index.vue';
  // import RowExpandContent from './components/row-expand-content/index.vue';
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
    (e: 'updateTotal', total: number): void
  }
  interface Exposes {
    loading: Ref<boolean>,
    tableSearchModel: Ref<Record<string, any>>,
  }
  interface ResultFilter {
    conditions: Array<{
      field: {
        raw_name: string,
        field_type?: string,
        keys: Array<string>,
      },
      operator: string,
      filters: Array<string | number>,
    }>
    [key: string]: any
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const initColumn: InstanceType<typeof Table>['$props']['columns'] = [
    // {
    //   label: () => '',
    //   type: 'expand',
    //   width: '40px',
    //   fixed: true,
    // },
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
      label: () =>  <div style="display: flex; align-items: center;">
        <label>{ t('来源系统(ID)') }</label>
        <FieldStatisticPopover
          fieldName="system_id"
          params={ tableSearchModel.value } />
      </div>,
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
      label: () => <div style="display: flex; align-items: center;">
        <label>{ t('操作事件名(ID)') }</label>
        <FieldStatisticPopover
          fieldName="action_id"
          params={ tableSearchModel.value } />
      </div>,
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
      label: () => <div style="display: flex; align-items: center;">
        <label>{ t('资源类型(ID)') }</label>
        <FieldStatisticPopover
          fieldName="resource_type_id"
          params={ tableSearchModel.value } />
      </div>,
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
  const settings = {
    fields: [],
    checked: [],
    showLineHeight: false,
  };
  const rootRef = ref();
  const listRef = ref();
  const route = useRoute();
  const targetList = ref<Array<StandardFieldModel>>([]);
  const tableColumn = ref(initColumn);
  const isExpand = ref<Record<number, boolean>>({});
  const isLoading = computed(() => (listRef.value ? listRef.value.loading : true));
  // 经过表格处理的查询参数
  const tableSearchModel = computed(() => (listRef.value ? listRef.value.getParamsMemo().value : {}));

  // Doris接口查询的参数需要调整
  const getFilter = (filter: Record<string, any>) => {
    if (!props.isDoris.enabled) {
      return filter;
    }
    const resultFilter: ResultFilter = {
      conditions: [],
    };
    // 将查询参数添加到 conditions 数组中
    Object.entries(filter).forEach(([k, v]) => {
      const config = filedConfig[k];
      if (config && config.operator) {
        let value: Array<string> = [];
        if (config.service || config.type === 'select' || config.type === 'user-selector') {
          value = v.split(',');
        } else {
          value.push(v);
        }

        // 检查 field 是否为数组字符串格式
        if (k.startsWith('[') && k.endsWith(']')) {
          try {
            const parsedKeys = JSON.parse(k);
            if (Array.isArray(parsedKeys) && parsedKeys.length > 0) {
              resultFilter.conditions.push({
                field: {
                  raw_name: parsedKeys[0],
                  // field_type: 'str',
                  keys: parsedKeys.slice(1), // 排除第一个元素后的数组
                },
                operator: config.operator,
                filters: value,
              });
            } else {
              // 如果解析后不是数组或数组为空，按原样处理
              resultFilter.conditions.push({
                field: {
                  raw_name: k,
                  // field_type: 'str',
                  keys: [],
                },
                operator: config.operator,
                filters: value,
              });
            }
          } catch (e) {
            // 解析 JSON 失败，按原样处理
            resultFilter.conditions.push({
              field: {
                raw_name: k,
                // field_type: 'str',
                keys: [],
              },
              operator: config.operator,
              filters: value,
            });
          }
        } else {
          // 不是数组字符串格式，按原样处理
          resultFilter.conditions.push({
            field: {
              raw_name: k,
              // field_type: 'str',
              keys: [],
            },
            operator: config.operator,
            filters: value,
          });
        }
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
  const handleRequestSuccess = (data: Array<SearchModel>, total: number) => {
    emits('updateTotal', total);
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
    listRef.value.fetchData(getFilter(props.filter));
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

  watch(() => props.filter, () => {
    nextTick(() => {
      listRef.value.fetchData(getFilter(props.filter));
    });
  }, {
    immediate: true,
  });

  defineExpose<Exposes>({
    loading: isLoading,
    tableSearchModel,
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

