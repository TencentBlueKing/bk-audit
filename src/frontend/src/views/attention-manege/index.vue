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
      @change="handleSearchChange" />
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
  </div>
</template>

<script setup lang='tsx'>
  import {
    computed,
    onUnmounted,
    ref,
  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';
  import {
    onBeforeRouteLeave,
    useRouter,
  } from 'vue-router';

  import RiskManageService from '@service/risk-manage';
  import StrategyManageService from '@service/strategy-manage';

  import type RiskManageModel from '@model/risk/risk';

  import useRequest from '@hooks/use-request';
  import useUrlSearch from '@hooks/use-url-search';

  import EditTag from '@components/edit-box/tag.vue';
  import Tooltips from '@components/show-tooltips-text/index.vue';

  import RiskLevel from '@views/handle-manage/components/risk-level.vue';

  import SearchBox from './search-box/index.vue';

  const dataSource = RiskManageService.fetchWatchRiskList;
  interface ISettings{
    checked: Array<string>,
    fields: Record<string, any>[],
    size: string
  }
  const strategyTagMap = ref<Record<string, string>>({});
  const { t } = useI18n();
  const router = useRouter();
  const { getSearchParams } = useUrlSearch();
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

  const tableColumn = [
    {
      label: () => t('风险ID'),
      field: () => 'risk_id',
      width: 200,
      fixed: true,
      minWidth: 180,
      render: ({ data }: { data: RiskManageModel }) => {
        const to = {
          name: 'attentionManageDetail',
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
      render: ({ data }: { data: RiskManageModel }) => <Tooltips data={data.title} />,
    },
    {
      label: () => t('风险描述'),
      field: () => 'event_content',
      minWidth: 320,
      render: ({ data }: { data: RiskManageModel }) => <Tooltips data={data.event_content} />,
    },
    {
      label: () => t('风险等级'),
      field: () => 'risk_id',
      minWidth: 320,
      render: ({ data }: { data: RiskManageModel }) => <>
          <RiskLevel levelData={levelData.value} data={data}></RiskLevel>
        </>,
    },
    {
      label: () => t('风险标签'),
      field: () => 'tags',
      minWidth: 200,
      render: ({ data }: { data: RiskManageModel }) => {
        const tags = data.tags.map(item => strategyTagMap.value[item] || item);
        return <EditTag data={tags} key={data.strategy_id} />;
      },
    },
    {
      label: () => t('责任人'),
      field: () => 'operator',
      minWidth: 148,
      render: ({ data }: { data: RiskManageModel }) => <EditTag data={data.operator} />,
    },
    {
      label: () => t('处理状态'),
      field: () => 'status',
      minWidth: 148,
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
      minWidth: 148,
      render: ({ data }: { data: RiskManageModel }) => <EditTag data={data.current_operator} />,
    },
    {
      label: () => t('风险标记'),
      field: () => 'risk_label',
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
      label: () => t('首次发现时间'),
      field: () => 'event_time',
      sort: 'custom',
      width: 168,
      minWidth: 168,
    },
    {
      label: () => t('风险命中策略(ID)'),
      field: () => 'strategy_id',
      minWidth: 200,
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
            <router-link to={to}>
              <Tooltips data={`${strategyName}(${data.strategy_id})`} />
            </router-link>
          ) : (
          <span>--</span>
        );
      },
    },
    {
      label: () => t('关注人'),
      field: () => 'notice_users',
      minWidth: 160,
      render: ({ data }: { data: RiskManageModel }) => <EditTag data={data.notice_users} />,
    },
    {
      label: () => t('最后一次处理时间'),
      field: () => 'last_operate_time',
      // sort: 'custom',
      minWidth: 168,
      render: ({ data }: { data: RiskManageModel }) => data.last_operate_time || '--',
    },
  ];
  let timeout: number| undefined = undefined;


  const listRef = ref();
  const searchBoxRef = ref();
  const searchModel = ref<Record<string, any>>({});

  const disabledMap: Record<string, string> = {
    risk_id: 'risk_id',
    event_content: 'event_content',
    operator: 'operator',
    status: 'status',
    current_operator: 'current_operator',
  };
  const initSettings = () => ({
    fields: tableColumn.reduce((res, item) => {
      if (item.field) {
        res.push({
          label: item.label(),
          field: item.field(),
          disabled: !!disabledMap[item.field()],
        });
      }
      return res;
    }, [] as Array<{
      label: string, field: string, disabled: boolean,
    }>),
    checked: [
      'risk_id',
      'event_content',
      'tags',
      'operator',
      'status',
      'current_operator',
      'risk_label',
      'event_time',
      'title',
      'notice_users',
      'strategy_id',
    ],
    showLineHeight: false,
    trigger: 'manual' as const,  // 添加 as const 类型断言
  });
  const settings = computed(() => {
    const defaultSettings = initSettings(); // 获取最新的默认配置
    const jsonStr = localStorage.getItem('audit-attention-risk-list-setting');

    if (!jsonStr) return defaultSettings;

    try {
      const savedSettings = JSON.parse(jsonStr);

      // 字段合并：以默认配置为基础，合并用户保存的字段状态
      const mergedFields = defaultSettings.fields.map((defaultField) => {
        const savedField = savedSettings.fields?.find((f: any) => f.field === defaultField.field);
        // 保留新字段配置，仅继承用户设置的disabled状态
        return savedField
          ? { ...defaultField, disabled: savedField.disabled }
          : defaultField;
      });

      // 选中的字段合并：保留用户选择 + 新增的默认选中字段
      const savedCheckedSet = new Set(savedSettings.checked || []);
      const newDefaultChecked = defaultSettings.checked
        .filter(field => !savedCheckedSet.has(field)); // 找出新增的默认选中字段
      const mergedChecked = [...(savedSettings.checked || []), ...newDefaultChecked]
        .filter(field => mergedFields.some(f => f.field === field)); // 过滤无效字段

      return {
        ...defaultSettings,       // 保留最新默认配置的其他属性
        fields: mergedFields,     // 合并后的字段配置
        checked: mergedChecked,   // 合并后的选中字段
        showLineHeight: false,    // 强制重置行高设置
        trigger: 'manual' as const,  // 添加 as const 类型断言
      };
    } catch (e) {
      console.error('本地设置解析失败，使用默认配置', e);
      return defaultSettings;
    }
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

  const {
    run: fetchRiskList,
  } = useRequest(RiskManageService.fetchTodoRiskList, {
    defaultValue: {
      total: 0,
      results: [],
      page: 1,
      num_pages: 1,
    },
    onSuccess(data) {
      const { results } = data;
      if (results && results.length) {
        results.forEach((item) => {
          const tmpItem = pollingDataMap.value[item.risk_id];
          if (!tmpItem) return;
          tmpItem.status = item.status;
          tmpItem.current_operator = item.current_operator;
          tmpItem.risk_label = item.risk_label;
          tmpItem.last_operate_time = item.last_operate_time;
        });
        startPolling(results);
      }
    },
  });


  const {
    data: levelData,
    run: fetchRiskLevel,
  } = useRequest(StrategyManageService.fetchRiskLevel, {
    defaultValue: {},
  });

  // 记录轮训的数据
  const pollingDataMap = ref<Record<string, RiskManageModel>>({});
  const handleRequestSuccess = ({ results }: {results: Array<RiskManageModel>}) => {
    startPolling(results);
    if (!results.length) return;
    // 获取对应风险等级
    fetchRiskLevel({
      strategy_ids: results.map(item => item.strategy_id).join(','),
    });
  };
  // 开始轮训
  const startPolling = (results: Array<RiskManageModel>) => {
    clearTimeout(timeout);
    pollingDataMap.value = {};
    results.forEach((item) => {
      if (item.status !== 'closed') {
        pollingDataMap.value[item.risk_id] = item;
      }
    });
    if (!Object.keys(pollingDataMap.value).length) return;
    timeout = setTimeout(() => {
      const params = getSearchParams();
      fetchRiskList({
        ...params,
        risk_id: Object.values(pollingDataMap.value).map(item => item.risk_id)
          .join(','),
      });
    }, 60 * 1000);
  };

  const handleSettingChange = (setting: ISettings) => {
    localStorage.setItem('audit-attention-risk-list-setting', JSON.stringify(setting));
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
  const handleSearchChange = (value: Record<string, any>) => {
    searchModel.value = value;
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
      strategy_id: '',
      operator: '',
      status: '',
      event_content: '',
      risk_level: '',
      title: '',
      notice_users: '',
    };
    listRef.value.fetchData({
      ...params,
      ...searchModel.value,
    });
  };
  onUnmounted(() => {
    clearTimeout(timeout);
  });

  onBeforeRouteLeave((to, from, next) => {
    if (to.name === 'attentionManageDetail') {
      const params = getSearchParams();
      // 保存当前查询参数到目标路由的 query 中
      // eslint-disable-next-line no-param-reassign
      to.query = {
        ...to.query,
        ...params,
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
