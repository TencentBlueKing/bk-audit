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
      <tdesign-list
        ref="listRef"
        :columns="initTableColumns"
        :data-source="dataSource"
        need-empty-search-tip
        row-key="risk_id"
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
  import {
    computed,
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
  import SearchBox from '@components/search-box/index.vue';
  import Tooltips from '@components/show-tooltips-text/index.vue';
  import TdesignList from '@components/tdesign-list/index.vue';

  import MarkRiskLabel from '@views/risk-manage/list/components/mark-risk-label.vue';
  import RiskLevel from '@views/risk-manage/list/components/risk-level.vue';

  import FieldConfig from './components/config';

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
    processing: {
      tag: 'info',
      icon: 'loading',
      color: '#3A84FF',
    },
  };

  const isShow = ref(false);

  // 直接按 TDesign PrimaryTable 格式定义列配置
  const initTableColumns = [
    {
      // 选择列
      type: 'multiple',
      colKey: 'row-select',
      width: 80,
      fixed: 'left',
    },
    {
      title: t('风险ID'),
      colKey: 'risk_id',
      width: 200,
      minWidth: 180,
      fixed: 'left',
      ellipsis: true,
      cell: (h: any, { row }: { row: RiskManageModel }) => {
        const to = {
          name: 'handleManageDetail',
          params: {
            riskId: row.risk_id,
          },
        };
        return <router-link to={to}>
          <Tooltips data={row.risk_id} />
        </router-link>;
      },
    },
    {
      title: t('风险标题'),
      colKey: 'title',
      minWidth: 320,
      ellipsis: true,
    },
    {
      title: t('风险描述'),
      colKey: 'event_content',
      minWidth: 320,
      ellipsis: true,
    },
    {
      title: t('风险等级'),
      colKey: 'risk_level',
      width: 120,
      sortType: 'all',
      sorter: true,
      cell: (h: any, { row }: { row: RiskManageModel }) => <>
        <RiskLevel levelData={levelData.value} data={row}></RiskLevel>
      </>,
    },
    {
      title: t('风险标签'),
      colKey: 'tags',
      width: 120,
      cell: (h: any, { row }: { row: RiskManageModel }) => {
        const tags = row.tags.map(item => strategyTagMap.value[item] || item);
        return <EditTag data={tags} key={row.strategy_id} />;
      },
    },
    {
      title: t('责任人'),
      colKey: 'operator',
      width: 160,
      cell: (h: any, { row }: { row: RiskManageModel }) => <EditTag data={row.operator} />,
    },
    {
      title: t('处理状态'),
      colKey: 'status',
      width: 110,
      cell: (h: any, { row }: { row: RiskManageModel }) => (
        row.status === 'closed' && row.experiences > 0
          ? (
          <div style='display: flex;align-items: center;height: 100%;'>
            <bk-tag
              theme={statusToMap[row.status]?.tag}>
              <p style='display: flex;align-items: center;'>
                <audit-icon type={statusToMap[row.status]?.icon} style={`margin-right: 6px;color: ${statusToMap[row.status]?.color || ''}`} />
                <span>{riskStatusCommon.value.find(item => item.id === row.status)?.name || '--'}</span>
              </p>
            </bk-tag>
            <bk-button text theme='primary' onClick={() => handleToDetail(row, true)}>
              <audit-icon v-bk-tooltips={t('已填写"风险总结"')} type="report" style='font-size: 14px;' />
            </bk-button>
          </div>
        )
          : (
          <bk-tag
            theme={statusToMap[row.status]?.tag}>
            <p style='display: flex;align-items: center;'>
              <audit-icon type={statusToMap[row.status]?.icon} style={`margin-right: 6px;color: ${statusToMap[row.status]?.color || ''}`} />
              <span>{riskStatusCommon.value.find(item => item.id === row.status)?.name || '--'}</span>
            </p>
          </bk-tag>)
      ),
    },
    {
      title: t('当前处理人'),
      colKey: 'current_operator',
      width: 200,
      cell: (h: any, { row }: { row: RiskManageModel }) => <EditTag data={row.current_operator} />,
    },
    {
      title: t('关注人'),
      colKey: 'notice_users',
      width: 200,
      cell: (h: any, { row }: { row: RiskManageModel }) => <EditTag data={row.notice_users} />,
    },
    {
      title: t('风险命中策略(ID)'),
      colKey: 'strategy_id',
      width: 200,
      ellipsis: true,
      cell: (h: any, { row }: { row: RiskManageModel }) => {
        const to = {
          name: 'strategyList',
          query: {
            strategy_id: row.strategy_id,
          },
        };
        const strategyName = strategyList.value
          .find(item => item.value === row.strategy_id)?.label;
        return strategyName
          ? (
          <router-link to={to} target='_blank'>
            <span>{`${strategyName}(${row.strategy_id})`}</span>
          </router-link>
          ) : (
          <span>--</span>
        );
      },
    },
    {
      title: t('首次发现时间'),
      colKey: 'event_time',
      width: 168,
      minWidth: 168,
      sortType: 'all',
      sorter: true,
    },
    {
      title: t('最后一次处理时间'),
      colKey: 'last_operate_time',
      width: 160,
      sorter: true,
      cell: (h: any, { row }: { row: RiskManageModel }) => row.last_operate_time || '--',
    },
    {
      title: t('事件调查报告'),
      colKey: 'has_report',
      width: 160,
      filter: {
        type: 'single',
        showConfirmAndReset: true,
        resetValue: undefined,
        list: [
          {
            label: t('已生成'),
            value: true,
          },
          {
            label: t('未生成'),
            value: false,
          },
        ],
      },
      cell: (h: any, { row }: { row: RiskManageModel }) => <bk-tag
    >{row.has_report ? t('已生成') : t('未生成')}</bk-tag>,
    },
    {
      title: t('风险标记'),
      colKey: 'risk_label',
      width: 110,
      cell: (h: any, { row }: { row: RiskManageModel }) => <span
      class={{
        misreport: row.risk_label === 'misreport',
        'risk-label-status': true,
      }}>
      {row.risk_label === 'normal' ? t('正常') : t('误报')}
    </span>,
    },
    {
      title: t('操作'),
      colKey: 'action',
      width: 180,
      fixed: 'right',
      cell: (h: any, { row }: { row: RiskManageModel }) => <p>
      <auth-button
        text
        theme='primary'
        class='mr16'
        permission={row.permission.process_risk || row.current_operator.includes(userInfo.value.username)}
        action-id='process_risk'
        resource={row.risk_id}
        onClick={() => handleToDetail(row)}>
        {t('处理')}
      </auth-button>
      {
        row.status === 'auto_process'
          ? <bk-button text theme='primary'
            class="is-disabled"
            v-bk-tooltips={{
              content: row.risk_label === 'normal'
                ? t('"套餐处理中"的风险单暂时不支持直接标记误报；请点开风险单详情，终止套餐或等套餐执行完毕后再标记误报。')
                : t('"套餐处理中"的风险单暂时不支持直接解除误报；请点开风险单详情，终止套餐或等套餐执行完毕后再标记误报。'),
            }}>
            {row.risk_label === 'normal' ? t('标记误报') : t('解除误报')}
          </bk-button>
          : <MarkRiskLabel
            onUpdate={() => fetchList()}
            userInfo={userInfo.value}
            data={row} />
      }
      <bk-dropdown
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
                  permission={row.permission.edit_risk_v2}
                  resource={row.strategy_id}
                  onClick={() => handleGenerateReport(row)}
                  text>
                  {row.has_report ? t('编辑调查报告') : t('创建调查报告')}
                </auth-button>
              </bk-dropdown-item>
            </bk-dropdown-menu>
          ),
        }}
      </bk-dropdown>
    </p>,
    },
  ];
  const listRef = ref();
  const searchBoxRef = ref();
  const searchModel = ref<Record<string, any>>({});

  // 默认的可配置列键
  const defaultSettings = ['risk_id', 'title', 'event_content', 'risk_level', 'tags', 'operator', 'status', 'current_operator', 'notice_users', 'strategy_id', 'event_time', 'last_operate_time', 'has_report', 'risk_label'];

  // 从 localStorage 读取保存的设置
  const settings = computed(() => {
    const jsonStr = localStorage.getItem('audit-handle-risk-list-setting');
    if (jsonStr) {
      try {
        const savedSettings = JSON.parse(jsonStr);
        // 如果保存的设置中有 checked 字段，使用它；否则使用默认设置
        return savedSettings.checked && Array.isArray(savedSettings.checked)
          ? savedSettings.checked
          : defaultSettings;
      } catch (e) {
        console.error('本地设置解析失败，使用默认配置', e);
        return defaultSettings;
      }
    }
    return defaultSettings;
  });
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
      query: {
        openEditReport: data.has_report ? 'true' : 'false',
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

  const handleRequestSuccess = ({ results }: { results: Array<RiskManageModel> }) => {
    if (!results.length) return;
    // 获取对应风险等级
    fetchRiskLevel({
      strategy_ids: results.map(item => item.strategy_id).join(','),
    });
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
      title: '',
      notice_users: '',
    };
    const dataParams: Record<string, any> = {
      ...params,
      ...searchModel.value,
    };
    // 如果没有 sort 参数，设置默认排序
    if (!dataParams.sort) {
      dataParams.sort = ['-risk_level', '-event_time', '-risk_id'];
    }
    // use_bkbase 参数已移除，由 event_filters 自动决定
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
