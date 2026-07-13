/**
 * 工具广场 URL 传参
 * 格式：raw_name=value（扁平 key，与 input_variable.raw_name 同名）
 */

/** 全局路由保留参数，不参与工具 raw_name 匹配 */
export const GLOBAL_ROUTE_RESERVED_QUERY_KEYS = new Set([
  'drillKey',
  'drillConfig',
  'rowData',
  'scene_id',
  'scope_id',
  'scope_type',
  'tool_id',
  'tool_uid',
  'initial_tab',
]);

/**
 * 游戏详情顶栏展示用 query key。
 * 若工具 input_variable 中存在同名 raw_name，则作为业务参数解析。
 */
export const GAME_DETAIL_DISPLAY_ROUTE_KEYS = new Set([
  'game_id',
  'game_name',
  'plat_type',
  'plat_account',
  'coin_balance',
  'total_recharge',
  'total_issue',
]);

/** @deprecated 使用 GLOBAL_ROUTE_RESERVED_QUERY_KEYS */
export const RESERVED_TOOL_ROUTE_QUERY_KEYS = GLOBAL_ROUTE_RESERVED_QUERY_KEYS;

export const SMART_PAGE_ACCOUNT_TYPES = ['ctx', 'openid', 'form_wechat', 'form_qq'] as const;

export type SmartPageAccountType = typeof SMART_PAGE_ACCOUNT_TYPES[number];

export interface SmartPageUrlParamConfig {
  key: string;
  enabled?: boolean;
  url_key?: string;
  account_type?: string;
}

export interface FlatToolParamsOptions {
  /** 工具 input_variable.raw_name 列表，用于解析与展示路由 key 同名的业务参数 */
  inputRawNames?: string[];
}

export const getRouteQueryValue = (value: unknown): string => {
  if (Array.isArray(value)) {
    return value[0] ? String(value[0]) : '';
  }
  if (value === undefined || value === null) {
    return '';
  }
  return String(value);
};

const shouldSkipRouteQueryKey = (key: string, inputRawNameSet: Set<string> | null): boolean => {
  if (GLOBAL_ROUTE_RESERVED_QUERY_KEYS.has(key)) return true;
  if (GAME_DETAIL_DISPLAY_ROUTE_KEYS.has(key) && (!inputRawNameSet || !inputRawNameSet.has(key))) {
    return true;
  }
  return false;
};

/** 从 URL 解析扁平工具参数 */
export const getFlatToolParamsFromRoute = (
  routeQuery: Record<string, unknown>,
  options: FlatToolParamsOptions = {},
): Record<string, string> => {
  const inputRawNameSet = options.inputRawNames?.length
    ? new Set(options.inputRawNames)
    : null;
  const params: Record<string, string> = {};
  Object.entries(routeQuery).forEach(([key, value]) => {
    if (shouldSkipRouteQueryKey(key, inputRawNameSet)) return;
    params[key] = getRouteQueryValue(value);
  });
  return params;
};

export const getRouteScopeQuery = (routeQuery: Record<string, unknown>): Record<string, string> => {
  const scope: Record<string, string> = {};
  ['scene_id', 'scope_id', 'scope_type'].forEach((key) => {
    const value = getRouteQueryValue(routeQuery[key]);
    if (value) scope[key] = value;
  });
  return scope;
};

const parseUrlValueByFieldCategory = (
  urlValue: string,
  fieldCategory?: string,
): unknown => {
  if (fieldCategory === 'person_select') {
    return urlValue.split(',').map(item => item.trim())
      .filter(Boolean);
  }
  if (fieldCategory === 'time_range_select') {
    const parts = urlValue.split(',').map(item => item.trim())
      .filter(Boolean);
    return parts.length >= 2 ? parts.slice(0, 2) : parts;
  }
  return urlValue;
};

/** 将 URL 参数按 raw_name 填入 searchList，URL 值优先 */
export const applyUrlParamsToSearchList = <T extends {
  raw_name: string;
  value: unknown;
  field_category?: string;
}>(
    searchList: T[],
    urlParams: Record<string, string>,
  ): { list: T[]; hasApplied: boolean } => {
  if (!searchList?.length || !Object.keys(urlParams).length) {
    return { list: searchList, hasApplied: false };
  }

  let hasApplied = false;
  const list = searchList.map((item) => {
    const urlValue = urlParams[item.raw_name];
    if (urlValue === undefined) return item;
    hasApplied = true;
    return {
      ...item,
      value: parseUrlValueByFieldCategory(urlValue, item.field_category),
    };
  });
  return { list, hasApplied };
};

const serializeSearchItemValue = (item: {
  value: unknown;
  field_category?: string;
}): string => {
  const { value } = item;
  if (value === null || value === undefined || value === '') return '';
  if (Array.isArray(value)) {
    const list = value.filter(v => v !== null && v !== undefined && v !== '');
    return list.length ? list.join(',') : '';
  }
  return String(value);
};

type FlatToolSearchItem = {
  raw_name: string;
  value: unknown;
  field_category?: string;
};

/** 将 searchList 序列化为 raw_name=value */
export const buildFlatToolRouteQuery = (searchList: Array<FlatToolSearchItem>): Record<string, string> => {
  const query: Record<string, string> = {};
  searchList.forEach((item) => {
    const value = serializeSearchItemValue(item);
    if (value !== '') {
      query[item.raw_name] = value;
    }
  });
  return query;
};

export const getGameIdFromRoute = (routeQuery: Record<string, unknown>): string => (
  getRouteQueryValue(routeQuery.game_id) || getRouteQueryValue(routeQuery.gameid)
);

type GameDetailIntent = { gameid: string; initialTab: string };

/** 用户画像 URL 中的游戏详情跳转意图（openid + gameid） */
export const parseSmartPageGameDetailIntent = (routeQuery: Record<string, unknown>): GameDetailIntent | null => {
  const gameid = getGameIdFromRoute(routeQuery);
  if (!gameid) return null;
  return {
    gameid,
    initialTab: getRouteQueryValue(routeQuery.initial_tab) || 'overview',
  };
};

export const buildSmartPageRouteQuery = (
  accountType?: string,
  accountId?: string,
  gameId?: string,
): Record<string, string> => {
  const query: Record<string, string> = {};
  if (accountType && accountId) {
    query[accountType] = accountId;
  }
  if (gameId) {
    query.game_id = gameId;
    query.gameid = gameId;
  }
  return query;
};

export const buildToolExecutionRouteQuery = (
  toolType: string,
  options: {
    searchList?: Array<{ raw_name: string; value: unknown; field_category?: string }>;
    accountType?: string;
    accountId?: string;
    gameId?: string;
  } = {},
): Record<string, string> => {
  if (toolType === 'smart_page') {
    return buildSmartPageRouteQuery(options.accountType, options.accountId, options.gameId);
  }
  return buildFlatToolRouteQuery(options.searchList || []);
};

export const mergeToolRouteQuery = (
  routeQuery: Record<string, unknown>,
  toolType: string,
  options: {
    searchList?: Array<{ raw_name: string; value: unknown; field_category?: string }>;
    accountType?: string;
    accountId?: string;
    gameId?: string;
  } = {},
): Record<string, string> => {
  const gameId = options.gameId || getGameIdFromRoute(routeQuery);
  return {
    ...getRouteScopeQuery(routeQuery),
    ...buildToolExecutionRouteQuery(toolType, { ...options, gameId }),
  };
};

type SearchListField = {
  value: unknown;
  required?: boolean;
  field_category?: string;
  is_show?: boolean;
};

/** 单个查询字段是否已填写 */
export const isSearchFieldValueFilled = (field: SearchListField): boolean => {
  if (field.is_show === false) return true;
  const { value } = field;
  if (field.field_category === 'time_range_select') {
    return Array.isArray(value) && value.length > 0;
  }
  if (field.field_category === 'person_select') {
    if (Array.isArray(value)) return value.length > 0;
    return value !== '';
  }
  if (value === null || value === undefined || value === '') return false;
  if (Array.isArray(value)) return value.length > 0;
  return true;
};

/** 必填查询字段是否均已填写 */
export const areRequiredSearchFieldsFilled = (searchList: SearchListField[] = []): boolean => {
  if (!searchList.length) return false;
  const requiredFields = searchList.filter(item => item.required !== false && item.is_show !== false);
  if (!requiredFields.length) return true;
  return requiredFields.every(isSearchFieldValueFilled);
};

export const toolTypeHasQueryButton = (toolType?: string): boolean => (
  toolType === 'data_search' || toolType === 'api' || toolType === 'smart_page'
);

/**
 * 加载时是否自动执行查询：
 * - 无查询按钮（如 bk_vision）：进入页面自动查询
 * - 有查询按钮（data_search / api）：必填项均有值时自动查询（URL / 缓存 / 默认值）
 * - 下钻场景：自动查询
 */
export const shouldAutoExecuteToolOnLoad = (
  toolType?: string,
  options: {
    searchList?: SearchListField[];
    hasDrillParams?: boolean;
  } = {},
): boolean => {
  if (options.hasDrillParams) return true;
  if (!toolTypeHasQueryButton(toolType)) return true;
  return areRequiredSearchFieldsFilled(options.searchList);
};

const resolveSmartPageAccountType = (key: string, configuredType?: string): string | null => {
  if (configuredType && SMART_PAGE_ACCOUNT_TYPES.includes(configuredType as SmartPageAccountType)) {
    return configuredType;
  }
  if (SMART_PAGE_ACCOUNT_TYPES.includes(key as SmartPageAccountType)) {
    return key;
  }
  if (key === 'uin') {
    return 'form_wechat';
  }
  return null;
};

/** 解析用户画像 URL 传参 */
export const parseSmartPageUrlParams = (
  routeQuery: Record<string, unknown>,
  toolConfig?: Record<string, any>,
): { accountType: string; accountId: string } | null => {
  const urlParamConfig = toolConfig?.property?.url_params as SmartPageUrlParamConfig[] | undefined;

  if (Array.isArray(urlParamConfig) && urlParamConfig.length > 0) {
    for (const cfg of urlParamConfig) {
      if (cfg.enabled === false) continue;
      if (cfg.key === 'name') continue;
      const urlKey = cfg.url_key || cfg.key;
      const value = getRouteQueryValue(routeQuery[urlKey]);
      if (!value) continue;
      const accountType = resolveSmartPageAccountType(cfg.key, cfg.account_type);
      if (accountType) {
        return { accountType, accountId: value };
      }
    }
  }

  for (const type of SMART_PAGE_ACCOUNT_TYPES) {
    const value = getRouteQueryValue(routeQuery[type]);
    if (value) {
      return { accountType: type, accountId: value };
    }
  }

  const uin = getRouteQueryValue(routeQuery.uin);
  if (uin) {
    return { accountType: 'form_wechat', accountId: uin };
  }

  return null;
};

export const buildGameDetailUid = (gameData: { openid?: string; gameid?: string | number; name?: string }) => {
  const openid = gameData.openid || '';
  const gameId = gameData.gameid !== undefined && gameData.gameid !== null && gameData.gameid !== ''
    ? String(gameData.gameid)
    : '';
  if (gameId) {
    return `game_detail_${openid}_${gameId}`;
  }
  return `game_detail_${openid}_${gameData.name || ''}`;
};

/** 游戏详情 Tab 标题：优先展示中文名，补查中不展示 game_id */
export const buildGameDetailTabLabel = (
  gameData?: { ctx?: string; name?: string; gameid?: string | number },
  options: { resolving?: boolean } = {},
): string => {
  const ctx = gameData?.ctx?.trim() || '';
  const gameId = gameData?.gameid !== undefined && gameData?.gameid !== null && gameData?.gameid !== ''
    ? String(gameData.gameid)
    : '';
  const name = gameData?.name && gameData.name !== gameId ? gameData.name.trim() : '';

  if (name) return ctx ? `${ctx} - ${name}` : name;
  if (options.resolving) return ctx || '游戏详情';
  return ctx || '游戏详情';
};

/** 游戏详情顶栏数据（来自用户画像关联游戏列表） */
export interface GameDetailRouteData {
  name: string;
  openid: string;
  gameid: string;
  ctx: string;
  wechat: string;
  platType: string;
  platAccount: string;
  loginDays31: number;
  coinBalance: number;
  totalRecharge: number;
  totalGift: number;
  totalIssue: number;
}

type ParsedGameDetailRoute = {
  gameData: GameDetailRouteData;
  toolUid: string;
  initialTab: string;
};

const toRouteNumber = (value: unknown): number => {
  const num = Number(value);
  return Number.isFinite(num) ? num : 0;
};

/** 将游戏详情顶栏信息序列化为 URL query（不传 game_name，游戏标识用 game_id） */
export const buildGameDetailRouteQuery = (
  gameData: Partial<GameDetailRouteData>,
  options: { toolUid?: string; initialTab?: string } = {},
): Record<string, string> => {
  const query: Record<string, string> = {};
  if (gameData.gameid) query.game_id = String(gameData.gameid);
  if (gameData.openid) query.openid = gameData.openid;
  if (options.toolUid) query.tool_uid = options.toolUid;
  if (options.initialTab) query.initial_tab = options.initialTab;
  if (gameData.ctx) query.ctx = gameData.ctx;
  if (gameData.platType) query.plat_type = gameData.platType;
  if (gameData.platAccount) query.plat_account = gameData.platAccount;
  if (gameData.coinBalance !== undefined && gameData.coinBalance !== null) {
    query.coin_balance = String(gameData.coinBalance);
  }
  if (gameData.totalRecharge !== undefined && gameData.totalRecharge !== null) {
    query.total_recharge = String(gameData.totalRecharge);
  }
  if (gameData.totalIssue !== undefined && gameData.totalIssue !== null) {
    query.total_issue = String(gameData.totalIssue);
  }
  return query;
};

/** 从 URL 解析游戏详情顶栏信息（不读取 game_name） */
export const parseGameDetailFromRoute = (
  routeQuery: Record<string, unknown>,
  options: { fallbackToolUid?: string } = {},
): ParsedGameDetailRoute | null => {
  const openid = getRouteQueryValue(routeQuery.openid);
  const toolUid = getRouteQueryValue(routeQuery.tool_uid) || options.fallbackToolUid || '';
  const gameId = getGameIdFromRoute(routeQuery);
  if (!openid || !toolUid || !gameId) return null;

  return {
    gameData: {
      name: '',
      openid,
      gameid: gameId,
      ctx: getRouteQueryValue(routeQuery.ctx),
      wechat: '',
      platType: getRouteQueryValue(routeQuery.plat_type),
      platAccount: getRouteQueryValue(routeQuery.plat_account),
      loginDays31: 0,
      coinBalance: toRouteNumber(getRouteQueryValue(routeQuery.coin_balance)),
      totalRecharge: toRouteNumber(getRouteQueryValue(routeQuery.total_recharge)),
      totalGift: 0,
      totalIssue: toRouteNumber(getRouteQueryValue(routeQuery.total_issue)),
    },
    toolUid,
    initialTab: getRouteQueryValue(routeQuery.initial_tab) || 'overview',
  };
};

export const mergeGameDetailRouteQuery = (
  routeQuery: Record<string, unknown>,
  gameData: Partial<GameDetailRouteData>,
  options: { toolUid?: string; initialTab?: string } = {},
): Record<string, string> => ({
  ...getRouteScopeQuery(routeQuery),
  ...buildGameDetailRouteQuery(gameData, options),
});
