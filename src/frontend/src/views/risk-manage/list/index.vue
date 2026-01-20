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
  <div class="risk-manage-list-page-wrap">
    <search-box
      ref="searchBoxRef"
      :field-config="FieldConfig"
      is-export
      @change="handleSearchChange"
      @export="handleExport"
      @model-value-watch="handleModelValueWatch" />
    <div class="risk-manage-list">
      <div class="add-button">
        <bk-button
          theme="primary"
          @click="handleAddRisk">
          <audit-icon
            class="add-icon"
            type="add" />
          {{ t('新增风险') }}
        </bk-button>
      </div>
      <render-list
        ref="listRef"
        class="audit-highlight-table"
        :columns="tableColumn"
        :data-source="dataSource"
        :is-row-select-enable="handleSelectEnable"
        :row-class="handleRowClass"
        :settings="settings"
        @clear-search="handleClearSearch"
        @on-setting-change="handleSettingChange"
        @request-success="handleRequestSuccess" />
    </div>
  </div>
  <add-risk
    ref="addRiskRef"
    @add-success="handleAddRiskSuccess" />
  <!-- <handle-risk-label-dialog
    ref="handleRiskLabelDialogRef"
    @close="fetchList" /> -->
</template>

<script setup lang='tsx'>
  import type { Column } from 'bkui-vue/lib/table/props';
  import {
    nextTick,
    onMounted,
    onUnmounted,
    ref,
  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';
  import {
    onBeforeRouteLeave,
    useRoute,
    useRouter,
  } from 'vue-router';

  import AccountManageService from '@service/account-manage';
  import RiskManageService from '@service/risk-manage';
  import StrategyManageService from '@service/strategy-manage';

  import AccountModel from '@model/account/account';
  import type RiskManageModel from '@model/risk/risk';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';
  import useUrlSearch from '@hooks/use-url-search';

  import EditTag from '@components/edit-box/tag.vue';
  import Tooltips from '@components/show-tooltips-text/index.vue';

  import addRisk from './add-risk/index.vue';
  import FieldConfig from './components/config';
  import MarkRiskLabel from './components/mark-risk-label.vue';
  import RiskLevel from './components/risk-level.vue';

  import useTableSettings from '@/hooks/use-table-settings';

  const dataSource = RiskManageService.fetchRiskList;

  interface ISettings{
    checked: Array<string>,
    fields: Record<string, any>[],
    size: string
  }

  const { messageWarn } = useMessage();
  const strategyTagMap = ref<Record<string, string>>({});
  const { t } = useI18n();
  const { getSearchParamsPost } = useUrlSearch();
  const router = useRouter();
  const route = useRoute();
  let timeout: number| undefined = undefined;
  const statusToMap: Record<string, {
    tag: string,
    icon: string,
    color: string,
  }> = {
    new: {
      tag: 'info',
      icon: 'auto',
      color: '#3A84FF',
    },
    closed: {
      tag: '',
      icon: 'corret-fill',
      color: '#979BA5',
    },
    await_deal: {
      tag: 'warning',
      icon: 'daichuli',
      color: '#FF9E00',
    },
    for_approve: {
      tag: 'info',
      icon: 'auto',
      color: '#3A84FF',
    },
    auto_process: {
      tag: 'success',
      icon: 'taocanchulizhong',
      color: '#0CA668',
    },
  };

  interface FieldItem {
    id: string;
    field_name: string;
    display_name: string;
    operator?: string;
    value?: string | string[];
  }

  const selectedItemList = ref<FieldItem[]>([]);

  const initTableColumns = [
    {
      type: 'selection',
      label: '',
      width: 80,
      fixed: 'left',
    },
    {
      label: () => t('风险ID'),
      field: () => 'risk_id',
      width: 200,
      minWidth: 180,
      fixed: true,
      render: ({ data }: { data: RiskManageModel }) => {
        const to = {
          name: 'riskManageDetail',
          params: {
            riskId: data.risk_id,
          },
        };
        return (data.status === 'stand_by'
          ? <span>{data.risk_id}</span>
          : (<router-link to={to}>
          <Tooltips data={data.risk_id} />
        </router-link>));
      },
    },
    {
      label: () => t('风险标题'),
      field: () => 'title',
      showOverflowTooltip: true,
      minWidth: 320,
      // render: ({ data }: { data: RiskManageModel }) => <Tooltips data={data.title} />,
    },
    {
      label: () => t('风险描述'),
      field: () => 'event_content',
      showOverflowTooltip: true,
      minWidth: 320,
      // render: ({ data }: { data: RiskManageModel }) => <Tooltips data={data.event_content} />,
    },
    {
      label: () => t('风险等级'),
      field: () => 'risk_level',
      sort: 'custom',
      width: 120,
      render: ({ data }: { data: RiskManageModel }) => <>
          <RiskLevel levelData={levelData.value} data={data}></RiskLevel>
        </>,
    },
    {
      label: () => t('风险标签'),
      width: 110,
      field: () => 'tags',
      render: ({ data }: { data: RiskManageModel }) => {
        const tags = data.tags.map(item => strategyTagMap.value[item] || item);
        return <EditTag data={tags} key={data.strategy_id} />;
      },
    },
    {
      label: () => t('责任人'),
      field: () => 'operator',
      width: 200,
      render: ({ data }: { data: RiskManageModel }) => <EditTag data={data.operator || []} />,
    },
    {
      label: () => t('处理状态'),
      field: () => 'status',
      width: 130,
      render: ({ data }: { data: RiskManageModel }) => (
        // eslint-disable-next-line no-nested-ternary
        data.status === 'stand_by' ? (
           <span style='font-size: 14px;color: #3a84ff;'>
           <audit-icon  type="loading" style='font-size: 14px;color: #3a84ff; animation: spin 1s linear infinite' />  {t('风险创建中')}
          </span>
        )
          : (data.status === 'closed' && data.experiences > 0
            ? (
              <div style='display: flex;align-items: center;height: 100%;'>
                <bk-tag
                  theme={statusToMap[data.status].tag}>
                  <p style='display: flex;align-items: center;'>
                    <audit-icon type={statusToMap[data.status].icon} style={`margin-right: 6px;color: ${statusToMap[data.status].color || ''}`} />
                    <span>{riskStatusCommon.value.find(item => item.id === data.status)?.name || '--'}</span>
                  </p>
                </bk-tag>
                <bk-button text theme='primary' onClick={() => handleToDetail(data, true)}>
                  <audit-icon v-bk-tooltips={t('已填写“风险总结”')} type="report" style='font-size: 14px;' />
                </bk-button>
              </div>
            )
            : (
              <bk-tag
                theme={statusToMap[data.status].tag}>
                <p style='display: flex;align-items: center;'>
                  <audit-icon type={statusToMap[data.status].icon} style={`margin-right: 6px;color: ${statusToMap[data.status].color || ''}`} />
                  <span>{riskStatusCommon.value.find(item => item.id === data.status)?.name || '--'}</span>
                </p>
              </bk-tag>))
      ),
    },
    {
      label: () => t('当前处理人'),
      field: () => 'current_operator',
      width: 200,
      render: ({ data }: { data: RiskManageModel }) => <EditTag data={data.current_operator} />,
    },
    {
      label: () => t('关注人'),
      field: () => 'notice_users',
      width: 200,
      render: ({ data }: { data: RiskManageModel }) => <EditTag data={data.notice_users} />,
    },
    {
      label: () => t('风险命中策略(ID)'),
      field: () => 'strategy_id',
      width: 200,
      showOverflowTooltip: true,
      render: ({ data }: { data: RiskManageModel }) => {
        const to = {
          name: 'strategyList',
          query: {
            strategy_id: data.strategy_id,
          },
        };
        return <router-link to={to} target='_blank'>
                  <span>{`
                ${strategyList.value.find(item => item.value === data.strategy_id)?.label || '--'}(${data.strategy_id})`}</span>
              </router-link>;
      },
    },
    {
      label: () => t('首次发现时间'),
      field: () => 'event_time',
      sort: 'custom',
      width: 168,
      minWidth: 168,
      render: ({ data }: { data: RiskManageModel }) => data.event_time || '--',
    },
    {
      label: () => t('最后一次处理时间'),
      field: () => 'last_operate_time',
      // sort: 'custom',
      width: 160,
      render: ({ data }: { data: RiskManageModel }) => data.last_operate_time || '--',
    },
    {
      label: () => t('风险标记'),
      field: () => 'risk_label',
      width: 110,
      minWidth: 100,
      render: ({ data }: { data: RiskManageModel }) => <span
        class={{
          misreport: data.risk_label === 'misreport',
          'risk-label-status': true,
        }}>
          {data.risk_label === 'normal' ? t('正常') : t('误报')}
        </span>,
    },
    {
      label: () => t('操作'),
      width: 148,
      fixed: 'right',
      render: ({ data }: { data: RiskManageModel }) => (
        data.status === 'stand_by'
          ? <div>
            <bk-button text  class='mr16'>{t('--')}</bk-button>
          </div>
          : (<p>
          {
            ['for_approve', 'auto_process'].includes(data.status)
              ? (
                <bk-button
                  v-bk-tooltips={t('当前状态不支持人工处理')}
                  text
                  theme='primary'
                  class='mr16 is-disabled'>
                  {t('处理')}
                </bk-button>
              )
              : (
                <auth-button
                  text
                  theme='primary'
                  class='mr16'
                  permission={data.permission.process_risk || data.current_operator.includes(userInfo.value.username)}
                  action-id='process_risk'
                  resource={data.risk_id}
                  onClick={() => handleToDetail(data)}>
                  {t('处理')}
                </auth-button>
            )
          }
          {
            data.status === 'auto_process'
              ? <bk-button text theme='primary'
                class="is-disabled"
                v-bk-tooltips={{
                  content: data.risk_label === 'normal'
                    ? t('“套餐处理中”的风险单暂时不支持直接标记误报；请点开风险单详情，终止套餐或等套餐执行完毕后再标记误报。')
                    : t('“套餐处理中”的风险单暂时不支持直接解除误报；请点开风险单详情，终止套餐或等套餐执行完毕后再标记误报。'),
                }}>
                  {data.risk_label === 'normal' ? t('标记误报') : t('解除误报')}
                </bk-button>
              : <MarkRiskLabel
                  onUpdate={() => fetchList()}
                  userInfo={userInfo.value}
                  data={data} />
          }
          <bk-dropdown
            trigger="click"
            style="margin-left: 8px">
            {{
              default: () => <bk-button text>
                <audit-icon type="more" />
              </bk-button>,
              content: () => (
                <bk-dropdown-menu>
                  <bk-dropdown-item>
                    <auth-button
                      style="width: 100%;"
                      actionId="edit_risk_v2"
                      permission={data.permission.edit_risk_v2}
                      resource={data.strategy_id}
                      onClick={() => handleGenerateReport(data)}
                      text>
                      {data.has_report ? t('编辑调查报告') : t('生成调查报告')}
                    </auth-button>
                  </bk-dropdown-item>
                </bk-dropdown-menu>
              ),
            }}
          </bk-dropdown>
          </p>)
      ),
    },
  ] as Column[];

  const tableColumn = ref(initTableColumns);


  const listRef = ref();
  const addRiskRef = ref();
  const searchBoxRef = ref();
  const searchModel = ref<Record<string, any>>({});

  const disabledMap: Record<string, string> = {
    risk_id: 'risk_id',
    title: 'title',
    risk_level: 'risk_level',
    status: 'status',
    current_operator: 'current_operator',
  };
  const handleSelectEnable = (item: any) => {
    if (item.row.status === 'stand_by') {
      return false;
    }
    return true;
  };
  const initSettings = () => {
    const fieldNames = selectedItemList.value.map(item => `event_data.${item.field_name}`);
    const list = selectedItemList.value.length > 0 ? tableColumn.value : initTableColumns;
    return  {
      fields: list.reduce((res:any, item: any, index: number) => {
        if (item.field) {
          const fieldValue = typeof item.field === 'function' ? item.field(item, index) : item.field;
          const labelValue = typeof item.label === 'function' ? item.label(item, index) : item.label;
          res.push({
            label: String(labelValue),
            field: String(fieldValue),
            disabled: !!disabledMap[String(fieldValue)] ||  fieldNames.includes(String(fieldValue)),
          });
        }
        return res;
      }, [] as Array<{
        label: string, field: string, disabled: boolean,
      }>) || [],
      checked: ['risk_id', 'title', 'event_content', 'risk_level', 'tags', 'operator', 'status', 'current_operator', 'notice_users', 'strategy_id', 'event_time', 'last_operate_time', 'risk_label'].concat(fieldNames),
      showLineHeight: false,
      trigger: 'manual' as const,  // 添加 as const 类型断言
    };
  };
  const settings  = ref();
  settings.value = useTableSettings('audit-all-risk-list-setting', initSettings).settings.value;

  // 导出数据
  const handleExport = () => {
    const selectedData = listRef.value.getSelection().map((i: any) => i.risk_id.toString());
    if (!selectedData.length) {
      messageWarn(t('请选择要操作的数据'));
      return;
    }
    searchBoxRef.value.exportData(selectedData, 'all');
  };

  const {
    run: getEventFields,
  } = useRequest(RiskManageService.fetchEventFields, {
    defaultValue: [],
    onSuccess: (data) => {
      const eventFields = data.map((item: any) => ({
        ...item,
      }));
      searchBoxRef.value?.initSelectedItems(eventFields);
    },
  });

  // 获取userinfo
  const {
    data: userInfo,
  } = useRequest(AccountManageService.fetchUserInfo, {
    defaultValue: new AccountModel(),
    manual: true,
  });
  const {
    data: riskStatusCommon,
  } = useRequest(RiskManageService.fetchRiskStatusCommon, {
    manual: true,
    defaultValue: [],
  });
  const {
    data: strategyList,
  } = useRequest(StrategyManageService.fetchAllStrategyList, {
    manual: true,
    defaultValue: [],
  });
  // 获取标签列表
  useRequest(RiskManageService.fetchRiskTags, {
    defaultParams: {
      page: 1,
      page_size: 1,
    },
    defaultValue: [],
    manual: true,
    onSuccess: (data) => {
      data.forEach((item) => {
        strategyTagMap.value[item.id] = item.name;
      });
    },
  });

  const handleRowClass = (row: Record<string, any>) => {
    const addEventRiskIds = JSON.parse(sessionStorage.getItem('addEventRiskIds') || '[]');
    if (row.status === 'stand_by' || addEventRiskIds.includes(row.risk_id)) {
      return 'new-row';
    }
  };


  const {
    data: levelData,
    run: fetchRiskLevel,
  } = useRequest(StrategyManageService.fetchRiskLevel, {
    defaultValue: {},
  });

  const {
    run: fetchRiskList,
  } = useRequest(RiskManageService.fetchRiskList, {
    defaultValue: {
      results: [],
      page: 0,
      num_pages: 0,
      total: 0,
    },
  });

  // 记录轮训的数据
  // const pollingDataMap = ref<Record<string, RiskManageModel>>({});
  const handleRequestSuccess = ({ results }: {results: Array<RiskManageModel>}) => {
    window.changeConfirm = false;
    selectedItemList.value =  searchBoxRef.value?.getSelectedItemList();
    if (JSON.stringify(tableColumn.value) !== JSON.stringify(initColumns())) {
      tableColumn.value =  initColumns();
    }
    settings.value =  useTableSettings('audit-all-risk-list-setting', initSettings).settings.value;
    if (!results.length) return;
    // 获取对应风险等级
    fetchRiskLevel({
      strategy_ids: results.map(item => item.strategy_id).join(','),
    });
    if (results.some(item => item.status === 'stand_by')) {
      // 执行定时器
      timeout = setTimeout(() => {
        const addEventRiskIds = JSON.parse(sessionStorage.getItem('addEventRiskIds') || '[]');
        if (addEventRiskIds.length === 0) {
          listRef.value?.initData();
        }
        fetchRiskList({
          risk_id: addEventRiskIds.join(','),
          page: 1,
          page_size: 20,
        }).then((data) => {
          listRef.value?.initListData(data.results, 'risk_id');
        });
      }, 5000);
    } else {
      // 消除定时器
      if (timeout) {
        clearTimeout(timeout);
        timeout = undefined;
        tableColumn.value =  initColumns();
      }
    }
  };

  const  initColumns = () => {
    if (selectedItemList.value.length === 0) {
      return [...initTableColumns];
    }
    const params = getSearchParamsPost('event_filters');
    const columns = [...initTableColumns]; // 创建副本避免修改原始数组
    // 选中的列
    let selectedColumns: Column[] = [];
    const noValue = selectedItemList.value.filter(item => item.value !== '');
    selectedColumns = noValue.map((item) => {
      const sortVal = params?.order_field === `event_data.${item.field_name}` ? params?.order_type :  '';
      return {
        label: item.display_name,
        field: `event_data.${item.field_name}`,
        width: 120,
        showOverflowTooltip: true,
        sort: {
          value: sortVal,
        },
        render: (args: any) => {
          const data = args.data as RiskManageModel;
          return <span>{data?.event_data?.[item.field_name] || '--'}</span>;
        },
      };
    }) as Column[];
    // 在操作列之前插入选中的列
    const operationColumnIndex = columns.findIndex(col => col.fixed === 'right');
    const insertIndex = operationColumnIndex > -1 ? operationColumnIndex : columns.length - 1;
    columns.splice(insertIndex, 0, ...selectedColumns);
    return  columns;
  };


  const handleToDetail = (data: RiskManageModel, needToRiskContent = false) => {
    const params: Record<string, any> = {
      name: 'riskManageDetail',
      params: {
        riskId: data.risk_id,
      },
      query: {
        tab: 'handleRisk',
      },
    };
    if (needToRiskContent) {
      params.query.scrollToContent = 1;
    }
    router.push(params);
  };
  const handleSettingChange = (setting: ISettings) => {
    localStorage.setItem('audit-all-risk-list-setting', JSON.stringify(setting));
  };

  interface SearchFormValue {
    strategy_id?: string[];
    // 可能还有其他字段，但根据当前使用场景，我们只关心 strategy_id
  }

  const handleModelValueWatch = (val: SearchFormValue) => {
    if (val?.strategy_id?.length) {
      getEventFields({
        strategy_ids: val.strategy_id,
      });
    } else {
      getEventFields();
    }
  };
  // 搜索
  const handleSearchChange = (value: Record<string, any>, exValue:  Record<string, any>, isClear?: boolean) => {
    if (!isClear) {
      sessionStorage.removeItem('addEventRiskIds');
    }
    searchModel.value = {
      ...value,
      event_filters: exValue };
    listRef.value.initTableHeight();
    fetchList();
  };
  const handleClearSearch = () => {
    searchBoxRef.value.clearValue();
  };
  const fetchList = () => {
    if (!listRef.value) return;
    const params = {
      risk_id: '',
      tags: '',
      start_time: '',
      end_time: '',
      strategy_id: route.query.strategy_id || '',
      operator: '',
      current_operator: '',
      status: '',
      risk_label: '',
      event_content: '',
      risk_level: '',
      use_bkbase: true,
      title: '',
      notice_users: '',
    };
    const dataParams: Record<string, any> = {
      ...params,
      ...searchModel.value,
    };
    listRef.value.fetchData(dataParams);
  };

  const handleGenerateReport = (data: RiskManageModel) => {
    router.push({
      name: 'riskManageDetail',
      params: {
        riskId: data.risk_id,
      },
    });
  };

  // 新增风险
  const handleAddRisk = () => {
    addRiskRef.value.show();
  };
  // 新增风险成功
  const handleAddRiskSuccess = () => {
    searchBoxRef.value.clearValue();
  };


  onMounted(() => {
    nextTick(() => {
      getEventFields();
      sessionStorage.removeItem('addEventRiskIds');
    });
  });
  onUnmounted(() => {
    if (timeout) {
      clearTimeout(timeout);
      timeout = undefined;
    }
  });

  onBeforeRouteLeave((to, from, next) => {
    if (to.name === 'riskManageDetail') {
      const params = getSearchParamsPost('event_filters');
      const paramsEventFilters = JSON.stringify(params.event_filters);
      const EventFiltersparams = {
        ...params,
        event_filters: paramsEventFilters,
      };
      // replaceSearchParams(params);
      // 保存当前查询参数到目标路由的 query 中
      // eslint-disable-next-line no-param-reassign
      to.query = {
        ...to.query,
        ...EventFiltersparams,
      };
    }
    next();
  });
</script>
<style lang='postcss'>
@keyframes spin {
  0% {
    transform: rotate(0deg);
  }

  100% {
    transform: rotate(360deg);
  }
}

.risk-manage-list-page-wrap {
  .risk-manage-list {
    padding: 5px 20px;
    margin-top: 16px;
    background-color: white;

    /* 解决表格悬浮超出 */

    /* .bk-table .bk-table-fixed .column_fixed {
      bottom: 0 !important;
    } */
    .add-button {
      padding-bottom: 5px;

      .add-icon {
        margin-right: 5px;
        font-size: 12px;
      }
    }
  }

}

.risk-label-status {
  padding: 1px 8px;
  font-size: 12px;
  color: #14a568;
  background-color: #e4faf0;
  border: 1px solid rgb(20 165 104 / 30%);
  border-radius: 11px;
}

.risk-label-status.misreport {
  color: #ea3536;
  background: #fedddc99;
  border: 1px solid #ea35364d;
}
</style>
