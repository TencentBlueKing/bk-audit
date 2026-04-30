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
      @query="handleQuery"
      @reset="handleReset" />

    <!-- 用户信息 -->
    <bk-loading :loading="userInfoLoading">
      <profile-user-info
        v-if="hasQueried"
        :user-info="userInfo"
        @view-detail="handleViewDetail" />
    </bk-loading>

    <!-- 分割线 -->
    <div
      v-if="hasQueried"
      class="section-divider" />

    <!-- 关联游戏列表 -->
    <bk-loading :loading="gameListLoading">
      <div
        v-if="hasQueried"
        class="top-search game-list-section">
        <div class="game-list-header">
          <div class="top-search-title">
            {{ t('关联游戏列表') }}
          </div>
          <div class="game-list-actions">
            <bk-input
              v-model="gameSearchKey"
              class="game-search-input"
              :placeholder="t('搜索 游戏名称、openid')"
              type="search" />
            <bk-popover
              ref="exportPopoverRef"
              :is-show="isExportPopoverShow"
              placement="bottom-start"
              theme="light"
              trigger="click"
              :width="420"
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
        <bk-table
          :columns="gameColumns"
          :data="filteredGameList"
          :pagination="pagination"
          remote-pagination
          stripe
          @page-limit-change="handlePageLimitChange"
          @page-value-change="handlePageChange" />
      </div>
    </bk-loading>
  </div>
</template>

<script setup lang="ts">
  import { computed, h, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';
  import * as XLSX from 'xlsx';

  import ToolManageService from '@service/tool-manage';

  import { execCopy } from '@utils/assist';

  import ProfileQueryInput from './profile-query-input.vue';
  import ProfileUserInfo from './profile-user-info.vue';

  import useRequest from '@/hooks/use-request';

  interface Props {
    toolUid?: string;       // 工具 uid，用于调用执行接口
    toolName?: string;      // 工具名称，用于导出文件命名
  }

  interface Emits {
    (e: 'openGameDetail', gameData: Record<string, any>, initialTab?: string): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    toolUid: '',
    toolName: '',
  });
  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const router = useRouter();

  const queryInputRef = ref();
  const hasQueried = ref(false);
  const gameSearchKey = ref('');

  // ========== 日期参数计算工具函数 ==========
  // 获取近一年起始日期，格式 YYYYMMDD
  const getOneYearAgoYmd = (): string => {
    const d = new Date();
    d.setFullYear(d.getFullYear() - 1);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}${m}${day}`;
  };

  // 用户信息（默认空值，接口返回后填充）
  // 按设计稿只展示：企业微信、用户名、微信、QQ、在职状态、部门 + 责任单数/风险系数
  const userInfo = ref({
    avatar: '',
    wecom: '',       // 企业微信
    username: '',    // 用户名
    wechat: '',      // 微信（来自 main_qqwechat_list）
    qq: '',          // QQ（来自 main_qqwechat_list）
    status: '',      // 在职状态
    department: '',  // 部门
    responsibilityCount: 0,  // 责任单数（来自 main_auditrisk_stat）
    riskLevel: '',           // 风险系数（来自 main_auditrisk_stat）
  });

  // 关联游戏列表（接口返回后填充）
  const gameList = ref<Array<Record<string, any>>>([]);

  // 缓存 openid_list_first_ctx（微信/QQ/openid 搜索时，从 main_openid_list 首条结果获取的 ctx）
  const openidListFirstCtx = ref('');

  // 缓存最近一次查询参数，用于翻页
  const lastQueryParams = ref<Record<string, any> | null>(null);
  // 缓存最近一次查询的账号类型
  const lastAccountType = ref('');

  // 搜索过滤，并按累计赠送逆序排序
  const filteredGameList = computed(() => {
    let list = gameList.value;
    if (gameSearchKey.value) {
      const key = gameSearchKey.value.toLowerCase();
      list = list.filter(item => (item.name || item.游戏名称 || '').toLowerCase().includes(key)
        || (item.openid || '').toLowerCase().includes(key));
    }
    return [...list].sort((a, b) => (b.totalGift || b.总支出 || 0) - (a.totalGift || a.总支出 || 0));
  });

  // ========== 接口调用：用户信息 (main_user_info) ==========
  const {
    loading: userInfoLoading,
    run: fetchUserInfo,
  } = useRequest(ToolManageService.fetchToolsExecute, {
    defaultValue: {},
    onSuccess: (data) => {
      // smart_page 工具返回结构: data.data.result.results
      const results = data?.data?.result?.results
        || data?.result?.results || data?.data?.results || data?.results;
      if (results && (Array.isArray(results) ? results.length > 0 : true)) {
        const userData = Array.isArray(results) ? results[0] : results;
        // 将接口返回的字段映射到 userInfo（按设计稿只取6个展示字段）
        userInfo.value = {
          ...userInfo.value,
          avatar: userData.avatar || userData.头像 || '',
          wecom: userData.企业微信 || userData.wecom || userData.wx_work_id || '',
          username: userData.用户名 || userData.username || userData.display_name || '',
          status: userData.在职状态 || userData.status || '',
          department: userData.部门 || userData.department || '',
        };

        // 企业微信搜索成功后，获取到 username(企业微信)，
        // 用它作为 user_info_output_var_ctx 触发查询 main_qqwechat_list 和 main_auditrisk_stat
        const ctx = userInfo.value.wecom || userData.企业微信 || '';
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
      // smart_page 工具返回结构: data.data.result.results
      const results = data?.data?.result?.results
        || data?.result?.results || data?.data?.results || data?.results;
      if (results) {
        const statData = Array.isArray(results) ? results[0] : results;
        if (statData) {
          userInfo.value.responsibilityCount = statData.count_tickets
            ?? statData.责任单数 ?? statData.responsibility_count ?? 0;
          // max_risk_level_num: 3=高, 2=中, 1=低, 0=无
          const riskNum = statData.max_risk_level_num
            ?? statData.风险系数 ?? statData.risk_level ?? 0;
          const riskMap: Record<number, string> = { 3: '高', 2: '中', 1: '低', 0: '无' };
          userInfo.value.riskLevel = riskMap[Number(riskNum)] ?? String(riskNum);
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
      // smart_page 工具返回结构: data.data.result.results
      const results = data?.data?.result?.results
        || data?.result?.results || data?.data?.results || data?.results;
      if (results) {
        const qqwechatData = Array.isArray(results) ? results : [results];
        // 从结果中提取微信和QQ账号
        const wechatAccounts: string[] = [];
        const qqAccounts: string[] = [];
        qqwechatData.forEach((item: any) => {
          const accountType = item.账号类型 || item.account_type || '';
          const accountList = item.账号列表 || item.account_list || '';
          if (accountType === '微信' || accountType === 'wechat') {
            wechatAccounts.push(accountList);
          } else if (accountType === 'QQ' || accountType === 'qq') {
            qqAccounts.push(accountList);
          }
        });
        if (wechatAccounts.length > 0) {
          userInfo.value.wechat = wechatAccounts.join(', ');
        }
        if (qqAccounts.length > 0) {
          userInfo.value.qq = qqAccounts.join(', ');
        }
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
      // smart_page 工具返回结构: data.data.result.results
      const results = data?.data?.result?.results
        || data?.result?.results || data?.data?.results || data?.results;
      if (Array.isArray(results)) {
        gameList.value = results;
        pagination.value.count = data?.data?.result?.total
          || data?.result?.total || data?.data?.total || results.length;

        // 从首条结果中提取 ctx 作为 openid_list_first_ctx
        if (results.length > 0) {
          const firstRow = results[0];
          openidListFirstCtx.value = firstRow.ctx || firstRow.平台账号 || firstRow.企业微信 || '';
        }

        // 微信/QQ/openid 搜索时，游戏列表返回后需要级联查询用户信息
        if (['form_wechat', 'form_qq', 'openid'].includes(lastAccountType.value)) {
          if (lastAccountType.value === 'openid' && results.length === 1) {
            // openid 搜索且仅有1条结果：直接跳转游戏详情
            const gameData = mapGameData(results[0]);
            // 赋值 openid_list_selected_* 变量
            emit('openGameDetail', gameData, 'overview');
          }

          // 有结果时，用 openid_list_first_ctx 查询用户信息
          if (openidListFirstCtx.value) {
            executeUserInfoByCtx(openidListFirstCtx.value);
          }
        }
      }
    },
  });

  // 映射游戏数据字段
  const mapGameData = (row: Record<string, any>) => ({
    name: row.游戏名称 || row.name || '',
    openid: row.openid || '',
    gameid: row.gameid || '',
    ctx: userInfo.value.wecom || '',
    wechat: userInfo.value.wechat || '',
    coinBalance: row.代币存量 || row['代币存量（代）'] || row.coinBalance || 0,
    totalRecharge: row.累计充值 || row['累计充值（代）'] || row.totalRecharge || 0,
    totalGift: row.总支出 || row.totalGift || 0,
    totalIssue: row.总入账 || row.totalIssue || 0,
    totalBalance: row.总余额 || row.totalBalance || 0,
    totalTopup: row.总充值 || row.totalTopup || 0,
    source: row.source || '',
    platformAccount: row.平台账号 || row.platformAccount || '',
    exchangeRate: row.人民币代币兑换比 || row.exchangeRate || '',
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

  // 点击责任单数跳转 - 新开标签页至场景风险，带入openid筛选
  const handleJumpToSceneRisk = (openid: string) => {
    const routeData = router.resolve({
      name: 'sceneRiskManageList',
      query: { openid },
    });
    window.open(routeData.href, '_blank');
  };

  // 表格列配置（按设计稿：游戏名称 | openid | 代币存量(代) | 累计充值(代) | 累计赠送(¥) | 累计发放(¥) | 登录次数/月 | 责任单数 | 操作）
  const gameColumns: Array<Record<string, any>> = [
    {
      label: () => t('游戏名称'),
      field: 'name',
      width: 120,
      render: ({ data }: { data: Record<string, any> }) => h(
        'span',
        {
          style: 'color: #3a84ff; cursor: pointer;',
          onClick: () => handleClickGame(data),
        },
        data.游戏名称 || data.name,
      ),
    },
    {
      label: () => 'openid',
      field: 'openid',
      minWidth: 320,
      showOverflowTooltip: true,
      render: ({ data }: { data: Record<string, any> }) => h(
        'span',
        {
          class: 'openid-cell',
          style: 'display: inline-flex; align-items: center; gap: 4px;',
        },
        [
          h('span', {}, data.openid),
          h('i', {
            class: 'audit-icon audit-icon-copy hover-show-icon openid-copy-icon',
            onClick: (e: Event) => {
              e.stopPropagation();
              handleCopyOpenid(data.openid);
            },
          }),
        ],
      ),
    },
    { label: () => `${t('代币存量')} (${t('代')})`, field: '代币存量（代）', sort: true },
    { label: () => `${t('累计充值')} (${t('代')})`, field: '累计充值（代）', sort: true },
    { label: () => `${t('累计赠送')} (¥)`, field: '累计赠送（¥）', sort: true },
    { label: () => `${t('累计发放')} (¥)`, field: '累计发放（¥）', sort: true },
    { label: () => `${t('登录次数')} / ${t('月')}`, field: '登录次数/月', sort: true },
    {
      label: () => t('责任单数'),
      field: '责任单数',
      sort: true,
      render: ({ data }: { data: Record<string, any> }) => {
        const count = data.责任单数 ?? data.responsibility_count ?? 0;
        const hasRisk = count > 0;
        return h(
          'span',
          {
            style: hasRisk ? 'display: inline-flex; align-items: center; gap: 4px;' : '',
          },
          [
            h('span', {}, count),
            hasRisk
              ? h('i', {
                class: 'audit-icon audit-icon-jump-link hover-show-icon responsibility-jump-icon',
                style: 'cursor: pointer;',
                onClick: (e: Event) => {
                  e.stopPropagation();
                  handleJumpToSceneRisk(data.openid);
                },
              })
              : null,
          ],
        );
      },
    },
    {
      label: () => t('操作'),
      field: 'action',
      width: 100,
      render: ({ data }: { data: Record<string, any> }) => h(
        'span',
        {
          style: 'color: #3a84ff; cursor: pointer;',
          onClick: () => handleViewRecord(data),
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
    if (lastQueryParams.value) {
      executeDataSource('main_openid_list', {
        ...lastQueryParams.value,
        page: pagination.value.current,
        page_size: pagination.value.limit,
      }, fetchGameList);
    }
  };

  const handlePageLimitChange = (limit: number) => {
    pagination.value.limit = limit;
    pagination.value.current = 1;
    if (lastQueryParams.value) {
      executeDataSource('main_openid_list', {
        ...lastQueryParams.value,
        page: pagination.value.current,
        page_size: pagination.value.limit,
      }, fetchGameList);
    }
  };

  // ========== 查询入口：根据账号类型分发不同的查询链路 ==========
  const handleQuery = (accountType: string, accountId: string) => {
    hasQueried.value = true;
    lastAccountType.value = accountType;

    // 重置中间变量
    openidListFirstCtx.value = '';
    gameList.value = [];
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
        [accountType]: accountId,
      }, fetchGameList);
    } else if (accountType === 'openid') {
      // ===== 选择openid =====
      // 1. 查询"游戏列表" main_openid_list（输入 form_openid=openid）
      //    成功后 onSuccess 中自动：
      //    a. 仅1条 → 直接跳转游戏详情
      //    b. 大于1条 → 触发查询用户信息 + 展示列表
      lastQueryParams.value = { form_openid: accountId };
      executeDataSource('main_openid_list', {
        form_openid: accountId,
      }, fetchGameList);
    }
  };

  // 重置
  const handleReset = () => {
    hasQueried.value = false;
    lastQueryParams.value = null;
    lastAccountType.value = '';
    openidListFirstCtx.value = '';
    // 重置用户信息
    userInfo.value = {
      avatar: '', wecom: '', username: '', wechat: '', qq: '',
      status: '', department: '',
      responsibilityCount: 0, riskLevel: '',
    };
    // 重置游戏列表
    gameList.value = [];
    pagination.value.count = 0;
    pagination.value.current = 1;
  };

  // 查看详情 - 新开标签页跳转至场景风险，带入企微名称作为责任人(operator)筛选
  const handleViewDetail = () => {
    const { wecom } = userInfo.value;
    const routeData = router.resolve({
      name: 'sceneRiskManageList',
      query: wecom ? { operator: wecom } : {},
    });
    window.open(routeData.href, '_blank');
  };

  // ========== 导出功能 ==========
  const exportPopoverRef = ref();
  const isExportPopoverShow = ref(false);
  const isExporting = ref(false);

  // 导出内容选项（对应表格列）
  const exportContentOptions = [
    { id: 'gameName', name: t('游戏名称'), field: '游戏名称', fallbackField: 'name' },
    { id: 'openid', name: 'openid', field: 'openid', fallbackField: '' },
    { id: 'coinBalance', name: `${t('代币存量')}(${t('代')})`, field: '代币存量（代）', fallbackField: 'coinBalance' },
    { id: 'totalRecharge', name: `${t('累计充值')}(${t('代')})`, field: '累计充值（代）', fallbackField: 'totalRecharge' },
    { id: 'totalGift', name: `${t('累计赠送')}(¥)`, field: '累计赠送（¥）', fallbackField: 'totalGift' },
    { id: 'totalIssue', name: `${t('累计发放')}(¥)`, field: '累计发放（¥）', fallbackField: 'totalIssue' },
    { id: 'loginCount', name: `${t('登录次数')}/${t('月')}`, field: '登录次数/月', fallbackField: 'loginCount' },
    { id: 'responsibilityCount', name: t('责任单数'), field: '责任单数', fallbackField: 'responsibility_count' },
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
        colWidths.push({ wch: Math.min(maxLen + 2, 50) });
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

      // 导出文件，文件名为工具名
      const fileName = props.toolName || t('关联游戏列表');
      XLSX.writeFile(wb, `${fileName}.xlsx`);

      isExportPopoverShow.value = false;
    } finally {
      isExporting.value = false;
    }
  };
</script>

<style scoped lang="postcss">
.audit-user-profile {
  /* 分割线 */
  .section-divider {
    height: 1px;
    margin: 0 24px;
    background: #eaebf0;
  }

  /* 关联游戏列表 */
  .game-list-section {
    margin-bottom: 16px;
  }
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

  .top-search-title {
    margin-bottom: 0;
  }
}

.game-list-actions {
  display: flex;
  gap: 8px;
  align-items: center;

  .game-search-input {
    width: 320px;
  }
}

/* 导出弹窗样式 */
.export-popover-content {
  padding: 4px 0;

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
    gap: 12px 24px;
  }

  .export-popover-footer {
    display: flex;
    gap: 8px;
    justify-content: center;
    padding-top: 8px;
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
:deep(tr:hover .hover-show-icon) {
  visibility: visible;
}
</style>
