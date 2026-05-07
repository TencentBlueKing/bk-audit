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
          <span class="info-label">{{ t('微信') }}</span>
          <span class="info-value">
            {{ isWechatVisible ? gameData.wechat : '******' }}
            <audit-icon
              class="eye-icon"
              :type="isWechatVisible ? 'view' : 'unview'"
              @click="isWechatVisible = !isWechatVisible" />
          </span>
        </div>
        <div class="info-item">
          <span class="info-label">{{ t('代币存量') }}</span>
          <span class="info-value">{{ t('代') }} {{ gameData.coinBalance }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">{{ t('累计充值') }}</span>
          <span class="info-value">{{ t('代') }} {{ gameData.totalRecharge }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">{{ t('累计赠送') }}</span>
          <span class="info-value">¥ {{ gameData.totalGift }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">{{ t('累计发放') }}</span>
          <span class="info-value">¥ {{ gameData.totalIssue }}</span>
        </div>
      </div>
      <bk-popover
        ref="exportPopoverRef"
        :is-show="isExportPopoverShow"
        placement="bottom-end"
        theme="light"
        trigger="click"
        :width="340"
        @after-hidden="isExportPopoverShow = false">
        <bk-button
          class="export-btn"
          @click="isExportPopoverShow = !isExportPopoverShow">
          <audit-icon
            style="margin-right: 4px;"
            type="download" />
          {{ t('导出') }}
        </bk-button>
        <template #content>
          <div class="export-popover-content">
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
                :placeholder="t('选择时间范围')"
                style="width: 100%"
                type="daterange" />
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
          <!-- 概览内容 -->
          <bk-loading
            class="tab-loading-wrapper"
            :loading="overviewLoading">
            <!-- loading时的占位元素，擑开容器高度使loading居中 -->
            <div
              v-if="overviewLoading"
              class="loading-placeholder" />
            <bk-exception
              v-if="!overviewLoading && isOverviewEmpty"
              class="tab-empty"
              type="empty">
              {{ t('暂无数据') }}
            </bk-exception>
            <div
              v-else-if="!overviewLoading"
              class="overview-content">
              <div
                v-for="section in overviewSections"
                :key="section.key"
                class="section">
                <!-- 标题行 -->
                <div
                  v-if="section.tabKey"
                  class="section-title-row">
                  <span class="section-title">{{ section.title }}</span>
                  <span
                    class="view-detail-link"
                    @click="activeTab = section.tabKey">
                    {{ t('查看详情') }}
                    <audit-icon type="jump-link" />
                  </span>
                </div>
                <div
                  v-else
                  class="section-title">
                  {{ section.title }}
                </div>

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
              </div>
            </div>
          </bk-loading>
        </bk-tab-panel>

        <bk-tab-panel
          v-for="tab in recordTabs"
          :key="tab.key"
          :label="tab.label"
          :name="tab.key">
          <bk-loading
            class="tab-loading-wrapper"
            :loading="tabLoadingMap[tab.key]">
            <!-- loading时的占位元素，擑开容器高度使loading居中 -->
            <div
              v-if="tabLoadingMap[tab.key]"
              class="loading-placeholder" />
            <bk-exception
              v-if="!tabLoadingMap[tab.key] && isTabEmpty(tab.key)"
              class="tab-empty"
              type="empty">
              {{ t('暂无数据') }}
            </bk-exception>
            <game-record-tab
              v-else-if="!tabLoadingMap[tab.key]"
              :chart-rows="tab.chartRows"
              :search-fields="tab.searchFields"
              :search-placeholder="tab.searchPlaceholder"
              :table-columns="tab.table.columns"
              :table-data="tab.table.data"
              :table-pagination="tab.table.pagination"
              :table-title="tab.table.title"
              @date-change="handleTabDateChange(tab.key, $event)"
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
          </bk-loading>
        </bk-tab-panel>
      </bk-tab>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import * as XLSX from 'xlsx';

  import ToolManageService from '@service/tool-manage';

  import useExportExcel from '@hooks/use_export_excel';

  import { execCopy } from '@utils/assist';

  import {
    CHART_FIELDS,
    CHAT_DETAIL_FIELDS,
    COIN_DETAIL_FIELDS,
    EXPORT_USER_FIELDS,
    GIFT_DETAIL_FIELDS,
    LOGIN_DETAIL_FIELDS,
    ROLE_FIELDS,
    TRADE_DETAIL_FIELDS,
  } from './game-field-keys';
  import GameRecordTab from './game-record-tab.vue';
  import { type SearchFieldItem, useGameSearchFields } from './game-search-fields';
  import { useGameTableColumns } from './game-table-columns';
  import RecordDetailTable from './record-detail-table.vue';

  // Tab 配置接口
  interface ChartConfig {
    title: string;
    data: Array<{ name: string; value: number }>;
    total: number;
    centerLabel: string;
  }

  interface GameRecordTabConfig {
    key: string;
    label: string;
    chartRows: ChartConfig[][];
    searchPlaceholder: string;
    searchFields: SearchFieldItem[];
    table: {
      columns: Array<Record<string, any>>;
      data: Array<Record<string, any>>;
      pagination: { count: number; current: number; limit: number };
      title: string;
    };
    extraFilter?: 'chatViolation';
  }

  interface GameData {
    name: string;
    openid: string;
    gameid: string | number;
    wechat: string;
    coinBalance: number;
    totalRecharge: number;
    totalGift: number;
    totalIssue: number;
  }

  interface Props {
    gameData?: GameData;
    initialTab?: string;
    toolUid?: string;
    toolName?: string;
  }

  const props = withDefaults(defineProps<Props>(), {
    gameData: () => ({
      name: '',
      openid: '',
      gameid: '',
      wechat: '',
      coinBalance: 0,
      totalRecharge: 0,
      totalGift: 0,
      totalIssue: 0,
    }),
    initialTab: '',
    toolUid: '',
    toolName: '',
  });

  const { t } = useI18n();
  const activeTab = ref(props.initialTab || 'overview');

  // 当 initialTab 变化时同步切换 tab
  watch(() => props.initialTab, (newTab) => {
    if (newTab) {
      activeTab.value = newTab;
    }
  });

  // ========== 日期工具函数 ==========
  const formatYmd = (d: Date): string => {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}${m}${day}`;
  };

  const formatYmdDashed = (d: Date): string => {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  };

  const getDateParams = () => {
    const now = new Date();
    const oneMonthAgo = new Date(now);
    oneMonthAgo.setMonth(oneMonthAgo.getMonth() - 1);
    const oneWeekAgo = new Date(now);
    oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
    const twoWeekAgo = new Date(now);
    twoWeekAgo.setDate(twoWeekAgo.getDate() - 14);
    const oneYearAgo = new Date(now);
    oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);

    return {
      one_month_ago_Ymd: formatYmd(oneMonthAgo),
      one_month_ago_Ymd_dashed: formatYmdDashed(oneMonthAgo),
      one_week_ago_Ymd_dashed: formatYmdDashed(oneWeekAgo),
      two_week_ago_Ymd_dashed: formatYmdDashed(twoWeekAgo),
      one_year_ago_Ymd: formatYmd(oneYearAgo),
      last_record_thedate_Ymd: formatYmd(oneMonthAgo),
      today_Ymd: formatYmd(now),
    };
  };

  // 明细 Tab 的日期范围（默认最近一个月）
  const detailDateRange = ref<Record<string, { start: string; end: string }>>({
    login: { start: '', end: '' },
    gift: { start: '', end: '' },
    trade: { start: '', end: '' },
    coin: { start: '', end: '' },
    chat: { start: '', end: '' },
  });

  const initDateRange = () => {
    const dp = getDateParams();
    const defaultRange = { start: dp.one_month_ago_Ymd, end: dp.today_Ymd };
    detailDateRange.value = {
      login: { ...defaultRange },
      gift: { ...defaultRange },
      trade: { ...defaultRange },
      coin: { ...defaultRange },
      chat: { ...defaultRange },
    };
  };
  initDateRange();

  // 提取接口返回的 results 数组
  const extractResults = (data: any): any[] => {
    const results = data?.data?.result?.results
      || data?.result?.results || data?.data?.results || data?.results;
    return Array.isArray(results) ? results : [];
  };

  // 通用接口调用封装
  const executeDataSource = (dataSourceName: string, params: Record<string, any>) => {
    if (!props.toolUid) return Promise.resolve(null);
    return ToolManageService.fetchToolsExecute({
      uid: props.toolUid,
      params: {
        data_source_name: dataSourceName,
        params,
      },
    });
  };

  // 微信号显示/隐藏
  const isWechatVisible = ref(false);

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

  // ========== 概览 - 角色总览 ==========
  const roleList = ref<Array<Record<string, any>>>([]);

  // 合并三个角色统计接口的数据（按角色ID合并）
  const mergeRoleStats = (loginData: any[], chatData: any[], dealData: any[]) => {
    const roleMap = new Map<string, Record<string, any>>();
    // 先用 login 数据建立基础
    loginData.forEach((row) => {
      const id = row[ROLE_FIELDS.ROLE_ID] || row.roleId || '';
      roleMap.set(id, { ...row });
    });
    // 合并 chat 数据
    chatData.forEach((row) => {
      const id = row[ROLE_FIELDS.ROLE_ID] || row.roleId || '';
      const existing = roleMap.get(id) || { [ROLE_FIELDS.ROLE_ID]: id };
      roleMap.set(id, {
        ...existing,
        [ROLE_FIELDS.CHAT_TARGET_MONTH]: row[ROLE_FIELDS.CHAT_TARGET_MONTH] ?? 0,
        [ROLE_FIELDS.CHAT_TARGET_YEAR]: row[ROLE_FIELDS.CHAT_TARGET_YEAR] ?? 0,
        [ROLE_FIELDS.CHAT_COUNT_MONTH]: row[ROLE_FIELDS.CHAT_COUNT_MONTH] ?? 0,
        [ROLE_FIELDS.CHAT_COUNT_YEAR]: row[ROLE_FIELDS.CHAT_COUNT_YEAR] ?? 0,
      });
    });
    // 合并 deal 数据
    dealData.forEach((row) => {
      const id = row[ROLE_FIELDS.ROLE_ID] || row.roleId || '';
      const existing = roleMap.get(id) || { [ROLE_FIELDS.ROLE_ID]: id };
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

  // ========== 概览 - 登录统计 ==========
  const loginStatList = ref<Array<Record<string, any>>>([]);

  // ========== 概览 - 最近记录 ==========
  const lastLoginRecord = ref<Record<string, any>>({});
  const lastGiveRecord = ref<Record<string, any>>({});
  const lastDealRecord = ref<Record<string, any>>({});
  const lastSapRecord = ref<Record<string, any>>({});
  const lastChatRecord = ref<Record<string, any>>({});

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
        { label: t('最近一次赠送时间'), value: lastGiveRecord.value[GIFT_DETAIL_FIELDS.GIFT_TIME] || '--' },
        { label: t('赠送账号'), value: lastGiveRecord.value[GIFT_DETAIL_FIELDS.GIFT_TARGET] || lastGiveRecord.value[GIFT_DETAIL_FIELDS.TARGET_OPENID] || '--' },
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
        { label: t('赠送总额'), value: lastDealRecord.value[TRADE_DETAIL_FIELDS.TRADE_TOTAL] ? `${lastDealRecord.value[TRADE_DETAIL_FIELDS.TRADE_TOTAL]} 元` : '--' },
      ],
    },
    {
      key: 'coin',
      title: t('代币发放记录'),
      tabKey: 'coin',
      lastRecordItems: [
        { label: t('最近一次发放时间'), value: lastSapRecord.value[COIN_DETAIL_FIELDS.ISSUE_TIME] || '--' },
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

  // ========== 登录记录 tab ==========
  const loginGroupStats = ref<Array<Record<string, any>>>([]);
  const loginDetailList = ref<Array<Record<string, any>>>([]);
  const loginPagination = ref({ count: 0, current: 1, limit: 10 });

  // 将 groupdim_stats 数据按"分组"拆分为饼图数据
  const buildChartFromGroupStats = (data: any[], groupName: string, valueField: string) => data
    .filter(row => row[CHART_FIELDS.GROUP] === groupName)
    .map(row => ({ name: row[CHART_FIELDS.DIMENSION] || '', value: Number(row[valueField]) || 0 }));

  const loginChartRows = computed<ChartConfig[][]>(() => {
    const stats = loginGroupStats.value;
    if (stats.length === 0) return [];
    const deviceData = buildChartFromGroupStats(stats, CHART_FIELDS.LOGIN_DEVICE, CHART_FIELDS.LOGIN_TOTAL);
    const locationData = buildChartFromGroupStats(stats, CHART_FIELDS.LOGIN_LOCATION, CHART_FIELDS.LOGIN_TOTAL);
    const timeData = buildChartFromGroupStats(stats, CHART_FIELDS.LOGIN_TIME_PERIOD, CHART_FIELDS.LOGIN_TOTAL);
    const total = stats.reduce((sum, row) => sum + (Number(row[CHART_FIELDS.LOGIN_TOTAL]) || 0), 0);
    const charts: ChartConfig[] = [];
    if (deviceData.length > 0) charts.push({ title: t('登录设备分布'), data: deviceData, total, centerLabel: t('登录总数') });
    if (locationData.length > 0) charts.push({ title: t('登录地点分布'), data: locationData, total, centerLabel: t('登录总数') });
    if (timeData.length > 0) charts.push({ title: t('登录时段分布'), data: timeData, total, centerLabel: t('登录总数') });
    return charts.length > 0 ? [charts] : [];
  });

  // ========== 赠送记录 tab ==========
  const giveGroupStats = ref<Array<Record<string, any>>>([]);
  const giveDetailList = ref<Array<Record<string, any>>>([]);
  const giftPagination = ref({ count: 0, current: 1, limit: 10 });

  const giveChartRows = computed<ChartConfig[][]>(() => {
    const stats = giveGroupStats.value;
    if (stats.length === 0) return [];
    // 赠送分布：按金额和次数
    const targetAmountData = buildChartFromGroupStats(stats, CHART_FIELDS.GIFT_TARGET, CHART_FIELDS.GIFT_AMOUNT_YUAN);
    const targetCountData = buildChartFromGroupStats(stats, CHART_FIELDS.GIFT_TARGET, CHART_FIELDS.TIMES);
    const itemAmountData = buildChartFromGroupStats(stats, CHART_FIELDS.GIFT_ITEM, CHART_FIELDS.GIFT_AMOUNT_YUAN);
    const itemCountData = buildChartFromGroupStats(stats, CHART_FIELDS.GIFT_ITEM, CHART_FIELDS.TIMES);
    const rows: ChartConfig[][] = [];
    const row1: ChartConfig[] = [];
    if (targetAmountData.length > 0) {
      const total = targetAmountData.reduce((s, d) => s + d.value, 0);
      row1.push({ title: t('赠送对象分布（按金额）'), data: targetAmountData, total, centerLabel: t('总额（元）') });
    }
    if (targetCountData.length > 0) {
      const total = targetCountData.reduce((s, d) => s + d.value, 0);
      row1.push({ title: t('赠送对象分布（按次数）'), data: targetCountData, total, centerLabel: t('总次数') });
    }
    if (row1.length > 0) rows.push(row1);
    const row2: ChartConfig[] = [];
    if (itemAmountData.length > 0) {
      const total = itemAmountData.reduce((s, d) => s + d.value, 0);
      row2.push({ title: t('赠送道具分布（按金额）'), data: itemAmountData, total, centerLabel: t('总额（元）') });
    }
    if (itemCountData.length > 0) {
      const total = itemCountData.reduce((s, d) => s + d.value, 0);
      row2.push({ title: t('赠送道具分布（按次数）'), data: itemCountData, total, centerLabel: t('总次数') });
    }
    if (row2.length > 0) rows.push(row2);
    return rows;
  });

  // ========== 交易记录 tab ==========
  const dealGroupStats = ref<Array<Record<string, any>>>([]);
  const dealDetailList = ref<Array<Record<string, any>>>([]);
  const tradePagination = ref({ count: 0, current: 1, limit: 10 });

  const dealChartRows = computed<ChartConfig[][]>(() => {
    const stats = dealGroupStats.value;
    if (stats.length === 0) return [];
    const targetAmountData = buildChartFromGroupStats(stats, CHART_FIELDS.TRADE_TARGET, CHART_FIELDS.ISSUE_AMOUNT_YUAN);
    const targetCountData = buildChartFromGroupStats(stats, CHART_FIELDS.TRADE_TARGET, CHART_FIELDS.TIMES);
    const itemAmountData = buildChartFromGroupStats(stats, CHART_FIELDS.TRADE_ITEM, CHART_FIELDS.ISSUE_AMOUNT_YUAN);
    const itemCountData = buildChartFromGroupStats(stats, CHART_FIELDS.TRADE_ITEM, CHART_FIELDS.TIMES);
    const rows: ChartConfig[][] = [];
    const row1: ChartConfig[] = [];
    if (targetAmountData.length > 0) {
      const total = targetAmountData.reduce((s, d) => s + d.value, 0);
      row1.push({ title: t('交易对象分布（按金额）'), data: targetAmountData, total, centerLabel: t('总额（元）') });
    }
    if (targetCountData.length > 0) {
      const total = targetCountData.reduce((s, d) => s + d.value, 0);
      row1.push({ title: t('交易对象分布（按次数）'), data: targetCountData, total, centerLabel: t('总次数') });
    }
    if (row1.length > 0) rows.push(row1);
    const row2: ChartConfig[] = [];
    if (itemAmountData.length > 0) {
      const total = itemAmountData.reduce((s, d) => s + d.value, 0);
      row2.push({ title: t('交易道具分布（按金额）'), data: itemAmountData, total, centerLabel: t('总额（元）') });
    }
    if (itemCountData.length > 0) {
      const total = itemCountData.reduce((s, d) => s + d.value, 0);
      row2.push({ title: t('交易道具分布（按次数）'), data: itemCountData, total, centerLabel: t('总次数') });
    }
    if (row2.length > 0) rows.push(row2);
    return rows;
  });

  // ========== 发放记录 tab ==========
  const sapGroupStats = ref<Array<Record<string, any>>>([]);
  const sapDetailList = ref<Array<Record<string, any>>>([]);
  const coinPagination = ref({ count: 0, current: 1, limit: 10 });

  const sapChartRows = computed<ChartConfig[][]>(() => {
    const stats = sapGroupStats.value;
    if (stats.length === 0) return [];
    const demandTypeData = buildChartFromGroupStats(stats, CHART_FIELDS.DEMAND_TYPE, CHART_FIELDS.ISSUE_AMOUNT_YUAN);
    const issuerData = buildChartFromGroupStats(stats, CHART_FIELDS.ISSUER, CHART_FIELDS.ISSUE_AMOUNT_YUAN);
    const sourceData = buildChartFromGroupStats(stats, CHART_FIELDS.DEMAND_SOURCE, CHART_FIELDS.ISSUE_AMOUNT_YUAN);
    const total = stats.reduce((sum, row) => sum + (Number(row[CHART_FIELDS.ISSUE_AMOUNT_YUAN]) || 0), 0);
    const charts: ChartConfig[] = [];
    if (demandTypeData.length > 0) charts.push({ title: t('需求类型分布'), data: demandTypeData, total, centerLabel: t('总金额（元）') });
    if (issuerData.length > 0) charts.push({ title: t('发放人分布'), data: issuerData, total, centerLabel: t('总金额（元）') });
    if (sourceData.length > 0) charts.push({ title: t('需求来源分布'), data: sourceData, total, centerLabel: t('总金额（元）') });
    return charts.length > 0 ? [charts] : [];
  });

  // ========== 聊天记录 tab ==========
  const chatSuspectedViolation = ref(false);
  const chatDetailList = ref<Array<Record<string, any>>>([]);
  const chatPagination = ref({ count: 0, current: 1, limit: 10 });

  // ========== 各 Tab 搜索条件缓存 ==========
  const tabSearchConditions = ref<Record<string, any[]>>({
    login: [],
    gift: [],
    trade: [],
    coin: [],
    chat: [],
  });

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
      const cellValue = String(row[dataKey] ?? '');
      const cellValueLower = cellValue.toLowerCase();

      // 支持逗号分隔多值（中英文逗号均支持）
      const searchValues = searchValue.split(/[,，]/).map((s: string) => s.trim())
        .filter(Boolean);

      switch (operator) {
      case 'eq': // 等于（多值时任一匹配即可）
        return searchValues.some((sv: string) => cellValue === sv);
      case 'neq': // 不等于（多值时全部不等才通过）
        return searchValues.every((sv: string) => cellValue !== sv);
      case 'gt': // 大于
        return Number(cellValue) > Number(searchValue);
      case 'lt': // 小于
        return Number(cellValue) < Number(searchValue);
      case 'gte': // 大于等于
        return Number(cellValue) >= Number(searchValue);
      case 'lte': // 小于等于
        return Number(cellValue) <= Number(searchValue);
      case 'in': // IN（逗号分隔多值）
        return searchValues.some((sv: string) => sv.toLowerCase() === cellValueLower);
      case 'not_in': // NOT IN（逗号分隔多值）
        return searchValues.every((sv: string) => sv.toLowerCase() !== cellValueLower);
      case 'like': // 包含（默认，多值时任一包含即可）
      default:
        return searchValues.some((sv: string) => cellValueLower.includes(sv.toLowerCase()));
      }
    }));
  };

  // ========== 统一 Tab 配置 ==========
  const recordTabs = computed<GameRecordTabConfig[]>(() => [
    {
      key: 'login',
      label: t('登录记录'),
      chartRows: loginChartRows.value,
      searchPlaceholder: t('搜索 登录地点、登录IP、大区ID、角色ID、角色名、等级、登录设备、机型'),
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
    },
  ]);

  // ========== 接口调用逻辑 ==========
  // 概览接口：加载角色总览（合并3个接口）
  const fetchOverviewRoleStats = async () => {
    const dp = getDateParams();
    const baseParams = {
      one_month_ago_Ymd_dashed: dp.one_month_ago_Ymd_dashed,
      one_year_ago_Ymd: dp.one_year_ago_Ymd,
      selected_gameid: props.gameData.gameid,
      selected_openid: props.gameData.openid,
    };
    const [loginRes, chatRes, dealRes] = await Promise.all([
      executeDataSource('overview_rolelogin_stats', baseParams),
      executeDataSource('overview_rolechat_stats', baseParams),
      executeDataSource('overview_roledeal_stats', baseParams),
    ]);
    const loginData = extractResults(loginRes);
    const chatData = extractResults(chatRes);
    const dealData = extractResults(dealRes);
    roleList.value = mergeRoleStats(loginData, chatData, dealData);
  };

  // 概览接口：加载登录统计
  const fetchOverviewLoginStats = async () => {
    const dp = getDateParams();
    const res = await executeDataSource('overview_login_stats', {
      one_month_ago_Ymd: dp.one_month_ago_Ymd,
      one_week_ago_Ymd_dashed: dp.one_week_ago_Ymd_dashed,
      two_week_ago_Ymd_dashed: dp.two_week_ago_Ymd_dashed,
      selected_gameid: props.gameData.gameid,
      selected_openid: props.gameData.openid,
    });
    loginStatList.value = extractResults(res);
  };

  // 概览接口：加载最近记录（5个接口并行）
  const fetchOverviewLastRecords = async () => {
    const dp = getDateParams();
    const baseParams = {
      last_record_thedate_Ymd: dp.last_record_thedate_Ymd,
      selected_gameid: props.gameData.gameid,
      selected_openid: props.gameData.openid,
    };
    const [loginRes, giveRes, dealRes, sapRes, chatRes] = await Promise.all([
      executeDataSource('overview_login_last', baseParams),
      executeDataSource('overview_give_last', baseParams),
      executeDataSource('overview_deal_last', baseParams),
      executeDataSource('overview_sap_last', baseParams),
      executeDataSource('overview_chat_last', baseParams),
    ]);
    const loginResults = extractResults(loginRes);
    const giveResults = extractResults(giveRes);
    const dealResults = extractResults(dealRes);
    const sapResults = extractResults(sapRes);
    const chatResults = extractResults(chatRes);
    lastLoginRecord.value = loginResults[0] || {};
    lastGiveRecord.value = giveResults[0] || {};
    lastDealRecord.value = dealResults[0] || {};
    lastSapRecord.value = sapResults[0] || {};
    lastChatRecord.value = chatResults[0] || {};
  };

  // 概览 loading 状态
  const overviewLoading = ref(false);

  // 概览是否为空（所有数据都没有）
  const isOverviewEmpty = computed(() => roleList.value.length === 0
    && loginStatList.value.length === 0
    && Object.keys(lastLoginRecord.value).length === 0
    && Object.keys(lastGiveRecord.value).length === 0
    && Object.keys(lastDealRecord.value).length === 0
    && Object.keys(lastSapRecord.value).length === 0
    && Object.keys(lastChatRecord.value).length === 0);

  // 各明细 Tab loading 状态
  const tabLoadingMap = ref<Record<string, boolean>>({
    login: false,
    gift: false,
    trade: false,
    coin: false,
    chat: false,
  });

  // 判断某个 Tab 是否为空
  const isTabEmpty = (tabKey: string): boolean => {
    switch (tabKey) {
    case 'login':
      return loginGroupStats.value.length === 0 && loginDetailList.value.length === 0;
    case 'gift':
      return giveGroupStats.value.length === 0 && giveDetailList.value.length === 0;
    case 'trade':
      return dealGroupStats.value.length === 0 && dealDetailList.value.length === 0;
    case 'coin':
      return sapGroupStats.value.length === 0 && sapDetailList.value.length === 0;
    case 'chat':
      return chatDetailList.value.length === 0;
    default:
      return false;
    }
  };

  // 加载所有概览数据
  const fetchOverviewData = async () => {
    if (!props.toolUid || !props.gameData.openid) return;
    overviewLoading.value = true;
    try {
      await Promise.all([
        fetchOverviewRoleStats(),
        fetchOverviewLoginStats(),
        fetchOverviewLastRecords(),
      ]);
    } finally {
      overviewLoading.value = false;
    }
  };

  // ========== 明细 Tab 接口调用 ==========
  // 登录记录
  const fetchLoginData = async () => {
    tabLoadingMap.value.login = true;
    try {
      const range = detailDateRange.value.login;
      const baseParams = {
        detail_startdate_Ymd: range.start,
        detail_enddate_Ymd: range.end,
        selected_gameid: props.gameData.gameid,
        selected_openid: props.gameData.openid,
      };
      const [groupRes, detailRes] = await Promise.all([
        executeDataSource('login_groupdim_stats', baseParams),
        executeDataSource('login_detail_list', baseParams),
      ]);
      loginGroupStats.value = extractResults(groupRes);
      loginDetailList.value = extractResults(detailRes);
      loginPagination.value.count = loginDetailList.value.length;
    } finally {
      tabLoadingMap.value.login = false;
    }
  };

  // 赠送记录
  const fetchGiveData = async () => {
    tabLoadingMap.value.gift = true;
    try {
      const dp = getDateParams();
      const range = detailDateRange.value.gift;
      const [groupRes, detailRes] = await Promise.all([
        executeDataSource('give_groupdim_stats', {
          detail_startdate_Ymd: range.start,
          detail_enddate_Ymd: range.end,
          selected_gameid: props.gameData.gameid,
          selected_openid: props.gameData.openid,
        }),
        executeDataSource('give_detail_list', {
          one_year_ago_Ymd: dp.one_year_ago_Ymd,
          selected_gameid: props.gameData.gameid,
          selected_openid: props.gameData.openid,
        }),
      ]);
      giveGroupStats.value = extractResults(groupRes);
      giveDetailList.value = extractResults(detailRes);
      giftPagination.value.count = giveDetailList.value.length;
    } finally {
      tabLoadingMap.value.gift = false;
    }
  };

  // 交易记录
  const fetchDealData = async () => {
    tabLoadingMap.value.trade = true;
    try {
      const range = detailDateRange.value.trade;
      const baseParams = {
        detail_startdate_Ymd: range.start,
        detail_enddate_Ymd: range.end,
        selected_gameid: props.gameData.gameid,
        selected_openid: props.gameData.openid,
      };
      const [groupRes, detailRes] = await Promise.all([
        executeDataSource('deal_groupdim_stats', baseParams),
        executeDataSource('deal_detail_list', baseParams),
      ]);
      dealGroupStats.value = extractResults(groupRes);
      dealDetailList.value = extractResults(detailRes);
      tradePagination.value.count = dealDetailList.value.length;
    } finally {
      tabLoadingMap.value.trade = false;
    }
  };

  // 发放记录
  const fetchSapData = async () => {
    tabLoadingMap.value.coin = true;
    try {
      const range = detailDateRange.value.coin;
      const baseParams = {
        detail_startdate_Ymd: range.start,
        detail_enddate_Ymd: range.end,
        selected_gameid: props.gameData.gameid,
        selected_openid: props.gameData.openid,
      };
      const [groupRes, detailRes] = await Promise.all([
        executeDataSource('sap_groupdim_stats', baseParams),
        executeDataSource('sap_detail_list', baseParams),
      ]);
      sapGroupStats.value = extractResults(groupRes);
      sapDetailList.value = extractResults(detailRes);
      coinPagination.value.count = sapDetailList.value.length;
    } finally {
      tabLoadingMap.value.coin = false;
    }
  };

  // 聊天记录
  const fetchChatData = async () => {
    tabLoadingMap.value.chat = true;
    try {
      const range = detailDateRange.value.chat;
      const res = await executeDataSource('chat_detail_list', {
        detail_startdate_Ymd: range.start,
        detail_enddate_Ymd: range.end,
        is_sensitive: chatSuspectedViolation.value ? ['1'] : ['0', '1'],
        selected_gameid: props.gameData.gameid,
        selected_openid: props.gameData.openid,
      });
      chatDetailList.value = extractResults(res);
      chatPagination.value.count = chatDetailList.value.length;
    } finally {
      tabLoadingMap.value.chat = false;
    }
  };

  // Tab 切换时按需加载数据
  const tabDataLoaded = ref<Record<string, boolean>>({});

  const loadTabData = (tabKey: string) => {
    if (tabDataLoaded.value[tabKey]) return;
    tabDataLoaded.value[tabKey] = true;
    switch (tabKey) {
    case 'login':
      fetchLoginData();
      break;
    case 'gift':
      fetchGiveData();
      break;
    case 'trade':
      fetchDealData();
      break;
    case 'coin':
      fetchSapData();
      break;
    case 'chat':
      fetchChatData();
      break;
    default:
      break;
    }
  };

  // 监听 tab 切换
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

  // 分页映射表
  const paginationMap: Record<string, typeof loginPagination> = {
    login: loginPagination,
    gift: giftPagination,
    trade: tradePagination,
    coin: coinPagination,
    chat: chatPagination,
  };

  const handleTabPageChange = (tabKey: string, page: number) => {
    paginationMap[tabKey].value.current = page;
  };

  const handleTabPageLimitChange = (tabKey: string, limit: number) => {
    paginationMap[tabKey].value.limit = limit;
    paginationMap[tabKey].value.current = 1;
  };

  // 搜索条件变化处理
  const handleTabSearchConditionChange = (tabKey: string, conditions: any[]) => {
    tabSearchConditions.value[tabKey] = conditions;
  };

  // 日期范围变化时重新加载对应 tab 数据
  const handleTabDateChange = (tabKey: string, range: [string, string]) => {
    if (range[0] && range[1]) {
      const start = range[0].replace(/-/g, '');
      const end = range[1].replace(/-/g, '');
      detailDateRange.value[tabKey] = { start, end };
      tabDataLoaded.value[tabKey] = false;
      loadTabData(tabKey);
    }
  };

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

  // 默认时间范围：最近半年
  const getDefaultExportDateRange = (): [Date, Date] => {
    const now = new Date();
    const halfYearAgo = new Date(now);
    halfYearAgo.setMonth(halfYearAgo.getMonth() - 6);
    return [halfYearAgo, now];
  };
  const exportDateRange = ref<[Date, Date]>(getDefaultExportDateRange());

  // 导出内容选项
  const exportContentOptions = [
    { id: 'userInfo', name: t('用户信息') },
    { id: 'gameRole', name: t('游戏角色') },
    { id: 'login', name: t('登录记录') },
    { id: 'gift', name: t('赠送记录') },
    { id: 'trade', name: t('交易记录') },
    { id: 'coin', name: t('代币发放记录') },
    { id: 'chat', name: t('聊天记录') },
  ];
  // 默认全选
  const exportContentChecked = ref<string[]>(exportContentOptions.map(item => item.id));

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
      if (exportContentChecked.value.includes('gameRole')) {
        const dp = getDateParams();
        const roleParams = {
          one_month_ago_Ymd_dashed: dp.one_month_ago_Ymd_dashed,
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
        const dp = getDateParams();
        const res = await executeDataSource('give_detail_list', {
          one_year_ago_Ymd: dp.one_year_ago_Ymd,
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
        const data = extractResults(res);
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
          colWidths.push({ wch: Math.min(maxLen + 2, 50) });
        }
        ws['!cols'] = colWidths;
        // 表头自动筛选
        ws['!autofilter'] = { ref: ws['!ref'] };
      });

      // 导出文件，文件名为工具名
      const fileName = props.toolName || props.gameData.name || t('游戏审计数据');
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
    flex-wrap: wrap;
    gap: 32px;
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
    grid-template-columns: auto auto;
    gap: 12px 24px;
  }

  .export-popover-footer {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    padding-top: 8px;
  }
}

/* Tab 标签页 */
.game-tabs {
  margin-top: 12px;
}

/* 概览内容 */
.overview-content {
  padding-top: 16px;
}

/* Tab loading 容器 */
.tab-loading-wrapper {
  min-height: 400px;
}

/* loading 占位元素 */
.loading-placeholder {
  height: 400px;
}

/* Tab 暂无数据 */
.tab-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
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
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.view-detail-link {
  display: flex;
  font-size: 12px;
  color: #3a84ff;
  cursor: pointer;
  align-items: center;
  gap: 2px;

  &:hover {
    color: #1768ef;
  }
}

.last-record-row {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
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
