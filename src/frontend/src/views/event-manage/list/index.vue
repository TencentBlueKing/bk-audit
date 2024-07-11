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
  <skeleton-loading
    fullscreen
    :loading="isLoading"
    name="eventList">
    <div class="event-manage-list">
      <div class="action-header">
        <bk-search-select
          v-model="searchKey"
          clearable
          :data="searchData"
          :defaut-using-item="{inputHtml: t('请选择')}"
          :get-menu-list="getMenuList"
          style="width: 660px;"
          @update:model-value="handleSearch" />
        <bk-date-picker
          append-to-body
          :clearable="false"
          :disable-date="disableDate"
          :model-value="searchDate.datetime"
          :placeholder="t('请选择时间')"
          shortcut-close
          :shortcuts="shortcuts"
          style="width: 320px;margin-left: auto;"
          type="datetimerange"
          @change="handleChangeDate" />
      </div>
      <render-list
        ref="listRef"
        :columns="tableColumn"
        :data-source="dataSource"
        is-need-hide-clear-search-tip
        @request-success="handleRequestSuccess" />
    </div>
  </skeleton-loading>
  <audit-sideslider
    ref="sidesliderRef"
    v-model:isShow="showDetail"
    :show-footer="false"
    show-header-slot
    :title="t('风险详情')"
    :width="960">
    <template #header>
      <div class="flex mr24">
        <div>
          {{ t('风险详情') }}
          <bk-button
            v-bk-tooltips="t('复制链接')"
            text
            theme="primary"
            @click="handleCopyLink">
            <audit-icon
              style="font-size: 14px;"
              type="link" />
          </bk-button>
        </div>
      </div>
    </template>
    <div>
      <div style="height: 6px;background: #ea3636;" />
      <alarm-detail
        :alarm-data="alarmData" />
    </div>
  </audit-sideslider>
</template>
<script setup lang="tsx">
  import dayjs from 'dayjs';
  import {
    onMounted,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import EventManageService from '@service/event-manage';
  import MetaManageService from '@service/meta-manage';
  import StrategyManageService from '@service/strategy-manage';

  import RiskModel from '@model/event/risk';

  import useRequest from '@hooks/use-request';
  import useUrlSearch from '@hooks/use-url-search';

  import {
    execCopy,
  } from '@utils/assist';

  import AlarmDetail from './components/alarm-detail/index.vue';

  interface TShortcut {
    text: string,
    value: () => [Date, Date]
  }

  interface SearchKey{
    id: string,
    name: string,
    values: [
      {
        id: string,
        name: string
      }
    ]
  }
  interface Event {
    page: number;
    num_pages: number;
    total: number;
    results: Array<RiskModel>;
  }
  interface SearchType {
    name: string,
    id: string,
    placeholder: string,
    children?: Array<{
      name: string,
      id: string,
    }>
  }
  const {
    getSearchParams,
    replaceSearchParams,
  } = useUrlSearch();
  const { t } = useI18n();
  const isLoading = ref(false);
  const listRef = ref();
  const showDetail = ref(false);
  const searchKey = ref<Array<SearchKey>>([]);
  const dataSource = EventManageService.fetchRiskList;
  const searchDate = ref<Record<string, any>>({
    datetime: [
      dayjs(Date.now() - (86400000 * 3)).format('YYYY-MM-DD HH:mm:ss'),
      dayjs().format('YYYY-MM-DD HH:mm:ss'),
    ],
  });
  const disableDate = (date: number | Date): boolean => date.valueOf() > Date.now();
  const alarmData = ref(new RiskModel());
  const shortcuts: Array<TShortcut> = [
    {
      text: t('近 3 天'),
      value() {
        const end = new Date();
        const start = new Date();
        start.setTime(start.getTime() - 259200000);
        return [
          start, end,
        ];
      },
    },
    {
      text: t('近 7 天'),
      value() {
        const end = new Date();
        const start = new Date();
        start.setTime(start.getTime() - 604800000);
        return [
          start, end,
        ];
      },
    },
    {
      text: t('近 30 天'),
      value() {
        const end = new Date();
        const start = new Date();
        start.setTime(start.getTime() - 2592000000);
        return [
          start, end,
        ];
      },
    },
  ];
  const tableColumn = [
    {
      label: () => t('风险ID'),
      width: 260,
      render: ({ data }: { data: RiskModel }) => <bk-button
          class="ml8"
          theme="primary"
          text
          onClick={ () => handleAlertDetail(data) }>
          {data.risk_id}
        </bk-button>,
    },
    {
      label: () => t('风险描述'),
      showOverflowTooltip: true,
      render: ({ data }: { data: RiskModel }) => (data.event_content || '--'),
    },
    {
      label: () => t('风险类型'),
      showOverflowTooltip: true,
      render: ({ data }: { data: RiskModel }) => (data.event_type.length ? data.event_type.join(',') : '--'),
    },
    {
      label: () => t('策略名称(策略ID)'),
      showOverflowTooltip: true,
      render: ({ data }: { data: RiskModel }) => {
        const to = {
          name: 'strategyList',
          query: {
            strategy_id: data.strategy_id,
          },
        };
        const label = strategyList.value.find(item => item.value === data.strategy_id)?.label;
        return <router-link to={to} target='_blank'>
          {`${label}(${data.strategy_id})` || '--'}
        </router-link>;
      },
    },
    {
      label: () => t('风险产生时间'),
      width: '170px',
      render: ({ data }: { data: RiskModel }) => {
        if (data.event_time) {
          return dayjs(data.event_time).format('YYYY-MM-DD HH:mm:ss');
        }
        return '--';
      },
    },
    {
      label: () => t('风险来源'),
      showOverflowTooltip: true,
      render: ({ data }: { data: RiskModel }) => (data.event_source || '--'),
    },
    {
      label: () => t('责任人'),
      showOverflowTooltip: true,
      render: ({ data }: { data: RiskModel }) => (data.operator.join(',') || '--'),
    },
  ];

  let searchData = [
    {
      name: t('责任人'),
      id: 'operator',
      placeholder: t('请输入责任人'),
    },
    {
      name: t('风险ID'),
      id: 'risk_id',
      placeholder: t('请输入风险ID'),
    },
    {
      name: t('风险类型'),
      id: 'event_type',
      placeholder: t('请输入风险类型'),
    },
    {
      name: t('策略名称(策略ID)'),
      id: 'strategy_id',
      placeholder: t('请输入策略名称(策略ID)'),
    },
  ] as SearchType[];

  const isNeedShowDetail = ref(false);

  // 策略列表
  const {
    data: strategyList,
  } = useRequest(StrategyManageService.fetchAllStrategyList, {
    defaultValue: [],
    manual: true,
    onSuccess(data) {
      searchData = [
        {
          name: t('责任人'),
          id: 'operator',
          placeholder: t('请输入责任人'),
        },
        {
          name: t('风险ID'),
          id: 'risk_id',
          placeholder: t('请输入风险ID'),
        },
        {
          name: t('风险类型'),
          id: 'event_type',
          placeholder: t('请输入风险类型'),
        },
        {
          name: t('策略名称(策略ID)'),
          id: 'strategy_id',
          placeholder: t('请输入策略名称(策略ID)'),
          children: data.map(item => ({
            id: item.value.toString(),
            name: `${item.label}(${item.value})`,
          })),
        },
      ];
    },
  });

  // 人员列表
  const {
    run: fetchUserList,
  } = useRequest(MetaManageService.fetchUserList, {
    defaultParams: {
      page: 1,
      page_size: 30,
      fuzzy_lookups: '',
    },
    defaultValue: {
      count: 0,
      results: [],
    },
  });

  const getMenuList = async (item: any, keyword: string) => {
    if (!item) {
      return searchData;
    }
    const searchItem = searchData.find(searchItem => searchItem.id === item.id);
    if (searchItem && item.id === 'operator') {
      if (keyword) {
        const userList = await fetchUserList({
          fuzzy_lookups: keyword,
        });
        searchItem.children = userList.results.map(item => ({
          id: item.username,
          name: `${item.username}(${item.display_name})`,
        }));
      } else searchItem.children = [];
    }
    return searchData.find(searchItem => searchItem.id === item.id)?.children as [];
  };
  // 复制链接
  const handleCopyLink = () => {
    replaceSearchParams({
      risk_id: alarmData.value.risk_id,
      start_time: searchDate.value.datetime[0],
      end_time: searchDate.value.datetime[1],
    });
    const route = window.location.href;
    execCopy(route, t('复制成功'));
  };
  const handleSearch = (keyword: Array<any>) => {
    const search = {
      operator: '',
      strategy_id: '',
      risk_id: '',
      event_type: '',
      start_time: searchDate.value.datetime[0],
      end_time: searchDate.value.datetime[1],
    } as Record<string, string>;
    keyword.forEach((item: SearchKey) => {
      search[item.id] = item.values.map(item => item.id).join(',');
    });
    listRef.value.fetchData(search);
  };

  const handleChangeDate = (date: Array<string>) => {
    listRef.value.fetchData({
      start_time: date[0],
      end_time: date[1],
    });
    searchDate.value.datetime = date;
  };

  const handleAlertDetail = (data: RiskModel) => {
    alarmData.value = data;
    showDetail.value = true;
  };

  const handleRequestSuccess = (data: Event) => {
    const { risk_id: Id } = getSearchParams();
    if (Id && isNeedShowDetail.value) {
      handleAlertDetail(data.results[0]);
      isNeedShowDetail.value = false;
    }
  };
  onMounted(() => {
    let params:Record<string, any> = {
      start_time: searchDate.value.datetime[0],
      end_time: searchDate.value.datetime[1],
    };
    const { risk_id: Id, start_time: startTime, end_time: endTime } = getSearchParams();
    if (Id) {
      isNeedShowDetail.value = true;
      params = {
        risk_id: Id,
        start_time: startTime,
        end_time: endTime,
      };
      searchDate.value.datetime = [startTime, endTime];
      searchKey.value.push({ id: 'risk_id', name: t('风险ID'), values: [{ id: Id, name: Id }] });
      handleSearch(searchKey.value);
    } else {
      listRef.value.fetchData({
        ...params,
      });
    }
  });
</script>
<style lang="postcss">

.show-tooltips-text {
  width: 100%;
  max-width: 100%;
}

.event-manage-list {
  padding: 24px;
  background-color: white;

  .action-header {
    display: flex;
    margin-bottom: 16px;

    .search-dater {
      width: 480px;
      margin-left: auto;
    }
  }

  .label-box {
    display: inline-block;
    height: 23px;
    padding: 0 10px;
    margin-right: 4px;
    line-height: 22px;
    text-align: center;
    background-color: #f0f1f5;
    border-radius: 2px;
  }

  .recovered {
    color: #14a568;
    background: #e4faf0;
  }

  .unknown {
    color: #fe9c00;
    background: #fff1db;
  }

  .abnormal {
    color: #ea3536;
    background: #feebea;
  }

  .close {
    color: #979ba5;
    background: #f5f7fa;
  }
}
</style>
