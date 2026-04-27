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
            <bk-button>
              <audit-icon
                style="margin-right: 4px;"
                type="download" />
              {{ t('导出') }}
            </bk-button>
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

  import ToolManageService from '@service/tool-manage';

  import { execCopy } from '@utils/assist';

  import ProfileQueryInput from './profile-query-input.vue';
  import ProfileUserInfo from './profile-user-info.vue';

  import useRequest from '@/hooks/use-request';

  // smart_page 工具配置中的数据源定义
  interface DataSource {
    name: string;
    description: string;
    data_source_type: string;
    config: Record<string, any>;
  }

  interface ToolConfig {
    marker_type?: string;
    data_sources?: DataSource[];
    [key: string]: any;
  }

  interface Props {
    toolUid?: string;       // 工具 uid，用于调用执行接口
    toolConfig?: ToolConfig; // 工具 config，包含 data_sources 配置
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
  const gameSearchKey = ref('');

  // 用户信息（默认空值，接口返回后填充）
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

  // 关联游戏列表（接口返回后填充）
  const gameList = ref<Array<Record<string, any>>>([]);

  // 搜索过滤，并按累计赠送逆序排序
  const filteredGameList = computed(() => {
    let list = gameList.value;
    if (gameSearchKey.value) {
      const key = gameSearchKey.value.toLowerCase();
      list = list.filter(item => (item.name || '').toLowerCase().includes(key)
        || (item.openid || '').toLowerCase().includes(key));
    }
    return [...list].sort((a, b) => (b.totalGift || 0) - (a.totalGift || 0));
  });

  // 获取指定名称的数据源配置
  const getDataSource = (name: string): DataSource | undefined => (
    props.toolConfig?.data_sources?.find(ds => ds.name === name)
  );

  // ========== 接口调用：用户信息 ==========
  const {
    loading: userInfoLoading,
    run: fetchUserInfo,
  } = useRequest(ToolManageService.fetchToolsExecute, {
    defaultValue: {},
    onSuccess: (data) => {
      // 从 data.result.results 或 data.data.results 中提取用户信息
      const results = data?.result?.results || data?.data?.results || data?.results;
      if (results && (Array.isArray(results) ? results.length > 0 : true)) {
        const userData = Array.isArray(results) ? results[0] : results;
        // 将接口返回的字段映射到 userInfo
        userInfo.value = {
          avatar: userData.avatar || '',
          wecom: userData.wecom || userData.wx_work_id || '',
          username: userData.username || userData.display_name || '',
          wechat: userData.wechat || userData.wx_id || '',
          qq: userData.qq || '',
          status: userData.status || '',
          department: userData.department || '',
          responsibilityCount: userData.responsibility_count ?? userData.responsibilityCount ?? 0,
          riskLevel: userData.risk_level ?? userData.riskLevel ?? '',
        };
      }
    },
  });

  // ========== 接口调用：关联游戏列表 ==========
  const {
    loading: gameListLoading,
    run: fetchGameList,
  } = useRequest(ToolManageService.fetchToolsExecute, {
    defaultValue: {},
    onSuccess: (data) => {
      const results = data?.result?.results || data?.data?.results || data?.results;
      if (Array.isArray(results)) {
        gameList.value = results;
        pagination.value.count = data?.result?.total || data?.data?.total || results.length;
      }
    },
  });

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
    emit('openGameDetail', gameData, 'overview');
  };

  // 点击查看记录 - 打开新工具tab，自动展示登录记录tab
  const handleViewRecord = (gameData: Record<string, any>) => {
    emit('openGameDetail', gameData, 'login');
  };

  // 点击责任单数跳转 - 新开标签页至场景风险，带入openid筛选
  const handleJumpToSceneRisk = (openid: string) => {
    const routeData = router.resolve({
      name: 'sceneRiskManageList',
      query: { openid },
    });
    window.open(routeData.href, '_blank');
  };

  // 表格列配置
  const gameColumns: Array<Record<string, any>> = [
    {
      label: () => t('游戏名称'),
      field: 'name',
      width: 150,
      render: ({ data }: { data: Record<string, any> }) => h(
        'span',
        {
          style: 'color: #3a84ff; cursor: pointer;',
          onClick: () => handleClickGame(data),
        },
        data.name,
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
            class: 'audit-icon icon-copy hover-show-icon openid-copy-icon',
            onClick: (e: Event) => {
              e.stopPropagation();
              handleCopyOpenid(data.openid);
            },
          }),
        ],
      ),
    },
    { label: () => `${t('代币存量')} (${t('代')})`, field: 'coinBalance', sort: true },
    { label: () => `${t('累计充值')} (${t('代')})`, field: 'totalRecharge', sort: true },
    { label: () => `${t('累计赠送')} (¥)`, field: 'totalGift', sort: true },
    { label: () => `${t('累计发放')} (¥)`, field: 'totalIssue', sort: true },
    { label: () => `${t('登录次数')} / ${t('月')}`, field: 'loginCount', sort: true },
    {
      label: () => t('责任单数'),
      field: 'responsibilityCount',
      sort: true,
      render: ({ data }: { data: Record<string, any> }) => h(
        'span',
        {
          class: 'responsibility-cell',
          style: 'display: inline-flex; align-items: center; gap: 4px;',
        },
        [
          h('span', {}, data.responsibilityCount),
          h('i', {
            class: 'audit-icon icon-jump-link hover-show-icon responsibility-jump-icon',
            onClick: (e: Event) => {
              e.stopPropagation();
              handleJumpToSceneRisk(data.openid);
            },
          }),
        ],
      ),
    },
    {
      label: () => t('操作'),
      field: 'action',
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
    // 翻页时重新请求游戏列表数据源
    const gameDs = getDataSource('related_game_accounts');
    if (gameDs && lastQueryParams.value) {
      executeDataSource(gameDs.name, {
        ...lastQueryParams.value,
        page: pagination.value.current,
        page_size: pagination.value.limit,
      }, fetchGameList);
    }
  };

  const handlePageLimitChange = (limit: number) => {
    pagination.value.limit = limit;
    pagination.value.current = 1;
    const gameDs = getDataSource('related_game_accounts');
    if (gameDs && lastQueryParams.value) {
      executeDataSource(gameDs.name, {
        ...lastQueryParams.value,
        page: pagination.value.current,
        page_size: pagination.value.limit,
      }, fetchGameList);
    }
  };

  // 缓存最近一次查询参数，用于翻页
  const lastQueryParams = ref<Record<string, any> | null>(null);

  // 查询
  const handleQuery = (accountType: string, accountId: string) => {
    hasQueried.value = true;
    const queryParams = {
      [accountType]: accountId,
    };
    lastQueryParams.value = queryParams;

    // 获取 data_sources 配置，遍历执行各数据源
    const dataSources = props.toolConfig?.data_sources || [];

    // 用户画像页面需要调用的数据源（精确匹配接口文档定义）
    // user_basic_info: 用户基础信息
    // risk_ticket_summary: 责任单数及风险系数
    // related_game_accounts: 关联的游戏列表
    const userInfoSources = ['user_basic_info', 'risk_ticket_summary'];
    const gameListSource = 'related_game_accounts';

    if (dataSources.length > 0) {
      dataSources.forEach((ds) => {
        if (userInfoSources.includes(ds.name)) {
          // 用户基础信息 & 责任单数/风险系数
          executeDataSource(ds.name, queryParams, fetchUserInfo);
        } else if (ds.name === gameListSource) {
          // 关联游戏列表（带分页参数）
          executeDataSource(ds.name, {
            ...queryParams,
            page: pagination.value.current,
            page_size: pagination.value.limit,
          }, fetchGameList);
        }
        // 其他数据源（game_trade_records 等）在游戏详情页面调用，此处不处理
      });
    } else {
      // 没有 data_sources 配置时，直接用工具 uid 执行（兼容旧逻辑）
      if (props.toolUid) {
        fetchUserInfo({
          uid: props.toolUid,
          params: {
            data_source_name: 'user_basic_info',
            params: queryParams,
          },
        });
      }
    }
  };

  // 重置
  const handleReset = () => {
    hasQueried.value = false;
    lastQueryParams.value = null;
    // 重置用户信息
    userInfo.value = {
      avatar: '',
      wecom: '',
      username: '',
      wechat: '',
      qq: '',
      status: '',
      department: '',
      responsibilityCount: 0,
      riskLevel: '',
    };
    // 重置游戏列表
    gameList.value = [];
    pagination.value.count = 0;
    pagination.value.current = 1;
  };

  // 查看详情
  const handleViewDetail = () => {
    // TODO: 跳转到责任单详情
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
:deep(tr:hover) {
  .hover-show-icon {
    visibility: visible;
  }
}
</style>
