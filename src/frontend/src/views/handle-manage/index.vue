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
      is-reassignment
      @batch="handleBatch"
      @change="handleSearchChange"
      @export="handleExport"
      @model-value-watch="handleModelValueWatch" />
    <div class="risk-manage-list">
      <render-list
        ref="listRef"
        :columns="tableColumn"
        :data-source="dataSource"
        :settings="settings"
        @clear-search="handleClearSearch"
        @on-setting-change="handleSettingChange"
        @request-success="handleRequestSuccess" />
    </div>

    <bk-dialog
      v-model:is-show="isShow"
      theme="primary"
      :title="t('批量转单')"
      @closed="handleClosed"
      @confirm="handleConfirm">
      <audit-form
        ref="formRef"
        form-type="vertical"
        :model="formData"
        :rules="rules">
        <bk-form-item
          :label="t('转单人员')"
          property="new_operators"
          required>
          <audit-user-selector
            v-model="formData.new_operators"
            :placeholder="t('请输入人员')" />
        </bk-form-item>
        <bk-form-item
          :label="t('处理说明')"
          property="description"
          required>
          <bk-input
            v-model.trim="formData.description"
            :maxlength="1000"
            :placeholder="t('请输入')"
            show-word-limit
            style="resize: none;"
            type="textarea" />
        </bk-form-item>
      </audit-form>
    </bk-dialog>
  </div>
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

  import MarkRiskLabel from '@views/risk-manage/list/components/mark-risk-label.vue';
  import RiskLevel from '@views/risk-manage/list/components/risk-level.vue';

  // import SearchBox from './search-box/index.vue';
  import FieldConfig from './components/config';

  import useTableSettings from '@/hooks/use-table-settings';

  const dataSource = RiskManageService.fetchTodoRiskList;
  interface ISettings{
    checked: Array<string>,
    fields: Record<string, any>[],
    size: string
  }

  const { messageWarn, messageSuccess } = useMessage();

  const strategyTagMap = ref<Record<string, string>>({});
  const { t } = useI18n();
  const router = useRouter();
  const route = useRoute();
  const { getSearchParamsPost } = useUrlSearch();
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

  const isShow = ref(false);
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
      fixed: true,
      minWidth: 180,
      render: ({ data }: { data: RiskManageModel }) => {
        const to = {
          name: 'handleManageDetail',
          params: {
            riskId: data.risk_id,
          },
        };
        return <router-link to={to}>
          <Tooltips data={data.risk_id} />
        </router-link>;
      },
    },
    {
      label: () => t('风险标题'),
      field: () => 'title',
      minWidth: 320,
      showOverflowTooltip: true,
      // render: ({ data }: { data: RiskManageModel }) => <Tooltips data={data.title} />,
    },
    {
      label: () => t('风险描述'),
      field: () => 'event_content',
      minWidth: 320,
      showOverflowTooltip: true,
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
      field: () => 'tags',
      width: 120,
      render: ({ data }: { data: RiskManageModel }) => {
        const tags = data.tags.map(item => strategyTagMap.value[item] || item);
        return <EditTag data={tags} key={data.strategy_id} />;
      },
    },
    {
      label: () => t('责任人'),
      field: () => 'operator',
      width: 160,
      render: ({ data }: { data: RiskManageModel }) => <EditTag data={data.operator} />,
    },
    {
      label: () => t('处理状态'),
      field: () => 'status',
      width: 110,
      render: ({ data }: { data: RiskManageModel }) => (
        data.status === 'closed' && data.experiences > 0
          ? (
          <div style='display: flex;align-items: center;height: 100%;'>
            <bk-tag
              theme={statusToMap[data.status].tag}>
              <p style='display: flex;align-items: center;'>
                <audit-icon type={statusToMap[data.status].icon} style={`margin-right: 6px;color: ${statusToMap[data.status].color || ''}` } />
                <span>{riskStatusCommon.value.find(item => item.id === data.status)?.name || '--'}</span>
              </p>
            </bk-tag>
              <bk-button text theme='primary' onClick={ () => handleToDetail(data, true)}>
              <audit-icon v-bk-tooltips={ t('已填写“风险总结”')} type="report" style='font-size: 14px;'/>
            </bk-button>
          </div>
          )
          : (
          <bk-tag
            theme={statusToMap[data.status].tag}>
            <p style='display: flex;align-items: center;'>
              <audit-icon type={statusToMap[data.status].icon} style={`margin-right: 6px;color: ${statusToMap[data.status].color || ''}` } />
              <span>{riskStatusCommon.value.find(item => item.id === data.status)?.name || '--'}</span>
            </p>
          </bk-tag>)
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
        const strategyName = strategyList.value
          .find(item => item.value === data.strategy_id)?.label;
        return strategyName
          ? (
            <router-link to={to} target='_blank'>
              <span>{`${strategyName}(${data.strategy_id})`}</span>
            </router-link>
          ) : (
          <span>--</span>
        );
      },
    },
    {
      label: () => t('首次发现时间'),
      field: () => 'event_time',
      sort: 'custom',
      width: 168,
      minWidth: 168,
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
      render: ({ data }: { data: RiskManageModel }) => <p>
        <auth-button
          text
          theme='primary'
          class='mr16'
          permission={data.permission.edit_risk_v2 || data.current_operator.includes(userInfo.value.username)}
          action-id='edit_risk_v2'
          resource={data.risk_id}
          onClick={() => handleToDetail(data)}>
          {t('处理')}
        </auth-button>
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
          </p>,
    },
  ] as Column[];
  const tableColumn = ref(initTableColumns);

  // let timeout: number| undefined = undefined;

  const listRef = ref();
  const searchBoxRef = ref();
  const searchModel = ref<Record<string, any>>({});

  const disabledMap: Record<string, string> = {
    risk_id: 'risk_id',
    title: 'title',
    risk_level: 'risk_level',
    // operator: 'operator',
    status: 'status',
    current_operator: 'current_operator',
    // last_operate_time: 'last_operate_time',
    // risk_label: 'risk_label',
  };

  const initSettings = () => {
    const fieldNames = selectedItemList.value.map(item => `event_data.${item.field_name}`);
    const list = selectedItemList.value.length > 0 ? tableColumn.value : initTableColumns;

    return  {
      fields: list?.reduce((res, item, index) => {
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
  // 批量操作
  const {
    run: batchTransRisk,
  } = useRequest(RiskManageService.batchTransRisk, {
    defaultValue: [],
    onSuccess() {
      messageSuccess(t('转单成功'));
    },
  });

  const formData = ref<Record<string, any>>({
    new_operators: [],
    description: '',
  });
  const handleGenerateReport = (data: RiskManageModel) => {
    router.push({
      name: 'riskManageDetail',
      params: {
        riskId: data.risk_id,
      },
    });
  };
  const formRef = ref();
  const rules = ref<Record<string, any>>({});
  const handleConfirm = () => {
    formRef.value.validate().then(() => {
      const selectedData = listRef.value.getSelection();
      batchTransRisk({
        risk_ids: selectedData.map((item: RiskManageModel) => item.risk_id),
        new_operators: formData.value.new_operators,
        description: formData.value.description,
      }).then(() => {
        isShow.value = false;
        handleClosed();
        fetchList();
      });
    });
  };
  const handleClosed = () => {
    formRef.value?.clearValidate();
    formData.value = {
      new_operators: [],
      description: '',
    };
  };
  // 批量操作
  const handleBatch = () => {
    const selectedData = listRef.value.getSelection();
    if (!selectedData.length) {
      messageWarn(t('请选择要操作的数据'));
      return;
    }
    isShow.value = true;
    nextTick(() => {
      formRef.value.clearValidate();
    });
  };
  // 导出数据
  const handleExport = () => {
    const selectedData = listRef.value.getSelection().map((i: any) => i.risk_id);
    if (!selectedData.length) {
      messageWarn(t('请选择要操作的数据'));
      return;
    }
    searchBoxRef.value.exportData(selectedData, 'todo');
  };
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
  // 获取userinfo
  const {
    data: userInfo,
  } = useRequest(AccountManageService.fetchUserInfo, {
    defaultValue: new AccountModel(),
    manual: true,
  });
  // const {
  //   run: fetchRiskList,
  // } = useRequest(RiskManageService.fetchTodoRiskList, {
  //   defaultValue: {
  //     total: 0,
  //     results: [],
  //     page: 1,
  //     num_pages: 1,
  //   },
  //   onSuccess(data) {
  //     const { results } = data;
  //     if (results && results.length) {
  //       results.forEach((item) => {
  //         const tmpItem = pollingDataMap.value[item.risk_id];
  //         if (!tmpItem) return;
  //         tmpItem.status = item.status;
  //         tmpItem.current_operator = item.current_operator;
  //         tmpItem.risk_label = item.risk_label;
  //         tmpItem.last_operate_time = item.last_operate_time;
  //       });
  //       startPolling(results);
  //     }
  //   },
  // });


  const {
    data: levelData,
    run: fetchRiskLevel,
  } = useRequest(StrategyManageService.fetchRiskLevel, {
    defaultValue: {},
  });

  // 记录轮训的数据
  // const pollingDataMap = ref<Record<string, RiskManageModel>>({});
  const handleRequestSuccess = ({ results }: {results: Array<RiskManageModel>}) => {
    selectedItemList.value =  searchBoxRef.value?.getSelectedItemList();
    if (JSON.stringify(tableColumn.value) !== JSON.stringify(initColumns())) {
      tableColumn.value =  initColumns();
    }
    settings.value =  useTableSettings('audit-all-risk-list-setting', initSettings).settings.value;
    // startPolling(results);
    if (!results.length) return;
    // 获取对应风险等级
    fetchRiskLevel({
      strategy_ids: results.map(item => item.strategy_id).join(','),
    });
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
  // // 开始轮训
  // const startPolling = (results: Array<RiskManageModel>) => {
  //   clearTimeout(timeout);
  //   pollingDataMap.value = {};
  //   results.forEach((item) => {
  //     if (item.status !== 'closed') {
  //       pollingDataMap.value[item.risk_id] = item;
  //     }
  //   });
  //   if (!Object.keys(pollingDataMap.value).length) return;
  //   timeout = setTimeout(() => {
  //     const params = getSearchParamsPost('event_filters');
  //     fetchRiskList({
  //       ...params,
  //       risk_id: Object.values(pollingDataMap.value).map(item => item.risk_id)
  //         .join(','),
  //     });
  //   }, 60 * 1000);
  // };

  const handleSettingChange = (setting: ISettings) => {
    localStorage.setItem('audit-handle-risk-list-setting', JSON.stringify(setting));
  };

  const handleToDetail = (data: RiskManageModel, needToRiskContent = false) => {
    const params: Record<string, any> = {
      name: 'handleManageDetail',
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
  // 搜索
  const handleSearchChange = (value: Record<string, any>, exValue:  Record<string, any>) => {
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
      status: '',
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
  const handleModelValueWatch = (val: any) => {
    if (val?.strategy_id?.length) {
      getEventFields({
        strategy_ids: val.strategy_id,
      });
    } else {
      getEventFields();
    }
  };
  onMounted(() => {
    getEventFields();
  });
  onUnmounted(() => {
    // clearTimeout(timeout);
  });

  onBeforeRouteLeave((to, from, next) => {
    if (to.name === 'handleManageDetail') {
      const params = getSearchParamsPost('event_filters');
      const paramsEventFilters = JSON.stringify(params.event_filters);
      const EventFiltersParams = {
        ...params,
        event_filters: paramsEventFilters,
      };
      // 保存当前查询参数到目标路由的 query 中
      // eslint-disable-next-line no-param-reassign
      to.query = {
        ...to.query,
        ...EventFiltersParams,
      };
    }
    next();
  });
</script>
<style lang='postcss'>
.risk-manage-list-page-wrap {
  padding-bottom: 44px;

  .risk-manage-list {
    margin-top: 16px;
    background-color: white;

    /* 解决表格悬浮超出 */

    /* .bk-table .bk-table-fixed .column_fixed {
      bottom: 2px !important;
    } */
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
