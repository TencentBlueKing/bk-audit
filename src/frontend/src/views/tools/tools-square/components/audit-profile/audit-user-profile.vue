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
  <div class="audit-user-profile">
    <!-- 查询输入 -->
    <profile-query-input
      ref="queryInputRef"
      :loading="isQuerying"
      @query="handleQuery"
      @reset="handleReset" />
    <template
      v-if="hasQueried && !isQuerying && !userInfoLoading && !gameListLoading
        && isUserInfoEmpty && (hideGameList || gameList.length === 0)">
      <bk-exception
        class="profile-all-empty"
        scene="part"
        type="empty">
        {{ t('暂无数据') }}
      </bk-exception>
    </template>

    <template v-else-if="hasQueried || isQuerying || gameListLoading || userInfoLoading">
      <bk-loading
        v-if="isQuerying || userInfoLoading || gameListLoading || !isUserInfoEmpty"
        class="user-info-loading-wrapper"
        :loading="isQuerying || userInfoLoading || gameListLoading">
        <div
          v-if="isQuerying || userInfoLoading || gameListLoading"
          class="user-info-loading-placeholder" />
        <profile-user-info
          v-else
          :history-accounts="historyAccounts"
          :user-info="userInfo"
          @view-detail="handleViewDetail" />
      </bk-loading>

      <div
        v-if="!hideGameList && !(!isQuerying && !userInfoLoading && isUserInfoEmpty)"
        class="section-divider" />

      <!-- 关联游戏列表 - 独立 loading（openid 单条结果场景隐藏整个游戏列表区块） -->
      <bk-loading
        v-if="!hideGameList"
        class="game-list-loading-wrapper"
        :loading="isQuerying || userInfoLoading || gameListLoading">
        <div
          v-if="isQuerying || userInfoLoading || gameListLoading"
          class="game-list-loading-placeholder" />
        <template v-else>
          <!-- 游戏列表为空 -->
          <bk-exception
            v-if="gameList.length === 0"
            class="game-list-empty"
            scene="part"
            type="empty">
            {{ t('暂无关联游戏数据') }}
          </bk-exception>
          <!-- 关联游戏列表 -->
          <div
            v-else
            class="top-search game-list-section">
            <div class="game-list-header">
              <div class="top-search-title">
                {{ t('关联游戏列表') }}
              </div>
              <div class="game-list-actions">
                <bk-search-select
                  v-model="gameSearchKey"
                  class="game-search-input"
                  clearable
                  :condition="[]"
                  :data="gameSearchSelectData"
                  :defaut-using-item="{ inputHtml: t('请选择') }"
                  :placeholder="t('搜索 游戏名称、账号、openid')"
                  unique-select
                  @update:model-value="handleGameSearch" />
                <bk-popover
                  ref="exportPopoverRef"
                  ext-cls="export-popover-wrapper"
                  :is-show="isExportPopoverShow"
                  placement="bottom-start"
                  theme="light"
                  trigger="click"
                  :width="340"
                  @after-hidden="isExportPopoverShow = false">
                  <bk-button
                    @click="isExportPopoverShow = !isExportPopoverShow">
                    <audit-icon
                      style="margin-right: 4px;"
                      type="download" />
                    {{ t('导出') }}
                  </bk-button>
                  <template #content>
                    <div class="export-popover-content">
                      <div class="export-popover-body">
                        <div class="export-popover-title">
                          {{ t('导出关联游戏列表') }}
                        </div>
                        <div class="export-form-item">
                          <div class="export-form-label">
                            {{ t('导出内容') }}
                            <span class="required-star">*</span>
                          </div>
                          <bk-checkbox-group v-model="exportContentChecked">
                            <div class="export-checkbox-grid">
                              <bk-checkbox
                                v-for="item in exportContentOptions"
                                :key="item.id"
                                :label="item.id">
                                {{ item.name }}
                              </bk-checkbox>
                            </div>
                          </bk-checkbox-group>
                        </div>
                      </div>
                      <div class="export-popover-footer">
                        <bk-button
                          :loading="isExporting"
                          theme="primary"
                          @click="handleExportGameList">
                          {{ t('导出') }}
                        </bk-button>
                        <bk-button @click="isExportPopoverShow = false">
                          {{ t('取消') }}
                        </bk-button>
                      </div>
                    </div>
                  </template>
                </bk-popover>
              </div>
            </div>
            <primary-table
              class="game-list-table"
              :columns="gameColumns"
              :data="paginatedGameList"
              hover
              :row-key="getGameRowKey as any"
              :sort="tableSort"
              @sort-change="handleSortChange" />
            <div
              v-if="filteredGameList.length > 0"
              class="game-list-pagination">
              <bk-pagination
                v-model="pagination.current"
                align="left"
                :count="filteredGameList.length"
                :layout="['total', 'limit', 'list']"
                :limit="pagination.limit"
                :limit-list="paginationLimitList"
                location="left"
                @change="handlePageChange"
                @limit-change="handlePageLimitChange" />
            </div>
          </div>
        </template>
      </bk-loading>
    </template>
  </div>
</template>

<script setup lang="ts">
  import { computed, h, nextTick, onMounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';
  import * as XLSX from 'xlsx';

  import ToolManageService from '@service/tool-manage';

  import { PrimaryTable } from '@blueking/tdesign-ui';

  import { execCopy } from '@utils/assist';

  import { PROFILE_FIELDS } from '../game/game-field-keys';

  import ProfileQueryInput from './profile-query-input.vue';
  import ProfileUserInfo from './profile-user-info.vue';

  import useRequest from '@/hooks/use-request';

  import '@blueking/tdesign-ui/vue3/index.css';

  import qqSvg from '@/images/qq.svg';
  import wechatSvg from '@/images/wechat.svg';

  interface Props {
    toolUid?: string;       // 工具 uid，用于调用执行接口
    toolConfig?: {          // 工具配置，包含 property.scene_id 用于跳转风险时携带场景
      property?: {
        scene_id?: number | string;
      };
      [key: string]: any;
    };
  }

  interface Emits {
    (e: 'openGameDetail', gameData: Record<string, any>, initialTab?: string): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    toolUid: '',
    toolConfig: () => ({}),
  });
  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const router = useRouter();

  const queryInputRef = ref();
  const hasQueried = ref(false);
  // 查询进行中标志：从点击查询起立即为 true，待 useRequest 的 loading 真正接管后自动置 false，
  // 避免请求发起前出现"用户信息块不渲染、loading 也未起来"的空白时间窗
  const isQuerying = ref(false);
  const showAccount = ref(false); // 账号列显隐控制，默认隐藏

  interface GameSearchKey {
    id: string;
    name: string;
    values?: Array<{ id: string; name: string }>;
  }

  const GAME_SEARCH_FIELD_IDS = ['gameName', 'platformAccount', 'openid'] as const;

  const gameSearchSelectData = [
    {
      name: t('游戏名称'),
      id: 'gameName',
      placeholder: t('请输入'),
    },
    {
      name: t('账号'),
      id: 'platformAccount',
      placeholder: t('请输入'),
    },
    {
      name: 'openid',
      id: 'openid',
      placeholder: t('请输入'),
    },
  ];

  const gameSearchKey = ref<GameSearchKey[]>([]);

  // ========== 状态持久化（sessionStorage）==========
  // key 按 toolUid 区分：
  // 1. 多个画像工具实例间互不干扰
  // 2. 关闭工具 tab 时，外层可按 toolUid 精准清除该工具的查询状态
  // 3. 刷新页面 / 同 tab 内路由切换返回时，该 key 仍然存在，可恢复查询
  const STORAGE_KEY_PROFILE_QUERY_PREFIX = 'tool_audit_profile_query_';
  const getStorageKey = () => `${STORAGE_KEY_PROFILE_QUERY_PREFIX}${props.toolUid || ''}`;

  // 保存查询状态到 sessionStorage
  const saveQueryState = (accountType: string, accountId: string) => {
    if (!props.toolUid) return;
    try {
      sessionStorage.setItem(getStorageKey(), JSON.stringify({
        accountType,
        accountId,
        toolUid: props.toolUid,
      }));
    } catch {
      // 静默处理
    }
  };

  // 清除保存的查询状态
  const clearQueryState = () => {
    if (!props.toolUid) return;
    try {
      sessionStorage.removeItem(getStorageKey());
    } catch {
      // 静默处理
    }
  };

  // 从 sessionStorage 恢复查询状态
  const loadQueryState = (): { accountType: string; accountId: string; toolUid: string } | null => {
    if (!props.toolUid) return null;
    try {
      const raw = sessionStorage.getItem(getStorageKey());
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  };

  const getResults = (data: any) => data?.data?.result?.results;

  // 获取近一年起始日期，格式 YYYYMMDD
  const getOneYearAgoYmd = (): string => {
    const d = new Date();
    d.setFullYear(d.getFullYear() - 1);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}${m}${day}`;
  };

  // 获取前一天日期，格式 YYYYMMDD
  const getOneDayAgoYmd = (): string => {
    const d = new Date();
    d.setDate(d.getDate() - 1);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}${m}${day}`;
  };

  const userInfo = ref({
    avatar: '',
    wecom: '',
    username: '',
    wechat: '',
    qq: '',
    status: '',
    department: '',
    responsibilityCount: 0,
    riskLevel: '',
  });

  // 历史账号列表
  const historyAccounts = ref<Array<{ type: string; account: string }>>([]);

  // 关联游戏列表（接口返回后填充）
  const gameList = ref<Array<Record<string, any>>>([]);
  // 是否隐藏"关联游戏列表"区块（openid 搜索仅 1 条结果时，已自动跳转到游戏详情，工具页不再展示游戏列表，但仍展示用户信息）
  const hideGameList = ref(false);

  // 缓存 openid_list_first_ctx（微信/QQ/openid 搜索时，从 main_openid_list 首条结果获取的 ctx）
  const openidListFirstCtx = ref('');

  // 缓存最近一次查询参数，用于翻页
  const lastQueryParams = ref<Record<string, any> | null>(null);
  // 缓存最近一次查询的账号类型
  const lastAccountType = ref('');

  // 排序状态：默认不排序
  const sortState = ref<{ column: string; type: string }>({
    column: PROFILE_FIELDS.COIN_BALANCE_UNIT,
    type: 'desc',
  });

  const matchGameRowByField = (
    row: Record<string, any>,
    fieldId: typeof GAME_SEARCH_FIELD_IDS[number],
    keyword: string,
  ) => {
    const kw = keyword.toLowerCase();
    if (fieldId === 'gameName') {
      const value = String(row[PROFILE_FIELDS.GAME_NAME] || row.name || '').toLowerCase();
      return value.includes(kw);
    }
    if (fieldId === 'platformAccount') {
      const value = String(row[PROFILE_FIELDS.PLATFORM_ACCOUNT] || row.platformAccount || '').toLowerCase();
      return value.includes(kw);
    }
    const value = String(row.openid || '').toLowerCase();
    return value.includes(kw);
  };

  const isGameSearchFieldId = (fieldId: string): fieldId is typeof GAME_SEARCH_FIELD_IDS[number] => (
    GAME_SEARCH_FIELD_IDS.includes(fieldId as typeof GAME_SEARCH_FIELD_IDS[number])
  );

  // 搜索过滤：按 bk-search-select 选中的列精确匹配，避免账号/openid 同值时歧义
  const filteredGameList = computed(() => {
    const list = gameList.value;
    if (!gameSearchKey.value.length) {
      return list;
    }

    return list.filter(row => gameSearchKey.value.every((cond) => {
      const hasValues = !!cond.values?.length;
      const keyword = hasValues
        ? cond.values!.map(v => v.id).join(',')
        : cond.id;
      if (!keyword?.trim()) {
        return true;
      }
      const kw = keyword.trim();

      if (hasValues && isGameSearchFieldId(cond.id)) {
        return matchGameRowByField(row, cond.id, kw);
      }

      // 未选择列时的自由输入：匹配游戏名称、账号、openid 任意一列
      return GAME_SEARCH_FIELD_IDS.some(fieldId => matchGameRowByField(row, fieldId, kw));
    }));
  });

  const handleGameSearch = (keyword: GameSearchKey[]) => {
    keyword.forEach((item, index) => {
      if (item.values?.length || !item.id || isGameSearchFieldId(item.id)) {
        return;
      }
      gameSearchKey.value[index] = {
        id: 'gameName',
        name: t('游戏名称'),
        values: [{ id: item.id, name: item.id }],
      };
    });
    pagination.value.current = 1;
  };

  // 排序后的列表
  const sortedGameList = computed(() => {
    const list = [...filteredGameList.value];
    const { column, type } = sortState.value;
    if (!column || !type || type === 'null') return list;
    list.sort((a, b) => {
      const valA = Number(a[column]) || 0;
      const valB = Number(b[column]) || 0;
      return type === 'asc' ? valA - valB : valB - valA;
    });
    return list;
  });

  // 前端分页：根据当前页码和每页条数截取数据
  const paginatedGameList = computed(() => {
    const start = (pagination.value.current - 1) * pagination.value.limit;
    const end = start + pagination.value.limit;
    return sortedGameList.value.slice(start, end);
  });

  const tableSort = computed(() => {
    const { column, type } = sortState.value;
    if (!column || !type || type === 'null') {
      return undefined;
    }
    return {
      sortBy: column,
      descending: type === 'desc',
    };
  });

  const paginationLimitList = [10, 20, 50, 100];

  const getGameRowKey = (row: Record<string, any>) => (
    `${row.openid || ''}__${row[PROFILE_FIELDS.GAME_NAME] || row.name || ''}`
  );

  watch(gameSearchKey, () => {
    pagination.value.current = 1;
  }, { deep: true });

  // 用户信息是否为空
  const isUserInfoEmpty = computed(() => !userInfo.value.wecom
    && !userInfo.value.username);

  // ========== 接口调用：用户信息 (main_user_info) ==========
  const {
    loading: userInfoLoading,
    run: fetchUserInfo,
  } = useRequest(ToolManageService.fetchToolsExecute, {
    defaultValue: {},
    onSuccess: (data) => {
      const results = getResults(data);
      if (results && (Array.isArray(results) ? results.length > 0 : true)) {
        const userData = Array.isArray(results) ? results[0] : results;
        // 将接口返回的字段映射到 userInfo（按设计稿只取6个展示字段）
        userInfo.value = {
          ...userInfo.value,
          avatar: userData.avatar || userData[PROFILE_FIELDS.AVATAR] || '',
          wecom: userData[PROFILE_FIELDS.WECOM] || userData.wecom || userData.wx_work_id || '',
          username: userData[PROFILE_FIELDS.USERNAME] || userData.username || userData.display_name || '',
          status: userData[PROFILE_FIELDS.STATUS] || userData.status || '',
          department: userData[PROFILE_FIELDS.DEPARTMENT] || userData.department || '',
        };

        // 企业微信搜索成功后，获取到 username(企业微信)，
        // 用它作为 user_info_output_var_ctx 触发查询 main_qqwechat_list 和 main_auditrisk_stat
        const ctx = userInfo.value.wecom || userData[PROFILE_FIELDS.WECOM] || '';
        if (ctx) {
          // 触发查询责任单数及风险系数
          fetchAuditRiskStat(ctx);
          // 触发查询微信QQ列表
          fetchQQWechatList(ctx);
        }
      }
    },
  });

  // ========== 接口调用：责任单数及风险系数 (main_auditrisk_stat) ==========
  const {
    run: runFetchAuditRiskStat,
  } = useRequest(ToolManageService.fetchToolsExecute, {
    defaultValue: {},
    onSuccess: (data) => {
      const results = getResults(data);
      if (results) {
        const statData = Array.isArray(results) ? results[0] : results;
        if (statData) {
          userInfo.value.responsibilityCount = statData.count_tickets
            ?? statData[PROFILE_FIELDS.RESPONSIBILITY_COUNT] ?? statData.responsibility_count ?? 0;
          // max_risk_level_num: 3=高, 2=中, 1=低, null/0=低
          const riskNum = statData.max_risk_level_num
            ?? statData[PROFILE_FIELDS.RISK_LEVEL] ?? statData.risk_level;
          const riskMap: Record<number, string> = { 3: '高', 2: '中', 1: '低', 0: '低' };
          // 当 riskNum 为 null/undefined 时，默认展示"低"
          userInfo.value.riskLevel = (riskNum === null || riskNum === undefined)
            ? '低'
            : (riskMap[Number(riskNum)] ?? String(riskNum));
        }
      }
    },
  });

  // 封装：查询责任单数及风险系数
  const fetchAuditRiskStat = (username: string) => {
    if (!props.toolUid) return;
    runFetchAuditRiskStat({
      uid: props.toolUid,
      params: {
        data_source_name: 'main_auditrisk_stat',
        params: {
          one_year_ago_Ymd: getOneYearAgoYmd(),
          username,
        },
      },
    });
  };

  // ========== 接口调用：查询微信QQ (main_qqwechat_list) ==========
  const {
    run: runFetchQQWechatList,
  } = useRequest(ToolManageService.fetchToolsExecute, {
    defaultValue: {},
    onSuccess: (data) => {
      const results = getResults(data);
      if (results) {
        const qqwechatData = Array.isArray(results) ? results : [results];
        // 从结果中提取微信和QQ账号（当前账号）
        const wechatAccounts: string[] = [];
        const qqAccounts: string[] = [];
        // 从结果中提取历史账号
        const historyList: Array<{ type: string; account: string }> = [];
        qqwechatData.forEach((item: any) => {
          const accountType = item[PROFILE_FIELDS.ACCOUNT_TYPE] || item.account_type || '';
          const accountList = item[PROFILE_FIELDS.ACCOUNT_LIST] || item.account_list || '';
          // 判断是当前还是历史账号（后端通过 account_type 区分）
          const isHistory = item.is_history || accountType === 'history' || accountType === '历史';
          if (isHistory) {
            // 历史账号
            if (accountList) {
              historyList.push({ type: accountType, account: accountList });
            }
          } else {
            // 当前账号
            if (accountType === '微信' || accountType === 'wechat') {
              wechatAccounts.push(accountList);
            } else if (accountType === 'QQ' || accountType === 'qq') {
              qqAccounts.push(accountList);
            }
          }
        });
        // 遍历所有记录，提取每条记录的"历史账号列表"字段
        qqwechatData.forEach((item: any) => {
          const itemAccountType = item[PROFILE_FIELDS.ACCOUNT_TYPE] || item.account_type || '';
          let historyField = item[PROFILE_FIELDS.ACCOUNT_HISTORY_LIST];
          // 兼容多种格式：数组、JSON 字符串、分号分隔字符串
          if (typeof historyField === 'string' && historyField) {
            try {
              const parsed = JSON.parse(historyField);
              if (Array.isArray(parsed)) {
                historyField = parsed;
              } else {
                // 不是数组，当作分号分隔字符串处理
                historyField = historyField.split(';').map((v: string) => v.trim())
                  .filter(Boolean);
              }
            } catch {
              // JSON 解析失败，当作分号分隔字符串处理
              historyField = historyField.split(';').map((v: string) => v.trim())
                .filter(Boolean);
            }
          }
          if (Array.isArray(historyField)) {
            historyField.forEach((hItem: any) => {
              if (typeof hItem === 'string' && hItem) {
                historyList.push({ type: itemAccountType, account: hItem });
              } else if (hItem && typeof hItem === 'object') {
                const hType = hItem[PROFILE_FIELDS.ACCOUNT_TYPE] || hItem.account_type || itemAccountType;
                const hAccount = hItem[PROFILE_FIELDS.ACCOUNT_LIST] || hItem.account_list || '';
                if (hAccount) {
                  historyList.push({ type: hType, account: hAccount });
                }
              }
            });
          }
        });
        // 也检查顶层 history_list 字段（兼容旧数据结构）
        const topLevelHistoryField = data?.data?.result?.history_list
          || data?.history_list;
        if (Array.isArray(topLevelHistoryField)) {
          topLevelHistoryField.forEach((item: any) => {
            const accountType = item[PROFILE_FIELDS.ACCOUNT_TYPE] || item.account_type || '';
            const accountList = item[PROFILE_FIELDS.ACCOUNT_LIST] || item.account_list || '';
            if (accountList) {
              historyList.push({ type: accountType, account: accountList });
            }
          });
        }
        if (wechatAccounts.length > 0) {
          userInfo.value.wechat = wechatAccounts.join(';');
        }
        if (qqAccounts.length > 0) {
          userInfo.value.qq = qqAccounts.join(';');
        }
        historyAccounts.value = historyList;
      }
    },
  });

  // 封装：查询微信QQ列表
  const fetchQQWechatList = (username: string) => {
    if (!props.toolUid) return;
    runFetchQQWechatList({
      uid: props.toolUid,
      params: {
        data_source_name: 'main_qqwechat_list',
        params: {
          one_day_ago_Ymd: getOneDayAgoYmd(),
          username,
        },
      },
    });
  };

  // ========== 接口调用：关联游戏列表 (main_openid_list) ==========
  const {
    loading: gameListLoading,
    run: fetchGameList,
  } = useRequest(ToolManageService.fetchToolsExecute, {
    defaultValue: {},
    onSuccess: (data) => {
      const results = getResults(data);
      if (Array.isArray(results)) {
        gameList.value = results;
        pagination.value.count = data?.data?.result?.total
          || data?.result?.total || data?.data?.total || results.length;

        // 从首条结果中提取 ctx 作为 openid_list_first_ctx
        if (results.length > 0) {
          const firstRow = results[0];
          openidListFirstCtx.value = firstRow.ctx || firstRow[PROFILE_FIELDS.PLATFORM_ACCOUNT] || firstRow[PROFILE_FIELDS.WECOM] || '';
        }

        // 微信/QQ/openid 搜索时，游戏列表返回后需要级联查询用户信息
        if (['form_wechat', 'form_qq', 'openid'].includes(lastAccountType.value)) {
          // 正常展示游戏列表区块
          hideGameList.value = false;

          // openid 搜索时，结果返回后展示工具页内容
          if (lastAccountType.value === 'openid') {
            hasQueried.value = true;
          }

          // 有结果时，用 openid_list_first_ctx 查询用户信息
          if (openidListFirstCtx.value) {
            executeUserInfoByCtx(openidListFirstCtx.value);
          }
        }
      }
    },
  });

  // 当 useRequest 的 loading 真正接管后，自动关闭 isQuerying
  // 这样可以避免请求发起前的空白时间窗
  watch(
    () => [userInfoLoading.value, gameListLoading.value],
    ([uLoading, gLoading]) => {
      if (isQuerying.value && (uLoading || gLoading)) {
        isQuerying.value = false;
      }
    },
  );

  // 映射游戏数据字段
  const mapGameData = (row: Record<string, any>) => ({
    name: row[PROFILE_FIELDS.GAME_NAME] || row.name || '',
    openid: row.openid || '',
    gameid: row.gameid || '',
    ctx: userInfo.value.wecom || '',
    wechat: userInfo.value.wechat || '',
    coinBalance: row[PROFILE_FIELDS.COIN_BALANCE_UNIT] || row.coinBalance || 0,
    totalRecharge: row[PROFILE_FIELDS.TOTAL_RECHARGE_UNIT] || row.totalRecharge || 0,
    totalGift: row[PROFILE_FIELDS.TOTAL_GIFT_YUAN] || row.totalGift || 0,
    totalIssue: row[PROFILE_FIELDS.TOTAL_ISSUE_YUAN] || row.totalIssue || 0,
    totalBalance: row[PROFILE_FIELDS.TOTAL_BALANCE] || row.totalBalance || 0,
    totalTopup: row[PROFILE_FIELDS.TOTAL_TOPUP] || row.totalTopup || 0,
    source: row.source || '',
    platformAccount: row[PROFILE_FIELDS.PLATFORM_ACCOUNT] || row.platformAccount || '',
    exchangeRate: row[PROFILE_FIELDS.EXCHANGE_RATE] || row.exchangeRate || '',
    // 账号宽表新增字段
    platformAccountType: row[PROFILE_FIELDS.PLATFORM_ACCOUNT_TYPE] || row.platformAccountType || '',
    totalRechargeYuan: row[PROFILE_FIELDS.TOTAL_RECHARGE_YUAN] || row.totalRechargeYuan || 0,
    accountNature: row[PROFILE_FIELDS.ACCOUNT_NATURE] || row.accountNature || '',
    // 平台账号类型和平台账号（用于游戏详情顶栏动态展示微信/QQ）
    platType: row[PROFILE_FIELDS.PLATFORM_ACCOUNT_TYPE] || row.platformAccountType || '',
    platAccount: row[PROFILE_FIELDS.PLATFORM_ACCOUNT] || row.platformAccount || '',
    // 登录天数（31天）（用于传递给游戏详情）
    loginDays31: row[PROFILE_FIELDS.LOGIN_DAYS_31] || row.loginDays31 || 0,
  });

  // 封装：通过 ctx（企业微信）查询用户信息（用于微信/QQ/openid搜索的级联查询）
  const executeUserInfoByCtx = (ctx: string) => {
    if (!props.toolUid) return;
    fetchUserInfo({
      uid: props.toolUid,
      params: {
        data_source_name: 'main_user_info',
        params: {
          username: ctx,
        },
      },
    });
  };

  // 执行数据源查询
  const executeDataSource = (dataSourceName: string, params: Record<string, any>, runner: typeof fetchUserInfo) => {
    if (!props.toolUid) return;
    runner({
      uid: props.toolUid,
      params: {
        data_source_name: dataSourceName,
        params,
      },
    });
  };

  // 复制 openid
  const handleCopyOpenid = (openid: string) => {
    execCopy(openid, t('复制成功'));
  };

  // 点击游戏名称 - 打开新工具tab，自动展示概览tab
  const handleClickGame = (gameData: Record<string, any>) => {
    emit('openGameDetail', mapGameData(gameData), 'overview');
  };

  // 点击查看记录 - 打开新工具tab，自动展示登录记录tab
  const handleViewRecord = (gameData: Record<string, any>) => {
    emit('openGameDetail', mapGameData(gameData), 'login');
  };

  const toolSceneId = computed(() => {
    const id = props.toolConfig?.property?.scene_id;
    return (id !== undefined && id !== null && id !== '') ? String(id) : '';
  });

  const buildSceneRiskQuery = (extra: Record<string, string> = {}): Record<string, string> => {
    const query: Record<string, string> = { ...extra };
    if (toolSceneId.value) {
      query.scene_id = toolSceneId.value;
      query.scope_id = toolSceneId.value;
      query.scope_type = 'scene';
    }
    return query;
  };

  // TODO: 点击责任单数跳转 - 待后端接口支持后取消注释
  // const handleJumpToSceneRisk = (openid: string) => {
  //   const routeData = router.resolve({
  //     name: 'sceneRiskManageList',
  //     query: buildSceneRiskQuery({ openid }),
  //   });
  //   window.open(routeData.href, '_blank');
  // };

  // 表格列配置（按设计稿：游戏名称 | openid | 代币存量(元) | 累计充值(元)
  // | 累计发放(¥) | 累计赠送次数(隐藏) | 累计交易次数(隐藏) | 登录次数/月(隐藏) | 责任单数(隐藏) | 操作）
  // 代币字段已替换为元，null时醒目提示"未设汇率"
  const renderCoinField = (data: Record<string, any>, field: string) => {
    const val = data[field];
    if (val === null || val === undefined || val === '') {
      return h(
        'span',
        { style: 'color: #ea3636; cursor: default;' },
        t('未设汇率'),
      );
    }
    return h('span', {}, val);
  };

  const gameColumns: Array<Record<string, any>> = [
    {
      title: () => t('游戏名称'),
      colKey: 'name',
      width: 220,
      ellipsis: true,
      cell: (_h: any, { row }: { row: Record<string, any> }) => h(
        'span',
        {
          style: 'color: #3a84ff; cursor: pointer;',
          onClick: () => handleClickGame(row),
        },
        row[PROFILE_FIELDS.GAME_NAME] || row.name || '--',
      ),
    },
    {
      title: () => h('span', { style: 'display: inline-flex; align-items: center; gap: 6px;' }, [
        t('账号'),
        h('i', {
          class: `audit-icon audit-icon-${showAccount.value ? 'view' : 'unview'}`,
          style: 'cursor: pointer; font-size: 14px;',
          onClick: (e: Event) => {
            e.stopPropagation();
            showAccount.value = !showAccount.value;
          },
        }),
      ]),
      colKey: 'platformAccount',
      minWidth: 180,
      ellipsis: true,
      cell: (_h: any, { row }: { row: Record<string, any> }) => {
        const account = row.platformAccount || row[PROFILE_FIELDS.PLATFORM_ACCOUNT] || '';
        const platType = row.platType || row[PROFILE_FIELDS.PLATFORM_ACCOUNT_TYPE] || '';
        if (!account) return h('span', {}, '--');
        const iconSrc = platType === 'qq' ? qqSvg : wechatSvg;
        const maskAccount = (value: string) => {
          if (value.length <= 2) {
            return value;
          }
          return `${value[0]}${'*'.repeat(value.length - 2)}${value[value.length - 1]}`;
        };
        const displayAccount = showAccount.value ? account : maskAccount(account);
        return h(
          'span',
          { style: 'display: inline-flex; align-items: center; gap: 4px;' },
          [
            h('img', {
              src: iconSrc,
              style: 'width: 16px; height: 16px;',
              alt: platType === 'qq' ? 'QQ' : 'WeChat',
            }),
            h('span', {}, displayAccount),
          ],
        );
      },
    },
    {
      title: () => 'openid',
      colKey: 'openid',
      minWidth: 320,
      ellipsis: true,
      cell: (_h: any, { row }: { row: Record<string, any> }) => {
        if (row.openid === null || row.openid === undefined || row.openid === '') {
          return h('span', {}, '--');
        }
        return h(
          'span',
          {
            class: 'openid-cell',
            style: 'display: inline-flex; align-items: center; gap: 4px;',
          },
          [
            h('span', {}, row.openid),
            h('i', {
              class: 'audit-icon audit-icon-copy hover-show-icon openid-copy-icon',
              onClick: (e: Event) => {
                e.stopPropagation();
                handleCopyOpenid(row.openid);
              },
            }),
          ],
        );
      },
    },
    {
      title: () => `${t('代币存量')} (¥)`,
      colKey: PROFILE_FIELDS.COIN_BALANCE_UNIT,
      sorter: true,
      cell: (_h: any, { row }: { row: Record<string, any> }) => renderCoinField(row, PROFILE_FIELDS.COIN_BALANCE_UNIT),
    },
    {
      title: () => `${t('累计充值')} (¥)`,
      colKey: PROFILE_FIELDS.TOTAL_RECHARGE_UNIT,
      sorter: true,
      cell: (_h: any, { row }: { row: Record<string, any> }) => (
        renderCoinField(row, PROFILE_FIELDS.TOTAL_RECHARGE_UNIT)
      ),
    },
    {
      title: () => `${t('累计发放')} (¥)`,
      colKey: PROFILE_FIELDS.TOTAL_ISSUE_YUAN,
      sorter: true,
      cell: (_h: any, { row }: { row: Record<string, any> }) => h('span', {}, row[PROFILE_FIELDS.TOTAL_ISSUE_YUAN] ?? '--'),
    },
    {
      title: () => t('登录天数（31天）'),
      colKey: PROFILE_FIELDS.LOGIN_DAYS_31,
      sorter: true,
      cell: (_h: any, { row }: { row: Record<string, any> }) => h('span', {}, row[PROFILE_FIELDS.LOGIN_DAYS_31] ?? '--'),
    },
    {
      title: () => t('操作'),
      colKey: 'action',
      width: 100,
      cell: (_h: any, { row }: { row: Record<string, any> }) => h(
        'span',
        {
          style: 'color: #3a84ff; cursor: pointer;',
          onClick: () => handleViewRecord(row),
        },
        t('查看记录'),
      ),
    },
  ];

  // 分页
  const pagination = ref({
    count: 0,
    current: 1,
    limit: 10,
  });

  const handlePageChange = (page: number) => {
    pagination.value.current = page;
  };

  const handlePageLimitChange = (limit: number) => {
    pagination.value.limit = limit;
    pagination.value.current = 1;
  };

  const handleSortChange = (sort: any) => {
    let sortInfo: { sortBy?: string; descending?: boolean } | undefined;
    if (Array.isArray(sort)) {
      [sortInfo] = sort;
    } else if (sort?.sortBy !== undefined) {
      sortInfo = sort;
    }
    if (!sortInfo?.sortBy) {
      sortState.value = { column: '', type: 'null' };
    } else {
      sortState.value = {
        column: sortInfo.sortBy,
        type: sortInfo.descending ? 'desc' : 'asc',
      };
    }
    pagination.value.current = 1;
  };

  // ========== 查询入口：根据账号类型分发不同的查询链路 ==========
  const handleQuery = (accountType: string, accountId: string) => {
    // openid 类型查询时，先不设置 hasQueried，等结果返回后再决定
    hasQueried.value = accountType !== 'openid';
    // 立即进入"查询中"状态，确保 loading 占位立刻显示（涵盖 openid 类型 hasQueried=false 的场景）
    isQuerying.value = true;
    lastAccountType.value = accountType;
    // 保存查询状态到 sessionStorage
    saveQueryState(accountType, accountId);

    // 重置中间变量
    openidListFirstCtx.value = '';
    gameList.value = [];
    // 重置游戏列表隐藏标识（仅 openid 单条结果时会再次置 true）
    hideGameList.value = false;
    // 重置排序状态为默认：按代币存量降序
    sortState.value = { column: PROFILE_FIELDS.COIN_BALANCE_UNIT, type: 'desc' };
    pagination.value.current = 1;
    userInfo.value = {
      avatar: '', wecom: '', username: '', wechat: '', qq: '',
      status: '', department: '',
      responsibilityCount: 0, riskLevel: '',
    };

    if (accountType === 'ctx') {
      // ===== 选择企业微信 =====
      // 1. 查询"用户信息" main_user_info（输入 username=填写的选项）
      //    成功后 onSuccess 中自动触发查询 main_auditrisk_stat 和 main_qqwechat_list
      executeDataSource('main_user_info', {
        username: accountId,
      }, fetchUserInfo);

      // 2. 查询"游戏列表" main_openid_list（输入 form_ctx=填写的选项）
      lastQueryParams.value = { form_ctx: accountId };
      executeDataSource('main_openid_list', {
        one_day_ago_Ymd: getOneDayAgoYmd(),
        form_ctx: accountId,
      }, fetchGameList);
    } else if (accountType === 'form_wechat' || accountType === 'form_qq') {
      // ===== 选择微信或QQ =====
      // 1. 查询"游戏列表" main_openid_list（输入 form_wechat=iuin 或 form_qq=iuin）
      //    成功后 onSuccess 中自动：
      //    a. 设置 openid_list_first_ctx
      //    b. 触发查询"用户信息" main_user_info（输入 username=openid_list_first_ctx）
      //       用户信息成功后又自动触发 main_auditrisk_stat 和 main_qqwechat_list
      lastQueryParams.value = { [accountType]: accountId };
      executeDataSource('main_openid_list', {
        one_day_ago_Ymd: getOneDayAgoYmd(),
        [accountType]: accountId,
      }, fetchGameList);
    } else if (accountType === 'openid') {
      // ===== 选择openid =====
      // 1. 查询"游戏列表" main_openid_list（输入 form_openid=openid）
      //    成功后 onSuccess 中自动：
      //    a. 展示游戏列表区块
      //    b. 触发查询用户信息
      hasQueried.value = false;
      lastQueryParams.value = { form_openid: accountId };
      executeDataSource('main_openid_list', {
        one_day_ago_Ymd: getOneDayAgoYmd(),
        form_openid: accountId,
      }, fetchGameList);
    }
  };

  // 重置
  const handleReset = () => {
    hasQueried.value = false;
    isQuerying.value = false;
    lastQueryParams.value = null;
    lastAccountType.value = '';
    openidListFirstCtx.value = '';
    hideGameList.value = false;
    // 清除保存的查询状态
    clearQueryState();
    // 重置用户信息
    userInfo.value = {
      avatar: '', wecom: '', username: '', wechat: '', qq: '',
      status: '', department: '',
      responsibilityCount: 0, riskLevel: '',
    };
    // 重置历史账号
    historyAccounts.value = [];
    // 重置游戏列表
    gameList.value = [];
    gameSearchKey.value = [];
    sortState.value = { column: PROFILE_FIELDS.COIN_BALANCE_UNIT, type: 'desc' };
    pagination.value.count = 0;
    pagination.value.current = 1;
  };

  // 查看详情 - 新开标签页跳转至场景风险，带入企微名称作为责任人(operator)筛选
  const handleViewDetail = () => {
    const { wecom } = userInfo.value;
    const routeData = router.resolve({
      name: 'sceneRiskManageList',
      query: buildSceneRiskQuery(wecom ? { operator: wecom } : {}),
    });
    window.open(routeData.href, '_blank');
  };

  // ========== 导出功能 ==========
  const exportPopoverRef = ref();
  const isExportPopoverShow = ref(false);
  const isExporting = ref(false);

  // 导出内容选项（对应表格列）
  const exportContentOptions = [
    { id: 'gameName', name: t('游戏名称'), field: PROFILE_FIELDS.GAME_NAME, fallbackField: 'name' },
    {
      id: 'platformAccount',
      name: t('账号'),
      field: PROFILE_FIELDS.PLATFORM_ACCOUNT,
      fallbackField: 'platformAccount',
    },
    { id: 'openid', name: 'openid', field: 'openid', fallbackField: '' },
    { id: 'coinBalance', name: `${t('代币存量')}(¥)`, field: PROFILE_FIELDS.COIN_BALANCE_UNIT, fallbackField: 'coinBalance' },
    { id: 'totalRecharge', name: `${t('累计充值')}(¥)`, field: PROFILE_FIELDS.TOTAL_RECHARGE_UNIT, fallbackField: 'totalRecharge' },
    { id: 'totalIssue', name: `${t('累计发放')}(¥)`, field: PROFILE_FIELDS.TOTAL_ISSUE_YUAN, fallbackField: 'totalIssue' },
    { id: 'loginDays', name: t('登录天数（31天）'), field: PROFILE_FIELDS.LOGIN_DAYS_31, fallbackField: '' },
    // TODO: 后端暂未返回以下字段，待接口支持后取消注释
    // { id: 'totalGiftCount', name: t('累计赠送次数'),
    //   field: PROFILE_FIELDS.TOTAL_GIFT_COUNT, fallbackField: '' },
    // { id: 'totalTradeCount', name: t('累计交易次数'),
    //   field: PROFILE_FIELDS.TOTAL_TRADE_COUNT, fallbackField: '' },
    // { id: 'loginCount', name: `${t('登录次数')}/${t('月')}`,
    //   field: PROFILE_FIELDS.LOGIN_COUNT_MONTH, fallbackField: 'loginCount' },
    // { id: 'responsibilityCount', name: t('责任单数'),
    //   field: PROFILE_FIELDS.RESPONSIBILITY_COUNT,
    //   fallbackField: 'responsibility_count' },
  ];
  // 默认全选
  const exportContentChecked = ref<string[]>(exportContentOptions.map(item => item.id));

  // 设置列宽自适应 & 表头自动筛选
  const applyExcelStyles = (wb: XLSX.WorkBook) => {
    wb.SheetNames.forEach((sheetName: string) => {
      const ws = wb.Sheets[sheetName];
      if (!ws || !ws['!ref']) return;
      const range = XLSX.utils.decode_range(ws['!ref']);
      // 自动列宽
      const colWidths: Array<{ wch: number }> = [];
      for (let { c } = range.s; c <= range.e.c; c++) {
        let maxLen = 10;
        for (let { r } = range.s; r <= range.e.r; r++) {
          const cell = ws[XLSX.utils.encode_cell({ r, c })];
          if (cell && cell.v !== null && cell.v !== undefined) {
            const len = String(cell.v).length;
            // 中文字符按2倍宽度计算
            const cnLen = (String(cell.v).match(/[\u4e00-\u9fa5]/g) || []).length;
            const totalLen = len + cnLen;
            if (totalLen > maxLen) maxLen = totalLen;
          }
        }
        colWidths.push({ wch: Math.min(maxLen + 2, 200) });
      }
      ws['!cols'] = colWidths;
      // 表头自动筛选
      ws['!autofilter'] = { ref: ws['!ref'] };
    });
  };

  // 导出关联游戏列表（导出表格列数据）
  const handleExportGameList = () => {
    if (exportContentChecked.value.length === 0) return;
    if (filteredGameList.value.length === 0) return;

    isExporting.value = true;
    try {
      // 根据用户选中的列筛选导出内容
      const selectedColumns = exportContentOptions.filter(col => exportContentChecked.value.includes(col.id));

      // 构建导出数据
      const exportData = filteredGameList.value.map((game) => {
        const row: Record<string, any> = {};
        selectedColumns.forEach((col) => {
          row[col.name] = game[col.field] ?? (col.fallbackField ? game[col.fallbackField] : '') ?? '';
        });
        return row;
      });

      const wb = XLSX.utils.book_new();
      const headers = selectedColumns.map(col => col.name);
      const ws = XLSX.utils.json_to_sheet(exportData, { header: headers });
      XLSX.utils.book_append_sheet(wb, ws, t('关联游戏列表'));

      // 设置列宽自适应 & 表头自动筛选
      applyExcelStyles(wb);

      const now = new Date();
      const dateStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
      const timeStr = `${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}${String(now.getSeconds()).padStart(2, '0')}`;
      const userName = userInfo.value.wecom || '';
      const sheetName = t('关联游戏列表');
      const fileName = userName ? `${userName}_${sheetName}_${dateStr}_${timeStr}` : `${sheetName}_${dateStr}_${timeStr}`;
      XLSX.writeFile(wb, `${fileName}.xlsx`);

      isExportPopoverShow.value = false;
    } finally {
      isExporting.value = false;
    }
  };

  // ========== 组件挂载时恢复查询状态 ==========
  onMounted(() => {
    const savedState = loadQueryState();
    // 仅当保存的 toolUid 与当前一致时才恢复（避免不同工具实例间串数据）
    if (savedState && savedState.toolUid === props.toolUid && savedState.accountId) {
      nextTick(() => {
        // 恢复表单输入
        queryInputRef.value?.setForm(savedState.accountType, savedState.accountId);
        // 重新执行查询
        handleQuery(savedState.accountType, savedState.accountId);
      });
    }
  });
</script>

<style scoped lang="postcss">
.audit-user-profile {
  /* 分割线 */
  .section-divider {
    height: 1px;
    background: #fff;

    &::before {
      display: block;
      height: 1px;
      margin: 0 24px;
      background: #eaebf0;
      content: '';
    }
  }

  /* 关联游戏列表 */
  .game-list-section {
    margin-bottom: 16px;
  }
}

/* 用户信息 loading 容器 */
.user-info-loading-wrapper {
  min-height: 120px;
  margin-top: 12px;
  background: #fff;
}

/* 用户信息 loading 占位 */
.user-info-loading-placeholder {
  height: 120px;
  padding: 16px 24px 22px;
  background: #fff;
}

/* 游戏列表 loading 容器 */
.game-list-loading-wrapper {
  min-height: 200px;
  background: #fff;
}

/* 游戏列表 loading 占位 */
.game-list-loading-placeholder {
  height: 200px;
  padding: 16px 24px 22px;
  background: #fff;
}

/* 游戏列表为空 */
.game-list-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
}

/* 全部为空时的统一空状态 */
.profile-all-empty {
  display: flex;
  min-height: 360px;
  margin-top: 12px;
  background: #fff;
  align-items: center;
  justify-content: center
}

.top-search {
  padding: 16px 24px 22px;
  background: #fff;

  .top-search-title {
    margin-bottom: 16px;
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    letter-spacing: 0;
    color: #313238;
    align-items: center;
  }
}

.game-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;

  .top-search-title {
    margin-bottom: 0;
  }
}

.game-list-actions {
  display: flex;
  gap: 12px;
  align-items: center;

  .game-search-input {
    width: 500px;
  }
}

/* 导出弹窗样式 */
.export-popover-content {
  padding: 0;

  .export-popover-body {
    padding: 16px 16px 0;
  }

  .export-popover-title {
    margin-bottom: 16px;
    font-size: 16px;
    font-weight: 700;
    line-height: 24px;
    color: #313238;
  }

  .export-form-item {
    margin-bottom: 16px;

    .export-form-label {
      margin-bottom: 8px;
      font-size: 14px;
      line-height: 22px;
      color: #63656e;

      .required-star {
        color: #ea3636;
      }
    }
  }

  .export-checkbox-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px 24px;

    /* bkui-vue 默认给 .bk-checkbox 设置 justify-self: center 和 ~ 选择器加 margin-left: 24px，
       会导致 grid 单元格内复选框居中且偏移，必须强制覆盖以保证严格左对齐 */
    :deep(.bk-checkbox) {
      margin-right: 0 !important;
      margin-left: 0 !important;
      justify-self: start !important;
    }

    :deep(.bk-checkbox ~ .bk-checkbox) {
      margin-left: 0 !important;
    }
  }

  .export-popover-footer {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    padding: 12px 16px;
    margin-top: 8px;
    background: #fafbfd;
    border-top: 1px solid #dcdee5;
  }
}

.game-list-pagination {
  padding-top: 12px;

  :deep(.bk-pagination) {
    display: flex;
    align-items: center;
    width: 100%;

    .is-last {
      margin-left: auto;
    }
  }
}

:deep(.game-list-table) {
  .t-table,
  .t-table__content,
  .t-table__body,
  .t-table td {
    background-color: transparent;
  }

  .t-table--header-wrapper,
  .t-table__header,
  .t-table th {
    background-color: #f0f1f5 !important;
  }

  .t-table--striped .t-table__body tr:nth-child(even) td {
    background-color: transparent !important;
  }
}

/* 默认隐藏 hover-show-icon */
:deep(.hover-show-icon) {
  font-size: 14px;
  cursor: pointer;
  visibility: hidden;
}

/* openid 复制图标样式 */
:deep(.openid-copy-icon) {
  color: #979ba5;

  &:hover {
    color: #3a84ff;
  }
}

/* 责任单数跳转图标样式 */
:deep(.responsibility-jump-icon) {
  color: #3a84ff;
}

/* 鼠标移入表格行时显示图标 */
:deep(.game-list-table .t-table__body tr:hover .hover-show-icon) {
  visibility: visible;
}
</style>

<!-- 全局样式：导出弹窗去除 bk-popover 默认 padding -->
<style lang="postcss">
  /* 导出弹窗：消除 bk-popover 默认的 12px padding（仅作用于当前导出弹窗，不影响其他 popover） */
  .bk-popover.bk-pop2-content.export-popover-wrapper {
    padding: 0 !important;
  }
</style>
