/*
 * TencentBlueKing is pleased to support the open source community by making
 * 蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
 * Copyright (C) 2023 THL A29 Limited,
 * a Tencent company. All rights reserved.
 * Licensed under the MIT License (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at http://opensource.org/licenses/MIT
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on
 * an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
 * either express or implied. See the License for the
 * specific language governing permissions and limitations under the License.
 * We undertake not to change the open source license (MIT license) applicable
 * to the current version of the project delivered to anyone in the future.
 */

import { type Ref, ref } from 'vue';

import ToolManageService from '@service/tool-manage';

import { ROLE_FIELDS } from './game-field-keys';

// ========== 通用工具函数 ==========

// 提取接口返回的 results 数组（兼容多种嵌套形式）
export const extractResults = (data: any): any[] => {
  const results = data?.data?.result?.results
    || data?.result?.results || data?.data?.results || data?.results;
  return Array.isArray(results) ? results : [];
};

// 日期格式化为 YYYYMMDD
export const formatYmd = (d: Date): string => {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}${m}${day}`;
};

// 日期格式化为 YYYY-MM-DD
export const formatYmdDashed = (d: Date): string => {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
};

// 计算各种相对日期参数（一周前/一月前/半年前/一年前/今天 等）
export const getDateParams = () => {
  const now = new Date();
  const oneMonthAgo = new Date(now);
  oneMonthAgo.setMonth(oneMonthAgo.getMonth() - 1);
  const oneWeekAgo = new Date(now);
  oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
  const twoWeekAgo = new Date(now);
  twoWeekAgo.setDate(twoWeekAgo.getDate() - 14);
  const sixMonthAgo = new Date(now);
  sixMonthAgo.setMonth(sixMonthAgo.getMonth() - 6);
  const oneYearAgo = new Date(now);
  oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);

  return {
    one_month_ago_Ymd: formatYmd(oneMonthAgo),
    one_month_ago_Ymd_dashed: formatYmdDashed(oneMonthAgo),
    one_week_ago_Ymd_dashed: formatYmdDashed(oneWeekAgo),
    two_week_ago_Ymd_dashed: formatYmdDashed(twoWeekAgo),
    six_month_ago_Ymd: formatYmd(sixMonthAgo),
    six_month_ago_Ymd_dashed: formatYmdDashed(sixMonthAgo),
    one_year_ago_Ymd: formatYmd(oneYearAgo),
    last_record_thedate_Ymd: formatYmd(oneMonthAgo),
    today_Ymd: formatYmd(now),
  };
};

// 合并三个角色统计接口的数据（按角色ID合并）
// 以登录接口（loginData）返回的角色ID为准：
// - 聊天/交易接口若返回的角色ID与登录接口不一致（即不在登录角色ID集合内），则忽略不展示
// - 登录数据中缺失的统计字段统一补 0（避免页面展示为 -- 不直观）
export const mergeRoleStats = (loginData: any[], chatData: any[], dealData: any[]) => {
  const roleMap = new Map<string, Record<string, any>>();
  // 1. 以登录数据初始化角色集合，并为所有数值统计字段提供默认值 0
  loginData.forEach((row) => {
    const id = row[ROLE_FIELDS.ROLE_ID] || row.roleId || '';
    roleMap.set(id, {
      ...row,
      [ROLE_FIELDS.LOGIN_LOCATION_MONTH]: row[ROLE_FIELDS.LOGIN_LOCATION_MONTH] ?? 0,
      [ROLE_FIELDS.LOGIN_LOCATION_YEAR]: row[ROLE_FIELDS.LOGIN_LOCATION_YEAR] ?? 0,
      [ROLE_FIELDS.LOGIN_COUNT_MONTH]: row[ROLE_FIELDS.LOGIN_COUNT_MONTH] ?? 0,
      [ROLE_FIELDS.LOGIN_COUNT_YEAR]: row[ROLE_FIELDS.LOGIN_COUNT_YEAR] ?? 0,
      [ROLE_FIELDS.TRADE_TARGET_MONTH]: 0,
      [ROLE_FIELDS.TRADE_TARGET_YEAR]: 0,
      [ROLE_FIELDS.TRADE_COUNT_MONTH]: 0,
      [ROLE_FIELDS.TRADE_COUNT_YEAR]: 0,
      [ROLE_FIELDS.CHAT_TARGET_MONTH]: 0,
      [ROLE_FIELDS.CHAT_TARGET_YEAR]: 0,
      [ROLE_FIELDS.CHAT_COUNT_MONTH]: 0,
      [ROLE_FIELDS.CHAT_COUNT_YEAR]: 0,
    });
  });
  // 2. 聊天数据：仅当角色ID存在于登录角色集合内才合并，否则忽略
  chatData.forEach((row) => {
    const id = row[ROLE_FIELDS.ROLE_ID] || row.roleId || '';
    const existing = roleMap.get(id);
    if (!existing) return;
    roleMap.set(id, {
      ...existing,
      [ROLE_FIELDS.CHAT_TARGET_MONTH]: row[ROLE_FIELDS.CHAT_TARGET_MONTH] ?? 0,
      [ROLE_FIELDS.CHAT_TARGET_YEAR]: row[ROLE_FIELDS.CHAT_TARGET_YEAR] ?? 0,
      [ROLE_FIELDS.CHAT_COUNT_MONTH]: row[ROLE_FIELDS.CHAT_COUNT_MONTH] ?? 0,
      [ROLE_FIELDS.CHAT_COUNT_YEAR]: row[ROLE_FIELDS.CHAT_COUNT_YEAR] ?? 0,
    });
  });
  // 3. 交易数据：仅当角色ID存在于登录角色集合内才合并，否则忽略
  dealData.forEach((row) => {
    const id = row[ROLE_FIELDS.ROLE_ID] || row.roleId || '';
    const existing = roleMap.get(id);
    if (!existing) return;
    roleMap.set(id, {
      ...existing,
      [ROLE_FIELDS.TRADE_TARGET_MONTH]: row[ROLE_FIELDS.TRADE_TARGET_MONTH] ?? 0,
      [ROLE_FIELDS.TRADE_TARGET_YEAR]: row[ROLE_FIELDS.TRADE_TARGET_YEAR] ?? 0,
      [ROLE_FIELDS.TRADE_COUNT_MONTH]: row[ROLE_FIELDS.TRADE_COUNT_MONTH] ?? 0,
      [ROLE_FIELDS.TRADE_COUNT_YEAR]: row[ROLE_FIELDS.TRADE_COUNT_YEAR] ?? 0,
    });
  });
  return Array.from(roleMap.values());
};

// ========== 接口请求基础 ==========

interface GameContextLike {
  toolUid: string;
  gameid: string | number;
  openid: string;
}

// 创建数据源调用器（绑定当前游戏上下文）
export const createDataSourceExecutor = (getCtx: () => GameContextLike) => (
  dataSourceName: string,
  params: Record<string, any>,
) => {
  const ctx = getCtx();
  if (!ctx.toolUid) return Promise.resolve(null);
  return ToolManageService.fetchToolsExecute({
    uid: ctx.toolUid,
    params: {
      data_source_name: dataSourceName,
      params,
    },
  });
};

// ========== 概览数据加载 composable ==========

export interface OverviewState {
  roleList: Ref<Array<Record<string, any>>>;
  loginStatList: Ref<Array<Record<string, any>>>;
  lastLoginRecord: Ref<Record<string, any>>;
  lastGiveRecord: Ref<Record<string, any>>;
  lastDealRecord: Ref<Record<string, any>>;
  lastSapRecord: Ref<Record<string, any>>;
  lastChatRecord: Ref<Record<string, any>>;
  sectionLoadingMap: Ref<Record<string, boolean>>;
}

export const useGameOverviewFetcher = (
  executeDataSource: ReturnType<typeof createDataSourceExecutor>,
  getCtx: () => GameContextLike,
) => {
  const state: OverviewState = {
    roleList: ref<Array<Record<string, any>>>([]),
    loginStatList: ref<Array<Record<string, any>>>([]),
    lastLoginRecord: ref<Record<string, any>>({}),
    lastGiveRecord: ref<Record<string, any>>({}),
    lastDealRecord: ref<Record<string, any>>({}),
    lastSapRecord: ref<Record<string, any>>({}),
    lastChatRecord: ref<Record<string, any>>({}),
    sectionLoadingMap: ref<Record<string, boolean>>({
      role: false, login: false, gift: false, trade: false, coin: false, chat: false,
    }),
  };

  // 角色总览（合并3个接口）
  // 注：与明细 tab 默认"最近半年"保持一致，避免概览查不到数据但明细有数据的不一致情况
  // 后端字段名 one_month_ago_Ymd_dashed 不变，仅将值改为半年前日期
  const fetchOverviewRoleStats = async () => {
    const dp = getDateParams();
    const ctx = getCtx();
    const baseParams = {
      one_month_ago_Ymd_dashed: dp.six_month_ago_Ymd_dashed,
      one_year_ago_Ymd: dp.one_year_ago_Ymd,
      selected_gameid: ctx.gameid,
      selected_openid: ctx.openid,
    };
    const [loginRes, chatRes, dealRes] = await Promise.all([
      executeDataSource('overview_rolelogin_stats', baseParams),
      executeDataSource('overview_rolechat_stats', baseParams),
      executeDataSource('overview_roledeal_stats', baseParams),
    ]);
    state.roleList.value = mergeRoleStats(
      extractResults(loginRes),
      extractResults(chatRes),
      extractResults(dealRes),
    );
  };

  // 登录统计（展示最近7天、最近14天、最近1个月三行数据）
  const fetchOverviewLoginStats = async () => {
    const dp = getDateParams();
    const ctx = getCtx();
    const res = await executeDataSource('overview_login_stats', {
      one_month_ago_Ymd: dp.one_month_ago_Ymd,
      one_week_ago_Ymd_dashed: dp.one_week_ago_Ymd_dashed,
      two_week_ago_Ymd_dashed: dp.two_week_ago_Ymd_dashed,
      selected_gameid: ctx.gameid,
      selected_openid: ctx.openid,
    });
    // 后端返回带有 line(1/2/3) 字段，按 line 升序排列确保展示顺序为：最近7天、最近14天、最近1个月
    const results = extractResults(res);
    state.loginStatList.value = results.sort((a: any, b: any) => (Number(a.line) || 0) - (Number(b.line) || 0));
  };

  // 最近记录（5个接口并行）
  // 注：与明细 tab 默认"最近半年"保持一致，避免概览查不到数据但明细有数据的不一致情况
  // 后端字段名 last_record_thedate_Ymd 不变，仅将值改为半年前日期
  const fetchOverviewLastRecords = async () => {
    const dp = getDateParams();
    const ctx = getCtx();
    const baseParams = {
      last_record_thedate_Ymd: dp.six_month_ago_Ymd,
      selected_gameid: ctx.gameid,
      selected_openid: ctx.openid,
    };
    const [loginRes, giveRes, dealRes, sapRes, chatRes] = await Promise.all([
      executeDataSource('overview_login_last', baseParams),
      executeDataSource('overview_give_last', baseParams),
      executeDataSource('overview_deal_last', baseParams),
      executeDataSource('overview_sap_last', baseParams),
      executeDataSource('overview_chat_last', baseParams),
    ]);
    state.lastLoginRecord.value = extractResults(loginRes)[0] || {};
    state.lastGiveRecord.value = extractResults(giveRes)[0] || {};
    state.lastDealRecord.value = extractResults(dealRes)[0] || {};
    state.lastSapRecord.value = extractResults(sapRes)[0] || {};
    state.lastChatRecord.value = extractResults(chatRes)[0] || {};
  };

  // 加载所有概览数据（每个数据源独立 loading，互不阻塞）
  const fetchOverviewData = () => {
    const ctx = getCtx();
    if (!ctx.toolUid || !ctx.openid) return;

    state.sectionLoadingMap.value.role = true;
    fetchOverviewRoleStats().finally(() => {
      state.sectionLoadingMap.value.role = false;
    });

    state.sectionLoadingMap.value.login = true;
    fetchOverviewLoginStats().finally(() => {
      state.sectionLoadingMap.value.login = false;
    });

    state.sectionLoadingMap.value.gift = true;
    state.sectionLoadingMap.value.trade = true;
    state.sectionLoadingMap.value.coin = true;
    state.sectionLoadingMap.value.chat = true;
    fetchOverviewLastRecords().finally(() => {
      state.sectionLoadingMap.value.gift = false;
      state.sectionLoadingMap.value.trade = false;
      state.sectionLoadingMap.value.coin = false;
      state.sectionLoadingMap.value.chat = false;
    });
  };

  return { ...state, fetchOverviewData };
};

// ========== 明细 Tab 数据加载 composable ==========

export interface DetailState {
  loginGroupStats: Ref<Array<Record<string, any>>>;
  loginDetailList: Ref<Array<Record<string, any>>>;
  loginPagination: Ref<{ count: number; current: number; limit: number }>;

  giveGroupStats: Ref<Array<Record<string, any>>>;
  giveDetailList: Ref<Array<Record<string, any>>>;
  giftPagination: Ref<{ count: number; current: number; limit: number }>;

  dealGroupStats: Ref<Array<Record<string, any>>>;
  dealDetailList: Ref<Array<Record<string, any>>>;
  tradePagination: Ref<{ count: number; current: number; limit: number }>;

  sapGroupStats: Ref<Array<Record<string, any>>>;
  sapDetailList: Ref<Array<Record<string, any>>>;
  coinPagination: Ref<{ count: number; current: number; limit: number }>;

  chatDetailList: Ref<Array<Record<string, any>>>;
  chatPagination: Ref<{ count: number; current: number; limit: number }>;

  detailDateRange: Ref<Record<string, { start: string; end: string }>>;
  tabChartLoadingMap: Ref<Record<string, boolean>>;
  tabTableLoadingMap: Ref<Record<string, boolean>>;
  tabDataLoaded: Ref<Record<string, boolean>>;
}

const createPagination = () => ref({ count: 0, current: 1, limit: 10 });

export const useGameDetailFetcher = (
  executeDataSource: ReturnType<typeof createDataSourceExecutor>,
  getCtx: () => GameContextLike,
  chatSuspectedViolation: Ref<boolean>,
) => {
  // 初始化日期范围（默认最近半年）
  const initDateRange = () => {
    const dp = getDateParams();
    const defaultRange = { start: dp.six_month_ago_Ymd, end: dp.today_Ymd };
    return {
      login: { ...defaultRange },
      gift: { ...defaultRange },
      trade: { ...defaultRange },
      coin: { ...defaultRange },
      chat: { ...defaultRange },
    };
  };

  const state: DetailState = {
    loginGroupStats: ref([]),
    loginDetailList: ref([]),
    loginPagination: createPagination(),

    giveGroupStats: ref([]),
    giveDetailList: ref([]),
    giftPagination: createPagination(),

    dealGroupStats: ref([]),
    dealDetailList: ref([]),
    tradePagination: createPagination(),

    sapGroupStats: ref([]),
    sapDetailList: ref([]),
    coinPagination: createPagination(),

    chatDetailList: ref([]),
    chatPagination: createPagination(),

    detailDateRange: ref(initDateRange()),
    tabChartLoadingMap: ref({
      login: false, gift: false, trade: false, coin: false, chat: false,
    }),
    tabTableLoadingMap: ref({
      login: false, gift: false, trade: false, coin: false, chat: false,
    }),
    tabDataLoaded: ref({}),
  };

  // 通用：构建 detail 接口的基础参数（开始/结束日期 + 上下文）
  const buildRangeParams = (tabKey: string) => {
    const range = state.detailDateRange.value[tabKey];
    const ctx = getCtx();
    return {
      detail_startdate_Ymd: range.start,
      detail_enddate_Ymd: range.end,
      selected_gameid: ctx.gameid,
      selected_openid: ctx.openid,
    };
  };

  // 通用：执行图表接口 + 表格接口（独立 loading）
  // 返回 Promise 以便调用方在完成后做后续处理
  const loadChartAndTable = (
    tabKey: 'login' | 'gift' | 'trade' | 'coin',
    chartDataSource: string,
    chartParams: Record<string, any>,
    tableDataSource: string,
    tableParams: Record<string, any>,
    chartTarget: Ref<Array<Record<string, any>>>,
    tableTarget: Ref<Array<Record<string, any>>>,
    pagination: Ref<{ count: number; current: number; limit: number }>,
  ) => {
    state.tabChartLoadingMap.value[tabKey] = true;
    executeDataSource(chartDataSource, chartParams).then((groupRes) => {
      // eslint-disable-next-line no-param-reassign
      chartTarget.value = extractResults(groupRes);
    })
      .finally(() => {
        state.tabChartLoadingMap.value[tabKey] = false;
      });

    state.tabTableLoadingMap.value[tabKey] = true;
    executeDataSource(tableDataSource, tableParams).then((detailRes) => {
      // eslint-disable-next-line no-param-reassign
      tableTarget.value = extractResults(detailRes);
      // eslint-disable-next-line no-param-reassign
      pagination.value.count = tableTarget.value.length;
    })
      .finally(() => {
        state.tabTableLoadingMap.value[tabKey] = false;
      });
  };

  // 登录记录
  const fetchLoginData = () => {
    const baseParams = buildRangeParams('login');
    loadChartAndTable(
      'login',
      'login_groupdim_stats', baseParams,
      'login_detail_list', baseParams,
      state.loginGroupStats, state.loginDetailList, state.loginPagination,
    );
  };

  // 赠送记录（图表和表格都使用 detail 日期范围）
  const fetchGiveData = () => {
    const chartParams = buildRangeParams('gift');
    loadChartAndTable(
      'gift',
      'give_groupdim_stats', chartParams,
      'give_detail_list', chartParams,
      state.giveGroupStats, state.giveDetailList, state.giftPagination,
    );
  };

  // 交易记录
  const fetchDealData = () => {
    const baseParams = buildRangeParams('trade');
    loadChartAndTable(
      'trade',
      'deal_groupdim_stats', baseParams,
      'deal_detail_list', baseParams,
      state.dealGroupStats, state.dealDetailList, state.tradePagination,
    );
  };

  // 发放记录
  const fetchSapData = () => {
    const baseParams = buildRangeParams('coin');
    loadChartAndTable(
      'coin',
      'sap_groupdim_stats', baseParams,
      'sap_detail_list', baseParams,
      state.sapGroupStats, state.sapDetailList, state.coinPagination,
    );
  };

  // 聊天记录（无图表，只有表格）
  const fetchChatData = async () => {
    state.tabTableLoadingMap.value.chat = true;
    try {
      const range = state.detailDateRange.value.chat;
      const ctx = getCtx();
      const res = await executeDataSource('chat_detail_list', {
        detail_startdate_Ymd: range.start,
        detail_enddate_Ymd: range.end,
        is_sensitive: chatSuspectedViolation.value ? ['1'] : ['0', '1'],
        selected_gameid: ctx.gameid,
        selected_openid: ctx.openid,
      });
      state.chatDetailList.value = extractResults(res);
      state.chatPagination.value.count = state.chatDetailList.value.length;
    } finally {
      state.tabTableLoadingMap.value.chat = false;
    }
  };

  // 分页映射表
  const paginationMap: Record<string, Ref<{ count: number; current: number; limit: number }>> = {
    login: state.loginPagination,
    gift: state.giftPagination,
    trade: state.tradePagination,
    coin: state.coinPagination,
    chat: state.chatPagination,
  };

  // Tab 切换时按需加载数据
  const loadTabData = (tabKey: string) => {
    if (state.tabDataLoaded.value[tabKey]) return;
    state.tabDataLoaded.value[tabKey] = true;
    switch (tabKey) {
      case 'login': fetchLoginData(); break;
      case 'gift': fetchGiveData(); break;
      case 'trade': fetchDealData(); break;
      case 'coin': fetchSapData(); break;
      case 'chat': fetchChatData(); break;
      default: break;
    }
  };

  const handleTabPageChange = (tabKey: string, page: number) => {
    paginationMap[tabKey].value.current = page;
  };

  const handleTabPageLimitChange = (tabKey: string, limit: number) => {
    paginationMap[tabKey].value.limit = limit;
    paginationMap[tabKey].value.current = 1;
  };

  // 日期范围变化时重新加载对应 tab 数据
  const handleTabDateChange = (tabKey: string, range: [string, string]) => {
    if (range[0] && range[1]) {
      const start = range[0].replace(/-/g, '');
      const end = range[1].replace(/-/g, '');
      state.detailDateRange.value[tabKey] = { start, end };
      state.tabDataLoaded.value[tabKey] = false;
      loadTabData(tabKey);
    }
  };

  return {
    ...state,
    fetchChatData,
    loadTabData,
    handleTabPageChange,
    handleTabPageLimitChange,
    handleTabDateChange,
  };
};
