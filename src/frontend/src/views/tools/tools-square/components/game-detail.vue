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
            {{ gameData.wechat }}
            <audit-icon
              class="eye-icon"
              type="unview" />
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
      <bk-button class="export-btn">
        <audit-icon
          style="margin-right: 4px;"
          type="download" />
        {{ t('导出') }}
      </bk-button>
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
          <div class="overview-content">
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
        </bk-tab-panel>

        <bk-tab-panel
          v-for="tab in recordTabs"
          :key="tab.key"
          :label="tab.label"
          :name="tab.key">
          <game-record-tab
            :chart-rows="tab.chartRows"
            :search-placeholder="tab.searchPlaceholder"
            :table-columns="tab.table.columns"
            :table-data="tab.table.data"
            :table-pagination="tab.table.pagination"
            :table-title="tab.table.title"
            @page-change="handleTabPageChange(tab.key, $event)"
            @page-limit-change="handleTabPageLimitChange(tab.key, $event)">
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
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import GameRecordTab from './game-record-tab.vue';
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
    wechat: string;
    coinBalance: number;
    totalRecharge: number;
    totalGift: number;
    totalIssue: number;
  }

  interface Props {
    gameData?: GameData;
    initialTab?: string;
  }

  const props = withDefaults(defineProps<Props>(), {
    gameData: () => ({
      name: '王者荣耀',
      openid: 'wx_oABCd1234567890',
      wechat: 'm******4',
      coinBalance: 350,
      totalRecharge: 3200,
      totalGift: 0,
      totalIssue: 6978,
    }),
  });

  const { t } = useI18n();
  const activeTab = ref(props.initialTab || 'overview');

  // 当 initialTab 变化时（如同一游戏从不同入口再次打开），同步切换 tab
  watch(() => props.initialTab, (newTab) => {
    if (newTab) {
      activeTab.value = newTab;
    }
  });

  // 复制
  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  // 角色总览假数据
  const roleList = ref([
    { roleName: '无名剑客', roleId: 'R100070001', platform: 'QQ', zone: '电信区', loginPlaceMonth: 14, loginPlaceYear: 88, loginCountMonth: 561, loginCountYear: 561, tradeObjMonth: 561, tradeObjYear: 561 },
    { roleName: '破晓', roleId: 'R100070001', platform: 'IOS', zone: '5区', loginPlaceMonth: 7, loginPlaceYear: 85, loginCountMonth: 450, loginCountYear: 450, tradeObjMonth: 450, tradeObjYear: 450 },
    { roleName: '****', roleId: 'R100070001', platform: 'Android', zone: '10区', loginPlaceMonth: 17, loginPlaceYear: 34, loginCountMonth: 859, loginCountYear: 859, tradeObjMonth: 859, tradeObjYear: 859 },
    { roleName: '妲己', roleId: 'R100070001', platform: '微信', zone: '移动区', loginPlaceMonth: 3, loginPlaceYear: 32, loginCountMonth: 565, loginCountYear: 565, tradeObjMonth: 565, tradeObjYear: 0 },
  ]);

  const roleColumns = [
    { label: () => t('角色名称'), field: 'roleName' },
    { label: () => t('角色ID'), field: 'roleId' },
    { label: () => t('平台'), field: 'platform' },
    { label: () => t('小区'), field: 'zone' },
    { label: () => `${t('登录地点数')}/${t('月')}`, field: 'loginPlaceMonth', sort: true },
    { label: () => `${t('登录地点数')}/${t('年')}`, field: 'loginPlaceYear', sort: true },
    { label: () => `${t('登录次数')}/${t('月')}`, field: 'loginCountMonth', sort: true },
    { label: () => `${t('登录次数')}/${t('年')}`, field: 'loginCountYear', sort: true },
    { label: () => `${t('交易对象数')}/${t('月')}`, field: 'tradeObjMonth', sort: true },
    { label: () => `${t('交易对象数')}/${t('年')}`, field: 'tradeObjYear', sort: true },
  ];

  const loginStatList = ref([
    { period: '最近7天', loginCount: 561, loginPlaceCount: 561, loginDeviceCount: 561, loginIpCount: 561 },
    { period: '最近14天', loginCount: 450, loginPlaceCount: 450, loginDeviceCount: 450, loginIpCount: 450 },
    { period: '最近1个月', loginCount: 859, loginPlaceCount: 859, loginDeviceCount: 859, loginIpCount: 859 },
  ]);

  const loginStatColumns = [
    { label: () => t('统计频率'), field: 'period' },
    { label: () => t('登录次数'), field: 'loginCount', sort: true },
    { label: () => t('登录地点数'), field: 'loginPlaceCount', sort: true },
    { label: () => t('登录设备数'), field: 'loginDeviceCount', sort: true },
    { label: () => `${t('登录IP')} ${t('数')}`, field: 'loginIpCount', sort: true },
  ];

  // ========== 概览页面各 section 配置 ==========
  interface OverviewSectionConfig {
    key: string;
    title: string;
    tabKey?: string;                  // 点击"查看详情"跳转的 tab key
    lastRecordItems?: Array<{         // 最近一次记录的 label-value 列表
      label: string;
      value: string | number;
    }>;
    table?: {                         // simple 模式表格
      columns: Array<Record<string, any>>;
      data: Array<Record<string, any>>;
    };
  }

  const overviewSections = computed<OverviewSectionConfig[]>(() => [
    // 关联的游戏角色总览
    {
      key: 'role',
      title: t('关联的游戏角色总览'),
      table: { columns: roleColumns, data: roleList.value },
    },
    // 登录记录
    {
      key: 'login',
      title: t('登录记录'),
      tabKey: 'login',
      lastRecordItems: [
        { label: t('最近一次登录时间'), value: '2026-04-09 15:19:06' },
        { label: t('登录地点'), value: '广州' },
        { label: t('登录IP'), value: '10.20.30.40' },
        { label: t('登录设备'), value: 'iPhone' },
      ],
      table: { columns: loginStatColumns, data: loginStatList.value },
    },
    // 赠送记录
    {
      key: 'gift',
      title: t('赠送记录'),
      tabKey: 'gift',
      lastRecordItems: [
        { label: t('最近一次赠送时间'), value: '2026-04-09 15:19:06' },
        { label: t('赠送账号'), value: 'owanIsu7xMVj-6a6uwtygudODUxg' },
        { label: t('道具名称'), value: '英雄碎片' },
        { label: t('赠送总额'), value: '992 元' },
      ],
    },
    // 交易记录
    {
      key: 'trade',
      title: t('交易记录'),
      tabKey: 'trade',
      lastRecordItems: [
        { label: t('最近一次交易时间'), value: '2026-04-09 15:19:06' },
        { label: t('交易对象'), value: 'owanIsu7xMVj-6a6uwtygudODUxg' },
        { label: t('道具名称'), value: '英雄碎片' },
        { label: t('赠送总额'), value: '992 元' },
      ],
    },
    // 代币发放记录
    {
      key: 'coin',
      title: t('代币发放记录'),
      tabKey: 'coin',
      lastRecordItems: [
        { label: t('最近一次发放时间'), value: '2026-04-09 15:19:06' },
        { label: t('发放人'), value: 'yimohe' },
        { label: t('发放数量'), value: '代 2481' },
        { label: t('发放金额'), value: '992 元' },
      ],
    },
    // 聊天记录
    {
      key: 'chat',
      title: t('聊天记录'),
      tabKey: 'chat',
      lastRecordItems: [
        { label: t('最近一次聊天时间'), value: '2026-04-09 15:19:06' },
        { label: t('发起人'), value: 'frodomei' },
        { label: t('大区ID'), value: '2011' },
        { label: t('聊天内容'), value: '资源号便宜出，私聊聊' },
      ],
    },
  ]);

  // ========== 登录记录 tab 数据 ==========
  // 设备分布数据
  const loginDeviceData = [
    { name: 'iPhone', value: 528 },
    { name: 'Android', value: 308 },
    { name: 'Windows', value: 196 },
    { name: 'iPad', value: 113 },
    { name: 'Mac', value: 86 },
  ];
  // 地点分布数据
  const loginLocationData = [
    { name: '深圳', value: 528 },
    { name: '广州', value: 308 },
    { name: '北京', value: 196 },
    { name: '成都', value: 113 },
    { name: '上海', value: 86 },
    { name: '杭州', value: 44 },
  ];
  // 时段分布数据
  const loginTimeData = [
    { name: '18:00-20:59', value: 528 },
    { name: '09:00-11:59', value: 308 },
    { name: '12:00-14:59', value: 196 },
    { name: '21:00-23:59', value: 113 },
    { name: '15:00-17:59', value: 86 },
    { name: '06:00-08:59', value: 44 },
    { name: '03:00-05:59', value: 34 },
    { name: '00:00-02:59', value: 15 },
  ];
  const loginDetailList = ref([
    { time: '2026-04-09 09:07:35', location: '湖南省', ip: '94.37.229.177', region: 9603, roleId: 'R100070001', roleName: '王者用户0001', level: 'Lv.24', device: 'iPhone', model: 'iPhone 14' },
    { time: '2026-04-07 02:20:42', location: '江苏省', ip: '206.202.132.36', region: 4367, roleId: 'R100070001', roleName: '王者用户0001', level: 'Lv.24', device: 'iPhone', model: 'iPhone 14' },
    { time: '2026-03-31 23:07:22', location: '澳门特别行政区', ip: '29.203.230.134', region: 4294, roleId: 'R100070001', roleName: '王者用户0001', level: 'Lv.24', device: 'iPhone', model: 'iPhone 14' },
    { time: '2026-03-15 13:20:14', location: '上海', ip: '241.211.167.63', region: 1136, roleId: 'R100070001', roleName: '王者用户0001', level: 'Lv.24', device: 'iPhone', model: 'iPhone 14' },
    { time: '2026-03-10 00:19:54', location: '河北省', ip: '46.38.239.201', region: 890, roleId: 'R100070001', roleName: '王者用户0001', level: 'Lv.24', device: 'iPhone', model: 'iPhone 14' },
    { time: '2026-03-07 12:16:18', location: '山西省', ip: '23.138.206.34', region: 5311, roleId: 'R100070001', roleName: '王者用户0001', level: 'Lv.24', device: 'iPhone', model: 'iPhone 14' },
    { time: '2026-02-06 22:13:35', location: '福建省', ip: '238.121.252.150', region: 6770, roleId: 'R100070001', roleName: '王者用户0001', level: 'Lv.24', device: 'iPhone', model: 'iPhone 14' },
    { time: '2026-01-25 13:35:18', location: '广西壮族自治区', ip: '134.106.193.35', region: 1654, roleId: 'R100070001', roleName: '王者用户0001', level: 'Lv.24', device: 'iPhone', model: 'iPhone 14' },
    { time: '2026-01-23 02:40:10', location: '青海省', ip: '73.125.206.107', region: 1829, roleId: 'R100070001', roleName: '王者用户0001', level: 'Lv.24', device: 'iPhone', model: 'iPhone 14' },
    { time: '2026-01-18 13:09:41', location: '黑龙江省', ip: '151.197.149.120', region: 8536, roleId: 'R100070001', roleName: '王者用户0001', level: 'Lv.24', device: 'iPhone', model: 'iPhone 14' },
  ]);
  const loginDetailColumns = [
    { label: () => t('登录时间'), field: 'time', sort: true },
    { label: () => t('登录地点'), field: 'location', filter: true },
    { label: () => t('登录IP'), field: 'ip' },
    { label: () => t('大区'), field: 'region' },
    { label: () => t('角色ID'), field: 'roleId' },
    { label: () => t('角色名称'), field: 'roleName' },
    { label: () => t('等级'), field: 'level' },
    { label: () => t('登录设备'), field: 'device', filter: true },
    { label: () => t('机型'), field: 'model', filter: true },
  ];
  const loginPagination = ref({ count: 198, current: 1, limit: 10 });

  // ========== 赠送记录 tab 数据 ==========
  // 赠送对象分布（按金额）
  const giftTargetAmountData = [
    { name: 'owanIsu7xMVj', value: 420 },
    { name: 'wx_user_001', value: 280 },
    { name: 'wx_user_002', value: 160 },
    { name: 'wx_user_003', value: 82 },
    { name: t('其他'), value: 50 },
  ];
  // 赠送对象分布（按次数）
  const giftTargetCountData = [
    { name: 'owanIsu7xMVj', value: 35 },
    { name: 'wx_user_001', value: 22 },
    { name: 'wx_user_002', value: 15 },
    { name: 'wx_user_003', value: 8 },
    { name: t('其他'), value: 5 },
  ];
  // 赠送道具分布（按金额）
  const giftItemAmountData = [
    { name: '英雄碎片', value: 450 },
    { name: '铭文碎片', value: 300 },
    { name: '皮肤碎片', value: 150 },
    { name: t('其他'), value: 92 },
  ];
  // 赠送道具分布（按次数）
  const giftItemCountData = [
    { name: '英雄碎片', value: 40 },
    { name: '铭文碎片', value: 25 },
    { name: '皮肤碎片', value: 12 },
    { name: t('其他'), value: 8 },
  ];
  const giftDetailList = ref([
    { time: '2026-04-09 09:07:35', account: 'owanIsu7xMVj-6a6uwtygudODUxg', itemName: '英雄碎片', amount: 120, region: 9603, roleId: 'R100070001', roleName: '王者用户0001' },
    { time: '2026-04-07 02:20:42', account: 'wx_user_001', itemName: '铭文碎片', amount: 80, region: 4367, roleId: 'R100070001', roleName: '王者用户0001' },
    { time: '2026-03-31 23:07:22', account: 'wx_user_002', itemName: '皮肤碎片', amount: 200, region: 4294, roleId: 'R100070001', roleName: '王者用户0001' },
  ]);
  const giftDetailColumns = [
    { label: () => t('赠送时间'), field: 'time', sort: true },
    { label: () => t('赠送账号'), field: 'account' },
    { label: () => t('道具名称'), field: 'itemName', filter: true },
    { label: () => t('赠送金额'), field: 'amount', sort: true },
    { label: () => t('大区'), field: 'region' },
    { label: () => t('角色ID'), field: 'roleId' },
    { label: () => t('角色名称'), field: 'roleName' },
  ];
  const giftPagination = ref({ count: 85, current: 1, limit: 10 });

  // ========== 交易记录 tab 数据 ==========
  // 交易对象分布（按金额）
  const tradeTargetAmountData = [
    { name: 'owanIsu7xMVj', value: 420 },
    { name: 'wx_user_001', value: 280 },
    { name: 'wx_user_002', value: 160 },
    { name: 'wx_user_003', value: 82 },
    { name: t('其他'), value: 50 },
  ];
  // 交易对象分布（按次数）
  const tradeTargetCountData = [
    { name: 'owanIsu7xMVj', value: 35 },
    { name: 'wx_user_001', value: 22 },
    { name: 'wx_user_002', value: 15 },
    { name: 'wx_user_003', value: 8 },
    { name: t('其他'), value: 5 },
  ];
  // 交易道具分布（按金额）
  const tradeItemAmountData = [
    { name: '英雄碎片', value: 450 },
    { name: '铭文碎片', value: 300 },
    { name: '皮肤碎片', value: 150 },
    { name: t('其他'), value: 92 },
  ];
  // 交易道具分布（按次数）
  const tradeItemCountData = [
    { name: '英雄碎片', value: 40 },
    { name: '铭文碎片', value: 25 },
    { name: '皮肤碎片', value: 12 },
    { name: t('其他'), value: 8 },
  ];
  const tradeDetailList = ref([
    { time: '2026-04-09 09:07:35', target: 'owanIsu7xMVj-6a6uwtygudODUxg', itemName: '英雄碎片', amount: 120, region: 9603, roleId: 'R100070001', roleName: '王者用户0001' },
    { time: '2026-04-07 02:20:42', target: 'wx_user_001', itemName: '铭文碎片', amount: 80, region: 4367, roleId: 'R100070001', roleName: '王者用户0001' },
    { time: '2026-03-31 23:07:22', target: 'wx_user_002', itemName: '皮肤碎片', amount: 200, region: 4294, roleId: 'R100070001', roleName: '王者用户0001' },
  ]);
  const tradeDetailColumns = [
    { label: () => t('交易时间'), field: 'time', sort: true },
    { label: () => t('交易对象'), field: 'target' },
    { label: () => t('道具名称'), field: 'itemName', filter: true },
    { label: () => t('交易金额'), field: 'amount', sort: true },
    { label: () => t('大区'), field: 'region' },
    { label: () => t('角色ID'), field: 'roleId' },
    { label: () => t('角色名称'), field: 'roleName' },
  ];
  const tradePagination = ref({ count: 85, current: 1, limit: 10 });

  // ========== 代币发放记录 tab 数据 ==========
  // 需求类型分布
  const coinDemandTypeData = [
    { name: '活动奖励', value: 1200 },
    { name: '补偿发放', value: 800 },
    { name: '运营活动', value: 481 },
  ];
  // 发放人分布
  const coinIssuerData = [
    { name: 'yimohe', value: 1500 },
    { name: 'admin01', value: 600 },
    { name: 'admin02', value: 381 },
  ];
  // 需求来源分布
  const coinSourceData = [
    { name: '客服工单', value: 1000 },
    { name: '运营后台', value: 900 },
    { name: '自动发放', value: 581 },
  ];
  const coinDetailList = ref([
    { time: '2026-04-09 09:07:35', issuer: 'yimohe', demandType: '活动奖励', quantity: 500, amount: 200, source: '客服工单', region: 9603, roleId: 'R100070001', roleName: '王者用户0001' },
    { time: '2026-04-07 02:20:42', issuer: 'admin01', demandType: '补偿发放', quantity: 300, amount: 120, source: '运营后台', region: 4367, roleId: 'R100070001', roleName: '王者用户0001' },
    { time: '2026-03-31 23:07:22', issuer: 'yimohe', demandType: '运营活动', quantity: 200, amount: 80, source: '自动发放', region: 4294, roleId: 'R100070001', roleName: '王者用户0001' },
  ]);
  const coinDetailColumns = [
    { label: () => t('发放时间'), field: 'time', sort: true },
    { label: () => t('发放人'), field: 'issuer' },
    { label: () => t('需求类型'), field: 'demandType', filter: true },
    { label: () => t('发放数量'), field: 'quantity', sort: true },
    { label: () => t('发放金额'), field: 'amount', sort: true },
    { label: () => t('需求来源'), field: 'source', filter: true },
    { label: () => t('大区'), field: 'region' },
    { label: () => t('角色ID'), field: 'roleId' },
    { label: () => t('角色名称'), field: 'roleName' },
  ];
  const coinPagination = ref({ count: 56, current: 1, limit: 10 });

  // ========== 聊天记录 tab 数据 ==========
  const chatSuspectedViolation = ref(false);
  const chatDetailList = ref([
    { time: '2026-04-09 09:07:35', sender: 'frodomei', content: '资源号便宜出，私聊聊', region: 2011, roleId: 'R100070001', roleName: '王者用户0001', channel: '世界频道' },
    { time: '2026-04-07 02:20:42', sender: 'frodomei', content: '组队打排位，来人', region: 2011, roleId: 'R100070001', roleName: '王者用户0001', channel: '组队频道' },
    { time: '2026-03-31 23:07:22', sender: 'frodomei', content: '这个英雄怎么出装', region: 2011, roleId: 'R100070001', roleName: '王者用户0001', channel: '公会频道' },
  ]);
  const chatDetailColumns = [
    { label: () => t('聊天时间'), field: 'time', sort: true },
    { label: () => t('发起人'), field: 'sender' },
    { label: () => t('聊天内容'), field: 'content' },
    { label: () => t('大区'), field: 'region' },
    { label: () => t('角色ID'), field: 'roleId' },
    { label: () => t('角色名称'), field: 'roleName' },
    { label: () => t('频道'), field: 'channel', filter: true },
  ];
  const chatPagination = ref({ count: 120, current: 1, limit: 10 });

  // ========== 统一 Tab 配置 ==========
  const recordTabs = computed<GameRecordTabConfig[]>(() => [
    // 登录记录
    {
      key: 'login',
      label: t('登录记录'),
      chartRows: [
        [
          { title: t('登录设备分布'), data: loginDeviceData, total: 967, centerLabel: t('登录总数') },
          { title: t('登录地点分布'), data: loginLocationData, total: 967, centerLabel: t('登录总数') },
          { title: t('登录时段分布'), data: loginTimeData, total: 967, centerLabel: t('登录总数') },
        ],
      ],
      searchPlaceholder: t('搜索 登录地点、登录IP、大区ID、角色ID、角色名、等级、登录设备、机型'),
      table: {
        columns: loginDetailColumns,
        data: loginDetailList.value,
        pagination: loginPagination.value,
        title: t('登录明细'),
      },
    },
    // 赠送记录
    {
      key: 'gift',
      label: t('赠送记录'),
      chartRows: [
        [
          { title: t('赠送对象分布（按金额）'), data: giftTargetAmountData, total: 992, centerLabel: t('总额（元）') },
          { title: t('赠送对象分布（按次数）'), data: giftTargetCountData, total: 85, centerLabel: t('总次数') },
        ],
        [
          { title: t('赠送道具分布（按金额）'), data: giftItemAmountData, total: 992, centerLabel: t('总额（元）') },
          { title: t('赠送道具分布（按次数）'), data: giftItemCountData, total: 85, centerLabel: t('总次数') },
        ],
      ],
      searchPlaceholder: t('搜索 赠送账号、道具名称、大区ID、角色ID、角色名'),
      table: {
        columns: giftDetailColumns,
        data: giftDetailList.value,
        pagination: giftPagination.value,
        title: t('赠送明细'),
      },
    },
    // 交易记录
    {
      key: 'trade',
      label: t('交易记录'),
      chartRows: [
        [
          { title: t('交易对象分布（按金额）'), data: tradeTargetAmountData, total: 992, centerLabel: t('总额（元）') },
          { title: t('交易对象分布（按次数）'), data: tradeTargetCountData, total: 85, centerLabel: t('总次数') },
        ],
        [
          { title: t('交易道具分布（按金额）'), data: tradeItemAmountData, total: 992, centerLabel: t('总额（元）') },
          { title: t('交易道具分布（按次数）'), data: tradeItemCountData, total: 85, centerLabel: t('总次数') },
        ],
      ],
      searchPlaceholder: t('搜索 交易对象、道具名称、大区ID、角色ID、角色名'),
      table: {
        columns: tradeDetailColumns,
        data: tradeDetailList.value,
        pagination: tradePagination.value,
        title: t('交易明细'),
      },
    },
    // 代币发放记录
    {
      key: 'coin',
      label: t('代币发放记录'),
      chartRows: [
        [
          { title: t('需求类型分布'), data: coinDemandTypeData, total: 2481, centerLabel: t('总数量') },
          { title: t('发放人分布'), data: coinIssuerData, total: 2481, centerLabel: t('总数量') },
          { title: t('需求来源分布'), data: coinSourceData, total: 2481, centerLabel: t('总数量') },
        ],
      ],
      searchPlaceholder: t('搜索 发放人、需求来源、大区ID、角色ID、角色名'),
      table: {
        columns: coinDetailColumns,
        data: coinDetailList.value,
        pagination: coinPagination.value,
        title: t('发放明细'),
      },
    },
    // 聊天记录
    {
      key: 'chat',
      label: t('聊天记录'),
      chartRows: [],
      searchPlaceholder: t('搜索 聊天内容、大区ID、角色ID、角色名'),
      table: {
        columns: chatDetailColumns,
        data: chatDetailList.value,
        pagination: chatPagination.value,
        title: t('聊天明细'),
      },
      extraFilter: 'chatViolation',
    },
  ]);

  // 分页映射表
  const paginationMap: Record<string, typeof giftPagination> = {
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


</script>

<style scoped lang="postcss">

/* 游戏基本信息头部 */
.game-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px 16px;
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

/* Tab 标签页 */
.game-tabs {
  margin-top: 12px;
}

/* 概览内容 */
.overview-content {
  padding-top: 16px;
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
