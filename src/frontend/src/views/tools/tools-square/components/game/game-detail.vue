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
  <div class="game-detail">
    <!-- 上方游戏基本信息 -->
    <div class="game-header">
      <div class="game-info-row">
        <div class="info-item">
          <span class="info-label">{{ t('游戏名称') }}</span>
          <span class="info-value">{{ gameData.name }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">openid</span>
          <span class="info-value">
            {{ gameData.openid }}
            <audit-icon
              class="copy-icon"
              type="copy"
              @click="handleCopy(gameData.openid)" />
          </span>
        </div>
        <div class="info-item">
          <span class="info-label">{{ gameData.platType === 'qq' ? 'QQ' : '微信' }}</span>
          <span class="info-value">
            <template v-if="gameData.platType || gameData.platAccount">
              {{ isPlatAccountVisible ? gameData.platAccount : '******' }}
              <audit-icon
                class="eye-icon"
                :type="isPlatAccountVisible ? 'view' : 'unview'"
                @click="isPlatAccountVisible = !isPlatAccountVisible" />
            </template>
            <template v-else>
              {{ t('此账号未关联平台账号') }}
            </template>
          </span>
        </div>
        <div class="info-item">
          <span class="info-label">{{ t('代币存量') }}</span>
          <span class="info-value"><span class="info-unit">{{ t('代') }}</span> {{ gameData.coinBalance }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">{{ t('累计充值') }}</span>
          <span class="info-value"><span class="info-unit">{{ t('代') }}</span> {{ gameData.totalRecharge }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">{{ t('累计发放') }}</span>
          <span class="info-value"><span class="info-unit">¥</span> {{ gameData.totalIssue }}</span>
        </div>
        <!-- 累计赠送次数、累计发放次数：后端暂未返回，有数据后再展示 -->
        <!-- <div class="info-item">
          <span class="info-label">{{ t('累计赠送次数') }}</span>
          <span class="info-value">{{ gameData.totalGiftCount ?? '- -' }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">{{ t('累计发放次数') }}</span>
          <span class="info-value">{{ gameData.totalIssueCount ?? '- -' }}</span>
        </div> -->
      </div>
      <bk-popover
        ref="exportPopoverRef"
        ext-cls="export-popover-wrapper"
        :is-show="isExportPopoverShow"
        placement="bottom-end"
        theme="light"
        trigger="manual"
        :width="340">
        <bk-button
          class="export-btn"
          @click.stop="isExportPopoverShow = !isExportPopoverShow">
          <audit-icon
            style="margin-right: 4px;"
            type="download" />
          {{ t('导出') }}
        </bk-button>
        <template #content>
          <div
            class="export-popover-content"
            @click.stop>
            <div class="export-popover-body">
              <div class="export-popover-title">
                {{ t('导出游戏审计数据') }}
              </div>
              <div class="export-form-item">
                <div class="export-form-label">
                  {{ t('时间范围') }}
                  <span class="required-star">*</span>
                </div>
                <bk-date-picker
                  v-model="exportDateRange"
                  append-to-body
                  :clearable="false"
                  :shortcut-selected-index="exportShortcutSelectedIndex"
                  :shortcuts="exportDateShortcuts"
                  style="width: 100%"
                  type="daterange"
                  use-shortcut-text />
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
                      :disabled="item.disabled"
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
                @click="handleExport">
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

    <!-- Tab 标签页 -->
    <div class="game-tabs">
      <bk-tab
        v-model:active="activeTab"
        type="card-grid">
        <bk-tab-panel
          :label="t('概览')"
          name="overview">
          <!-- 概览内容 - 每个 section 独立骨架屏 -->
          <div class="overview-content">
            <div
              v-for="section in overviewSections"
              :key="section.key"
              class="section">
              <!-- 标题行（始终显示） -->
              <div class="section-title-row">
                <span class="section-title">{{ section.title }}</span>
                <span
                  v-if="section.tabKey"
                  class="view-detail-link"
                  @click.stop="handleViewDetail(section.tabKey!)">
                  <img
                    class="view-detail-icon"
                    src="@/images/file.svg">
                  {{ t('查看详情') }}
                </span>
              </div>

              <!-- loading 时显示简洁占位 -->
              <div
                v-if="sectionLoadingMap[section.key]"
                class="section-skeleton">
                <bk-loading
                  loading
                  size="small" />
              </div>

              <template v-else>
                <!-- 该 section 无数据时显示空提示 -->
                <div
                  v-if="isSectionEmpty(section.key)"
                  class="section-empty">
                  <span class="section-empty-text">{{ t('暂无数据') }}</span>
                </div>
                <template v-else>
                  <!-- 最近记录行 -->
                  <div
                    v-if="section.lastRecordItems?.length"
                    class="last-record-row">
                    <span
                      v-for="item in section.lastRecordItems"
                      :key="item.label"
                      class="record-item">
                      <span class="record-label">{{ item.label }}：</span>
                      <span class="record-value">{{ item.value }}</span>
                    </span>
                  </div>

                  <!-- 表格（simple 模式） -->
                  <record-detail-table
                    v-if="section.table"
                    :columns="section.table.columns"
                    :data="section.table.data"
                    simple />
                </template>
              </template>
            </div>
          </div>
        </bk-tab-panel>

        <bk-tab-panel
          v-for="tab in recordTabs"
          :key="tab.key"
          :label="tab.label"
          :name="tab.key">
          <game-record-tab
            :chart-active-names="tabChartActiveNames[tab.key]"
            :chart-columns="tab.chartColumns"
            :chart-loading="tabChartLoadingMap[tab.key]"
            :chart-rows="tab.chartRows"
            :chart-title="tab.chartTitle"
            :external-conditions="tabSearchConditions[tab.key]"
            :search-fields="tab.searchFields"
            :search-placeholder="tab.searchPlaceholder"
            :show-chart="tab.showChart !== false"
            :table-columns="tab.table.columns"
            :table-data="tab.table.data"
            :table-loading="tabTableLoadingMap[tab.key]"
            :table-pagination="tab.table.pagination"
            :table-title="tab.table.title"
            @date-change="handleTabDateChange(tab.key, $event)"
            @legend-click="handleTabLegendClick(tab.key, $event)"
            @page-change="handleTabPageChange(tab.key, $event)"
            @page-limit-change="handleTabPageLimitChange(tab.key, $event)"
            @search-condition-change="handleTabSearchConditionChange(tab.key, $event)">
            <!-- 插槽控制 -->
            <template
              v-if="tab.extraFilter === 'chatViolation'"
              #extra-filter>
              <bk-checkbox
                v-model="chatSuspectedViolation"
                class="suspected-violation-checkbox">
                {{ t('疑似违规') }}
              </bk-checkbox>
            </template>
          </game-record-tab>
        </bk-tab-panel>
      </bk-tab>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import * as XLSX from 'xlsx';

  import useExportExcel from '@hooks/use_export_excel';

  import { execCopy } from '@utils/assist';

  import {
    type ChartConfig,
    useChartTableLink,
    useGameChartBuilders,
  } from './game-chart-builder';
  import {
    createDataSourceExecutor,
    extractResults,
    formatYmd,
    getDateParams,
    mergeRoleStats,
    useGameDetailFetcher,
    useGameOverviewFetcher,
  } from './game-data-fetcher';
  import {
    CHAT_DETAIL_FIELDS,
    COIN_DETAIL_FIELDS,
    EXPORT_USER_FIELDS,
    GIFT_DETAIL_FIELDS,
    LOGIN_DETAIL_FIELDS,
    TRADE_DETAIL_FIELDS,
  } from './game-field-keys';
  import GameRecordTab from './game-record-tab.vue';
  import { type SearchFieldItem, useGameSearchFields } from './game-search-fields';
  import { formatIsoDateTime, useGameTableColumns } from './game-table-columns';
  import RecordDetailTable from './record-detail-table.vue';

  interface GameRecordTabConfig {
    key: string;
    label: string;
    chartRows: ChartConfig[][];
    chartTitle?: string;
    chartColumns?: number;
    searchPlaceholder: string;
    searchFields: SearchFieldItem[];
    table: {
      columns: Array<Record<string, any>>;
      data: Array<Record<string, any>>;
      pagination: { count: number; current: number; limit: number };
      title: string;
    };
    extraFilter?: 'chatViolation';
    showChart?: boolean;
  }

  interface GameData {
    name: string;
    openid: string;
    gameid: string | number;
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

  interface Props {
    gameData?: GameData;
    initialTab?: string;
    toolUid?: string;
  }

  const props = withDefaults(defineProps<Props>(), {
    gameData: () => ({
      name: '',
      openid: '',
      gameid: '',
      ctx: '',
      wechat: '',
      platType: '',
      platAccount: '',
      loginDays31: 0,
      coinBalance: 0,
      totalRecharge: 0,
      totalGift: 0,
      totalIssue: 0,
    }),
    initialTab: '',
    toolUid: '',
  });

  const { t } = useI18n();
  const activeTab = ref(props.initialTab || 'overview');

  // 当 initialTab 变化时同步切换 tab
  watch(() => props.initialTab, (newTab) => {
    if (newTab) {
      activeTab.value = newTab;
    }
  });

  // 点击概览中的"查看详情"切换到对应 tab
  const handleViewDetail = (tabKey: string) => {
    if (!tabKey) return;
    activeTab.value = tabKey;
  };

  // ========== 数据加载（统一封装在 game-data-fetcher.ts） ==========
  const getCtx = () => ({
    toolUid: props.toolUid,
    gameid: props.gameData.gameid,
    openid: props.gameData.openid,
  });
  const executeDataSource = createDataSourceExecutor(getCtx);

  // 微信号显示/隐藏
  const isPlatAccountVisible = ref(false);

  // 复制
  const handleCopy = (text: string) => {
    execCopy(text, t('复制成功'));
  };

  // ========== 列配置和搜索字段（从外部文件导入） ==========
  const {
    roleColumns, loginStatColumns, loginDetailColumns,
    giveDetailColumns, dealDetailColumns, sapDetailColumns, chatDetailColumns,
  } = useGameTableColumns();
  const {
    loginSearchFields, giftSearchFields, tradeSearchFields,
    coinSearchFields, chatSearchFields,
  } = useGameSearchFields();

  // ========== 概览数据 composable ==========
  const {
    roleList, loginStatList,
    lastLoginRecord, lastGiveRecord, lastDealRecord, lastSapRecord, lastChatRecord,
    sectionLoadingMap, fetchOverviewData,
  } = useGameOverviewFetcher(executeDataSource, getCtx);

  // ========== 概览 sections 配置 ==========
  interface OverviewSectionConfig {
    key: string;
    title: string;
    tabKey?: string;
    lastRecordItems?: Array<{ label: string; value: string | number }>;
    table?: {
      columns: Array<Record<string, any>>;
      data: Array<Record<string, any>>;
    };
  }

  const overviewSections = computed<OverviewSectionConfig[]>(() => [
    {
      key: 'role',
      title: t('角色行为概览'),
      table: { columns: roleColumns, data: roleList.value },
    },
    {
      key: 'login',
      title: t('登录记录'),
      tabKey: 'login',
      lastRecordItems: [
        { label: t('最近一次登录时间'), value: lastLoginRecord.value[LOGIN_DETAIL_FIELDS.LOGIN_TIME] || '--' },
        { label: t('登录地点'), value: lastLoginRecord.value[LOGIN_DETAIL_FIELDS.LOGIN_LOCATION] || '--' },
        { label: t('登录IP'), value: lastLoginRecord.value[LOGIN_DETAIL_FIELDS.LOGIN_IP] || '--' },
        { label: t('登录设备'), value: lastLoginRecord.value[LOGIN_DETAIL_FIELDS.LOGIN_DEVICE] || '--' },
      ],
      table: { columns: loginStatColumns, data: loginStatList.value },
    },
    {
      key: 'gift',
      title: t('赠送记录'),
      tabKey: 'gift',
      lastRecordItems: [
        { label: t('最近一次赠送时间'), value: lastGiveRecord.value[GIFT_DETAIL_FIELDS.TIME] || '--' },
        { label: t('赠送账号'), value: lastGiveRecord.value[GIFT_DETAIL_FIELDS.TARGET_OPENID] || '--' },
        { label: t('道具名称'), value: lastGiveRecord.value[GIFT_DETAIL_FIELDS.ITEM_NAME] || '--' },
        { label: t('赠送总额'), value: lastGiveRecord.value[GIFT_DETAIL_FIELDS.GIFT_AMOUNT] ? `${lastGiveRecord.value[GIFT_DETAIL_FIELDS.GIFT_AMOUNT]} 元` : '--' },
      ],
    },
    {
      key: 'trade',
      title: t('交易记录'),
      tabKey: 'trade',
      lastRecordItems: [
        { label: t('最近一次交易时间'), value: lastDealRecord.value[TRADE_DETAIL_FIELDS.TRADE_TIME] || '--' },
        { label: t('交易对象'), value: lastDealRecord.value[TRADE_DETAIL_FIELDS.TRADE_TARGET] || '--' },
        { label: t('道具名称'), value: lastDealRecord.value[TRADE_DETAIL_FIELDS.ITEM_NAME] || '--' },
        { label: t('交易总额'), value: lastDealRecord.value[TRADE_DETAIL_FIELDS.TRADE_TOTAL] ? `${lastDealRecord.value[TRADE_DETAIL_FIELDS.TRADE_TOTAL]} 元` : '--' },
      ],
    },
    {
      key: 'coin',
      title: t('代币发放记录'),
      tabKey: 'coin',
      lastRecordItems: [
        { label: t('最近一次发放时间'), value: formatIsoDateTime(lastSapRecord.value[COIN_DETAIL_FIELDS.ISSUE_TIME]) },
        { label: t('发放人'), value: lastSapRecord.value[COIN_DETAIL_FIELDS.ISSUER] || '--' },
        { label: t('发放数量'), value: lastSapRecord.value[COIN_DETAIL_FIELDS.ISSUE_COUNT] ? `代 ${lastSapRecord.value[COIN_DETAIL_FIELDS.ISSUE_COUNT]}` : '--' },
        { label: t('发放金额'), value: (lastSapRecord.value[COIN_DETAIL_FIELDS.ISSUE_AMOUNT_SHORT] ?? lastSapRecord.value[COIN_DETAIL_FIELDS.ISSUE_AMOUNT]) ? `${lastSapRecord.value[COIN_DETAIL_FIELDS.ISSUE_AMOUNT_SHORT] ?? lastSapRecord.value[COIN_DETAIL_FIELDS.ISSUE_AMOUNT]} 元` : '--' },
      ],
    },
    {
      key: 'chat',
      title: t('聊天记录'),
      tabKey: 'chat',
      lastRecordItems: [
        { label: t('最近一次聊天时间'), value: lastChatRecord.value[CHAT_DETAIL_FIELDS.CHAT_TIME] || '--' },
        { label: t('发起人'), value: lastChatRecord.value[CHAT_DETAIL_FIELDS.CHAT_TARGET] || lastChatRecord.value[CHAT_DETAIL_FIELDS.INITIATOR] || '--' },
        { label: t('大区ID'), value: lastChatRecord.value[CHAT_DETAIL_FIELDS.ZONE_ID] || '--' },
        { label: t('聊天内容'), value: lastChatRecord.value[CHAT_DETAIL_FIELDS.CHAT_CONTENT] || '--' },
      ],
    },
  ]);

  // ========== 明细 Tab 数据 composable（同时包含各 tab 的 stats / detail / pagination / loading / dateRange） ==========
  const chatSuspectedViolation = ref(true);
  const {
    loginGroupStats, loginDetailList, loginPagination,
    giveGroupStats, giveDetailList, giftPagination,
    dealGroupStats, dealDetailList, tradePagination,
    sapGroupStats, sapDetailList, coinPagination,
    chatDetailList, chatPagination,
    tabChartLoadingMap, tabTableLoadingMap, tabDataLoaded,
    fetchChatData, loadTabData,
    handleTabPageChange, handleTabPageLimitChange, handleTabDateChange,
  } = useGameDetailFetcher(executeDataSource, getCtx, chatSuspectedViolation);

  // 饼图数据构建（业务逻辑统一在 game-chart-builder.ts）
  const {
    buildLoginChartRows, buildGiveChartRows,
    buildDealChartRows, buildSapChartRows,
  } = useGameChartBuilders();
  const loginChartRows = computed<ChartConfig[][]>(() => buildLoginChartRows(
    loginGroupStats.value,
    loginDetailList.value,
  ));
  const giveChartRows = computed<ChartConfig[][]>(() => buildGiveChartRows(giveGroupStats.value));
  const dealChartRows = computed<ChartConfig[][]>(() => buildDealChartRows(dealGroupStats.value));
  const sapChartRows = computed<ChartConfig[][]>(() => buildSapChartRows(sapGroupStats.value));

  // ========== 各 Tab 搜索条件缓存 ==========
  const tabSearchConditions = ref<Record<string, any[]>>({
    login: [],
    gift: [],
    trade: [],
    coin: [],
    chat: [],
  });

  // ========== 图表 ↔ 表格 联动（图例点击 → 搜索条件 / 反向同步）==========
  const { tabChartActiveNames, handleLegendClick: handleTabLegendClick } = useChartTableLink(
    tabSearchConditions,
    {
      login: loginSearchFields,
      gift: giftSearchFields,
      trade: tradeSearchFields,
      coin: coinSearchFields,
      chat: chatSearchFields,
    },
  );

  // 根据搜索条件过滤表格数据（支持操作符）
  // ConditionTag 结构：{ fieldId, fieldName, operator, operatorName, value }
  const filterDataByConditions = (
    data: Array<Record<string, any>>,
    conditions: any[],
    searchFields: SearchFieldItem[] = [],
  ): Array<Record<string, any>> => {
    if (!conditions || conditions.length === 0) return data;
    return data.filter(row => conditions.every((condition) => {
      const { fieldId } = condition;
      const operator = condition.operator || 'like'; // 默认操作符为"包含"
      const searchValue = String(condition.value || '');
      if (!searchValue) return true;
      // 通过 fieldId 查找对应的 fieldKey（后端数据字段名），用于匹配行数据
      const fieldConfig = searchFields.find(f => f.id === fieldId);
      const dataKey = fieldConfig?.fieldKey || fieldId;

      // 取数据值并去除前后空白，避免后端返回数据带空格导致匹配失败
      const cellValue = String(row[dataKey] ?? '').trim();
      const cellValueLower = cellValue.toLowerCase();

      // 单值（eq/neq/like/gt/lt/...）：直接整体使用 searchValue
      // 多值（in/not_in）：按中英文逗号分隔为多个值
      const singleValue = searchValue.trim();
      const multiValues = searchValue.split(/[,，]/).map((s: string) => s.trim())
        .filter(Boolean);

      switch (operator) {
      case 'eq': // 等于（单值，忽略大小写）
        return cellValueLower === singleValue.toLowerCase();
      case 'neq': // 不等于（单值，忽略大小写）
        return cellValueLower !== singleValue.toLowerCase();
      case 'gt': // 大于
        return Number(cellValue) > Number(singleValue);
      case 'lt': // 小于
        return Number(cellValue) < Number(singleValue);
      case 'gte': // 大于等于
        return Number(cellValue) >= Number(singleValue);
      case 'lte': // 小于等于
        return Number(cellValue) <= Number(singleValue);
      case 'in': // IN（多值，命中任一即通过，忽略大小写）
        return multiValues.some((sv: string) => sv.toLowerCase() === cellValueLower);
      case 'not_in': // NOT IN（多值，全部不命中才通过，忽略大小写）
        return multiValues.every((sv: string) => sv.toLowerCase() !== cellValueLower);
      case 'like': // 包含（单值，子串匹配，忽略大小写）
      default:
        return cellValueLower.includes(singleValue.toLowerCase());
      }
    }));
  };

  // ========== 统一 Tab 配置 ==========
  const recordTabs = computed<GameRecordTabConfig[]>(() => [
    {
      key: 'login',
      label: t('登录记录'),
      chartRows: loginChartRows.value,
      chartTitle: t('登录分布总览'),
      chartColumns: 3,
      searchPlaceholder: t('搜索 登录地点、登录IP、大区ID、角色ID、角色名称、等级、登录设备、机型'),
      searchFields: loginSearchFields,
      table: {
        columns: loginDetailColumns,
        data: filterDataByConditions(loginDetailList.value, tabSearchConditions.value.login, loginSearchFields),
        pagination: loginPagination.value,
        title: t('登录明细'),
      },
    },
    {
      key: 'gift',
      label: t('赠送记录'),
      chartRows: giveChartRows.value,
      chartTitle: t('赠送分布总览'),
      searchPlaceholder: t('搜索 赠送对象、昵称、是否员工、大区、道具ID、道具名称、赠送总额、赠送单价、赠送数量、赠送次数'),
      searchFields: giftSearchFields,
      table: {
        columns: giveDetailColumns,
        data: filterDataByConditions(giveDetailList.value, tabSearchConditions.value.gift, giftSearchFields),
        pagination: giftPagination.value,
        title: t('赠送明细'),
      },
    },
    {
      key: 'trade',
      label: t('交易记录'),
      chartRows: dealChartRows.value,
      chartTitle: t('交易分布总览'),
      searchPlaceholder: t('搜索 交易对象、昵称、是否员工、大区、道具ID、道具名称、交易总额、交易单价、交易数量、交易次数'),
      searchFields: tradeSearchFields,
      table: {
        columns: dealDetailColumns,
        data: filterDataByConditions(dealDetailList.value, tabSearchConditions.value.trade, tradeSearchFields),
        pagination: tradePagination.value,
        title: t('交易明细'),
      },
    },
    {
      key: 'coin',
      label: t('代币发放记录'),
      chartRows: sapChartRows.value,
      chartTitle: t('发放分布总览'),
      chartColumns: 3,
      searchPlaceholder: t('搜索 发放人、大区、发放数量、发放金额、操作原因、需求类型、需求来源'),
      searchFields: coinSearchFields,
      table: {
        columns: sapDetailColumns,
        data: filterDataByConditions(sapDetailList.value, tabSearchConditions.value.coin, coinSearchFields),
        pagination: coinPagination.value,
        title: t('发放明细'),
      },
    },
    {
      key: 'chat',
      label: t('聊天记录'),
      chartRows: [],
      searchPlaceholder: t('搜索 发起方、接收方openid、接收方昵称、聊天内容、大区、是否员工、信息类型'),
      searchFields: chatSearchFields,
      table: {
        columns: chatDetailColumns,
        data: filterDataByConditions(chatDetailList.value, tabSearchConditions.value.chat, chatSearchFields),
        pagination: chatPagination.value,
        title: t('聊天明细'),
      },
      extraFilter: 'chatViolation',
      showChart: false,
    },
  ]);

  // 判断某个概览 section 是否为空
  const isSectionEmpty = (sectionKey: string): boolean => {
    switch (sectionKey) {
    case 'role':
      return roleList.value.length === 0;
    case 'login':
      return loginStatList.value.length === 0
        && Object.keys(lastLoginRecord.value).length === 0;
    case 'gift':
      return Object.keys(lastGiveRecord.value).length === 0;
    case 'trade':
      return Object.keys(lastDealRecord.value).length === 0;
    case 'coin':
      return Object.keys(lastSapRecord.value).length === 0;
    case 'chat':
      return Object.keys(lastChatRecord.value).length === 0;
    default:
      return false;
    }
  };

  // 搜索条件变化处理
  const handleTabSearchConditionChange = (tabKey: string, conditions: any[]) => {
    tabSearchConditions.value[tabKey] = conditions;
  };

  // 监听 tab 切换：按需加载明细数据
  watch(activeTab, (newTab) => {
    if (newTab !== 'overview') {
      loadTabData(newTab);
    }
  });

  // 监听疑似违规 checkbox 变化，重新查询聊天数据
  watch(chatSuspectedViolation, () => {
    tabDataLoaded.value.chat = false;
    fetchChatData().then(() => {
      tabDataLoaded.value.chat = true;
    });
  });

  // 初始化：加载概览数据
  watch(
    () => [props.toolUid, props.gameData.openid],
    ([uid, openid]) => {
      if (uid && openid) {
        // 重置已加载标记
        tabDataLoaded.value = {};
        fetchOverviewData();
        // 如果初始 tab 不是概览，也加载对应 tab 数据
        if (activeTab.value !== 'overview') {
          loadTabData(activeTab.value);
        }
      }
    },
    { immediate: true },
  );

  // ========== 导出功能 ==========
  const exportPopoverRef = ref();
  const isExportPopoverShow = ref(false);
  const isExporting = ref(false);

  // 导出时间范围快捷选项
  interface ExportShortcut {
    text: string;
    value: () => [Date, Date];
  }
  const exportDateShortcuts: ExportShortcut[] = [
    {
      text: t('最近一周'),
      value: () => {
        const end = new Date();
        const start = new Date();
        start.setDate(start.getDate() - 7);
        return [start, end];
      },
    },
    {
      text: t('最近一个月'),
      value: () => {
        const end = new Date();
        const start = new Date();
        start.setMonth(start.getMonth() - 1);
        return [start, end];
      },
    },
    {
      text: t('最近三个月'),
      value: () => {
        const end = new Date();
        const start = new Date();
        start.setMonth(start.getMonth() - 3);
        return [start, end];
      },
    },
    {
      text: t('最近半年'),
      value: () => {
        const end = new Date();
        const start = new Date();
        start.setMonth(start.getMonth() - 6);
        return [start, end];
      },
    },
    {
      text: t('最近一年'),
      value: () => {
        const end = new Date();
        const start = new Date();
        start.setFullYear(start.getFullYear() - 1);
        return [start, end];
      },
    },
  ];
  // 默认选中“最近半年”（index = 3）
  const exportShortcutSelectedIndex = ref(3);
  const exportDateRange = ref<[Date, Date]>(exportDateShortcuts[3].value());

  // 导出内容选项（用户信息、游戏角色为必选项，禁用不可取消）
  const exportContentOptions = [
    { id: 'userInfo', name: t('用户信息'), disabled: true },
    { id: 'gameRole', name: t('游戏角色'), disabled: true },
    { id: 'login', name: t('登录记录'), disabled: false },
    { id: 'gift', name: t('赠送记录'), disabled: false },
    { id: 'trade', name: t('交易记录'), disabled: false },
    { id: 'coin', name: t('代币发放记录'), disabled: false },
    { id: 'chat', name: t('聊天记录'), disabled: false },
  ];
  // 默认全选
  const exportContentChecked = ref<string[]>(exportContentOptions.map(item => item.id));

  // 导出弹窗：手动控制关闭（点击外部关闭，但排除日期选择器面板）
  const handleDocumentClickForExport = (e: MouseEvent) => {
    if (!isExportPopoverShow.value) return;
    const target = e.target as HTMLElement;
    if (!target) return;
    // 点击在日期选择器下拉面板内部——不关闭
    const datePickerDropdowns = document.querySelectorAll('.bk-date-picker-dropdown');
    for (const dropdown of Array.from(datePickerDropdowns)) {
      if (dropdown.contains(target)) return;
    }
    // 点击在导出弹窗内容区或触发按钮内部——不关闭（已通过 @click.stop 拦截）
    const popoverContents = document.querySelectorAll('.export-popover-wrapper');
    for (const content of Array.from(popoverContents)) {
      if (content.contains(target)) return;
    }
    // 其他区域 —— 关闭
    isExportPopoverShow.value = false;
  };

  onMounted(() => {
    document.addEventListener('click', handleDocumentClickForExport, true);
  });
  onBeforeUnmount(() => {
    document.removeEventListener('click', handleDocumentClickForExport, true);
  });

  // 导出逻辑
  const handleExport = async () => {
    if (!exportDateRange.value || exportDateRange.value.length < 2) return;
    if (exportContentChecked.value.length === 0) return;

    isExporting.value = true;
    try {
      const [startDate, endDate] = exportDateRange.value as [Date, Date];
      const startYmd = formatYmd(new Date(startDate as unknown as string | number | Date));
      const endYmd = formatYmd(new Date(endDate as unknown as string | number | Date));

      const baseParams = {
        selected_gameid: props.gameData.gameid,
        selected_openid: props.gameData.openid,
      };

      const wb = XLSX.utils.book_new();

      // 用户信息 sheet
      if (exportContentChecked.value.includes('userInfo')) {
        const userInfoData = [{
          [EXPORT_USER_FIELDS.GAME_NAME]: props.gameData.name,
          [EXPORT_USER_FIELDS.OPENID]: props.gameData.openid,
          [EXPORT_USER_FIELDS.WECHAT]: props.gameData.wechat,
          [EXPORT_USER_FIELDS.COIN_BALANCE]: props.gameData.coinBalance,
          [EXPORT_USER_FIELDS.TOTAL_RECHARGE]: props.gameData.totalRecharge,
          [EXPORT_USER_FIELDS.TOTAL_GIFT]: props.gameData.totalGift,
          [EXPORT_USER_FIELDS.TOTAL_ISSUE]: props.gameData.totalIssue,
        }];
        const userHeaders = [
          EXPORT_USER_FIELDS.GAME_NAME, EXPORT_USER_FIELDS.OPENID, EXPORT_USER_FIELDS.WECHAT,
          EXPORT_USER_FIELDS.COIN_BALANCE, EXPORT_USER_FIELDS.TOTAL_RECHARGE,
          EXPORT_USER_FIELDS.TOTAL_GIFT, EXPORT_USER_FIELDS.TOTAL_ISSUE,
        ];
        useExportExcel.exportExcelSheet(wb, userInfoData, t('用户信息'), userHeaders, userHeaders);
      }

      // 游戏角色 sheet
      // 注：与明细 tab 默认"最近半年"保持一致，避免概览查不到数据但明细有数据的不一致情况
      // 后端字段名 one_month_ago_Ymd_dashed 不变，仅将值改为半年前日期
      if (exportContentChecked.value.includes('gameRole')) {
        const dp = getDateParams();
        const roleParams = {
          one_month_ago_Ymd_dashed: dp.six_month_ago_Ymd_dashed,
          one_year_ago_Ymd: dp.one_year_ago_Ymd,
          ...baseParams,
        };
        const [loginRes, chatRes, dealRes] = await Promise.all([
          executeDataSource('overview_rolelogin_stats', roleParams),
          executeDataSource('overview_rolechat_stats', roleParams),
          executeDataSource('overview_roledeal_stats', roleParams),
        ]);
        const roleData = mergeRoleStats(extractResults(loginRes), extractResults(chatRes), extractResults(dealRes));
        const roleHeaders = roleColumns.map((col) => {
          const label = col.label();
          return label;
        });
        const roleKeys = roleColumns.map(col => col.field);
        useExportExcel.exportExcelSheet(wb, roleData, t('游戏角色'), roleHeaders, roleKeys);
      }

      // 登录记录 sheet
      if (exportContentChecked.value.includes('login')) {
        const res = await executeDataSource('login_detail_list', {
          detail_startdate_Ymd: startYmd,
          detail_enddate_Ymd: endYmd,
          ...baseParams,
        });
        const data = extractResults(res);
        const headers = loginDetailColumns.map(col => col.label());
        const keys = loginDetailColumns.map(col => col.field);
        useExportExcel.exportExcelSheet(wb, data, t('登录记录'), headers, keys);
      }

      // 赠送记录 sheet
      if (exportContentChecked.value.includes('gift')) {
        const res = await executeDataSource('give_detail_list', {
          detail_startdate_Ymd: startYmd,
          detail_enddate_Ymd: endYmd,
          ...baseParams,
        });
        const data = extractResults(res);
        const headers = giveDetailColumns.map(col => col.label());
        const keys = giveDetailColumns.map(col => col.field);
        useExportExcel.exportExcelSheet(wb, data, t('赠送记录'), headers, keys);
      }

      // 交易记录 sheet
      if (exportContentChecked.value.includes('trade')) {
        const res = await executeDataSource('deal_detail_list', {
          detail_startdate_Ymd: startYmd,
          detail_enddate_Ymd: endYmd,
          ...baseParams,
        });
        const data = extractResults(res);
        const headers = dealDetailColumns.map(col => col.label());
        const keys = dealDetailColumns.map(col => col.field);
        useExportExcel.exportExcelSheet(wb, data, t('交易记录'), headers, keys);
      }

      // 代币发放记录 sheet
      if (exportContentChecked.value.includes('coin')) {
        const res = await executeDataSource('sap_detail_list', {
          detail_startdate_Ymd: startYmd,
          detail_enddate_Ymd: endYmd,
          ...baseParams,
        });
        // 后端返回的「发放时间」为 ISO 8601 UTC 格式（如 2026-04-29T08:09:09Z），
        // 导出前转换为本地时间字符串，与表格展示保持一致
        const data = extractResults(res).map(row => ({
          ...row,
          [COIN_DETAIL_FIELDS.ISSUE_TIME]: formatIsoDateTime(row?.[COIN_DETAIL_FIELDS.ISSUE_TIME]),
        }));
        const headers = sapDetailColumns.map(col => col.label());
        const keys = sapDetailColumns.map(col => col.field);
        useExportExcel.exportExcelSheet(wb, data, t('代币发放记录'), headers, keys);
      }

      // 聊天记录 sheet
      if (exportContentChecked.value.includes('chat')) {
        const res = await executeDataSource('chat_detail_list', {
          detail_startdate_Ymd: startYmd,
          detail_enddate_Ymd: endYmd,
          is_sensitive: ['0', '1'],
          ...baseParams,
        });
        const data = extractResults(res);
        const headers = chatDetailColumns.map(col => col.label());
        const keys = chatDetailColumns.map(col => col.field);
        useExportExcel.exportExcelSheet(wb, data, t('聊天记录'), headers, keys);
      }

      // 设置列宽自适应 & 表头自动筛选
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

      // 导出文件，文件名格式：企业微信名_表格名_日期_时分秒
      const now = new Date();
      const dateStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
      const timeStr = `${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}${String(now.getSeconds()).padStart(2, '0')}`;
      const userName = props.gameData.ctx || '';
      const sheetName = props.gameData.name || t('游戏审计数据');
      const fileName = userName ? `${userName}_${sheetName}_${dateStr}_${timeStr}` : `${sheetName}_${dateStr}_${timeStr}`;
      XLSX.writeFile(wb, `${fileName}.xlsx`);

      isExportPopoverShow.value = false;
    } finally {
      isExporting.value = false;
    }
  };
</script>

<style scoped lang="postcss">

/* 游戏基本信息头部 */
.game-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: #f0f5ff;
  border: 1px solid #d4e4ff;
  border-radius: 2px;

  .game-info-row {
    display: flex;
    flex: 1;
    flex-wrap: wrap;
    min-width: 0;
    margin-right: 24px;
    gap: 16px clamp(32px, 6vw, 116px);
  }

  .info-item {
    display: flex;
    flex-direction: column;
    gap: 4px;

    .info-label {
      font-size: 12px;
      line-height: 20px;
      color: #979ba5;
    }

    .info-value {
      display: flex;
      font-size: 14px;
      line-height: 22px;
      color: #313238;
      align-items: center;
      gap: 4px;
    }

    .info-unit {
      font-weight: 700;
    }
  }

  .copy-icon,
  .eye-icon {
    font-size: 14px;
    color: #979ba5;
    cursor: pointer;

    &:hover {
      color: #3a84ff;
    }
  }

  .export-btn {
    flex-shrink: 0;
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

/* Tab 标签页 */
.game-tabs {
  margin-top: 4px;
}

.game-tabs :deep(.bk-tab),
.game-tabs :deep(.bk-tab-header),
.game-tabs :deep(.bk-tab-header-nav) {
  overflow: visible !important;
}

/* 在 nav 容器顶部留出 12px 空间用于阴影展示（nav 是阴影直接的父容器，最关键的一层） */
.game-tabs :deep(.bk-tab-header-nav) {
  padding-top: 12px;
}

.game-tabs :deep(.bk-tab-header-item.bk-tab-header--active) {
  position: relative;
  z-index: 2;
  box-shadow: /* 上方阴影：柔和淡灰色光晕 */
    0 -4px 10px -2px rgb(0 0 0 / 8%),
    /* 右侧阴影：与右侧相邻 tab 形成轻微层次 */
    3px 0 8px -3px rgb(0 0 0 / 8%) !important;
}

/* 概览内容 */
.overview-content {
  padding-top: 16px;
}

/* section 加载占位 */
.section-skeleton {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 50px;
}

/* section 无数据提示 */
.section-empty {
  display: flex;
  align-items: center;
  max-height: 50px;

  .section-empty-text {
    font-size: 12px;
    color: #979ba5;
  }
}

.section {
  padding: 16px;
  margin-bottom: 16px;
  background: #fff;
  border-radius: 2px;
}

.section-title {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 700;
  line-height: 22px;
  color: #313238;
}

.section-title-row {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  margin-bottom: 12px;

  .section-title {
    margin-bottom: 0;
  }
}

.view-detail-link {
  display: flex;
  margin-left: 20px;
  font-size: 12px;
  color: #3a84ff;
  cursor: pointer;
  align-items: center;
  gap: 4px;

  &:hover {
    color: #1768ef;
  }

  .view-detail-icon {
    width: 14px;
    height: 14px;
  }
}

.last-record-row {
  display: flex;
  flex-wrap: wrap;
  gap: 80px;
  margin-bottom: 12px;
  font-size: 14px;
  line-height: 22px;

  .record-item {
    display: flex;
    align-items: center;
  }

  .record-label {
    color: #979ba5;
    white-space: nowrap;
  }

  .record-value {
    color: #313238;
  }
}

.suspected-violation-checkbox {
  flex-shrink: 0;
}
</style>

<!-- 全局样式：提升日期选择器下拉面板的 z-index，避免被导出 popover 遮挡 -->
<style lang="postcss">
  /* 日期选择器下拉面板 z-index 必须高于导出 popover（bk-popover 默认在 2000-3000 段），
     设置一个足够高的值以确保不会被遮挡 */
  .bk-date-picker-dropdown,
  .bk-date-picker-dropdown.bk-picker-dropdown {
    z-index: 99999 !important;
  }

  /* 导出弹窗内的日期选择器，进一步保证其触发的下拉面板不被同级 popover 遮挡 */
  .export-popover-wrapper ~ .bk-date-picker-dropdown,
  body > .bk-date-picker-dropdown {
    z-index: 99999 !important;
  }

  /* 导出弹窗：消除 bk-popover 默认的 12px padding（仅作用于当前导出弹窗，不影响其他 popover） */
  .bk-popover.bk-pop2-content.export-popover-wrapper {
    padding: 0 !important;
  }
</style>
