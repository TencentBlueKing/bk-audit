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
    <profile-user-info
      v-if="hasQueried"
      :user-info="userInfo"
      @view-detail="handleViewDetail" />

    <!-- 分割线 -->
    <div
      v-if="hasQueried"
      class="section-divider" />

    <!-- 关联游戏列表 -->
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
  </div>
</template>

<script setup lang="ts">
  import { computed, h, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import { execCopy } from '@utils/assist';

  import ProfileQueryInput from './profile-query-input.vue';
  import ProfileUserInfo from './profile-user-info.vue';

  interface Emits {
    (e: 'openGameDetail', gameData: Record<string, any>, initialTab?: string): void;
  }

  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const router = useRouter();

  const queryInputRef = ref();
  const hasQueried = ref(false);
  const gameSearchKey = ref('');

  // 用户信息假数据
  const userInfo = ref({
    avatar: '',
    wecom: 'frodomei',
    username: '梅彦',
    wechat: 'm******4',
    qq: '3******9',
    status: '在职',
    department: '技术运营部/运营数据开发/互联网应用组以上',
    responsibilityCount: 11,
    riskLevel: '高',
  });

  // 关联游戏列表假数据
  const gameList = ref([
    {
      name: '王者荣耀',
      openid: '47B1fC4b-dc0c-86dB-4f7D-d0FF16EDCe19',
      coinBalance: 561,
      totalRecharge: 561,
      totalGift: 561,
      totalIssue: 561,
      loginCount: 561,
      responsibilityCount: 561,
    },
    {
      name: '刺激战场',
      openid: '4eFdef2B-9aA0-E2cF-C1e5-a1aeb8c6542f',
      coinBalance: 450,
      totalRecharge: 450,
      totalGift: 450,
      totalIssue: 450,
      loginCount: 450,
      responsibilityCount: 450,
    },
    {
      name: '地下城与勇士',
      openid: '6C45de7b-1a8f-Aef3-dF5B-47961B87edd7',
      coinBalance: 859,
      totalRecharge: 859,
      totalGift: 859,
      totalIssue: 859,
      loginCount: 859,
      responsibilityCount: 859,
    },
    {
      name: '金铲铲之战',
      openid: '5D3CccA5-2247-6B37-A4c4-E1fdD378ee3B',
      coinBalance: 565,
      totalRecharge: 565,
      totalGift: 565,
      totalIssue: 565,
      loginCount: 565,
      responsibilityCount: 0,
    },
  ]);

  // 搜索过滤，并按累计赠送逆序排序
  const filteredGameList = computed(() => {
    let list = gameList.value;
    if (gameSearchKey.value) {
      const key = gameSearchKey.value.toLowerCase();
      list = list.filter(item => item.name.toLowerCase().includes(key)
        || item.openid.toLowerCase().includes(key));
    }
    return [...list].sort((a, b) => b.totalGift - a.totalGift);
  });

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
    count: 198,
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

  // 查询
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const handleQuery = (accountType: string, accountId: string) => {
    // TODO: 后续接入接口时，使用 accountType 和 accountId 请求数据
    hasQueried.value = true;
  };

  // 重置
  const handleReset = () => {
    hasQueried.value = false;
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
