/*
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
*/
import { type Ref, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { CHART_FIELDS, LOGIN_DETAIL_FIELDS } from './game-field-keys';
import type { SearchFieldItem } from './game-search-fields';

// 登录时段完整列表（正向排序：0-3 → 3-6 → ... → 21-24）
const ALL_TIME_PERIODS = [
  '0:00~3:00', '3:00~6:00', '6:00~9:00', '9:00~12:00',
  '12:00~15:00', '15:00~18:00', '18:00~21:00', '21:00~24:00',
];

// 饼图数据项（与 API 返回格式一致）
export interface ChartDataItem {
  dim_type: string;       // 维度类型，如"登录地点"、"登录设备"等
  metric_type: string;    // 指标类型，如"登录总数"等
  dim_value: string;      // 维度值，如"北京市"等
  metric_value: number;   // 指标值
  rn: string;             // 排名，"其他"分类时rn为"99999"
}

// 饼图配置项
export interface ChartConfig {
  title: string;                                // 图表标题
  data: ChartDataItem[];                        // 饼图数据（新格式）
  total: number;                                // 总数
  centerLabel: string;                          // 中心文字
  tooltipNameMap?: Record<string, string>;      // 图例名称 → hover 展示名称 映射（如 UUID → 机型(UUID)）
}

/**
 * 将 groupdim_stats 数据按 dim_type 过滤，返回新格式的饼图数据
 * 新数据格式：{ dim_type, metric_type, dim_value, metric_value, rn }
 */
export const buildChartFromGroupStats = (
  data: Array<Record<string, any>>,
  dimType: string,
): ChartDataItem[] => data
  .filter(row => row.dim_type === dimType)
  .map(row => ({
    dim_type: row.dim_type || '',
    metric_type: row.metric_type || '',
    dim_value: row.dim_value || '',
    metric_value: Number(row.metric_value) || 0,
    rn: String(row.rn ?? ''),
  }));

/**
 * 各 Tab 下「图表标题 → 表格搜索字段ID」的映射工厂函数
 * 用于点击图例项时联动表格搜索条件
 */
export const useChartTitleToFieldIdMap = () => {
  const { t } = useI18n();
  const map: Record<string, Record<string, string>> = {
    login: {
      [t('登录设备分析')]: 'login_device',
      [t('登录地点分布')]: 'login_location',
    },
    gift: {
      [t('赠送对象分布（总额）')]: 'target_openid',
      [t('赠送对象分布（次数）')]: 'target_openid',
      [t('赠送道具分布（总额）')]: 'item_id',
      [t('赠送道具分布（数量）')]: 'item_id',
    },
    trade: {
      [t('交易对象分布（总额）')]: 'trade_target',
      [t('交易对象分布（次数）')]: 'trade_target',
      [t('交易道具分布（总额）')]: 'item_id',
      [t('交易道具分布（数量）')]: 'item_id',
    },
    coin: {
      [t('需求类型分布统计')]: 'demand_type',
      [t('发放人分布统计')]: 'issuer',
      [t('需求来源分布统计')]: 'demand_source',
    },
  };
  return map;
};

/**
 * 各 Tab 饼图行构建器工厂
 */
export const useGameChartBuilders = () => {
  const { t } = useI18n();

  // ========== 登录记录 tab ==========
  const buildLoginChartRows = (
    stats: Array<Record<string, any>>,
    detailList: Array<Record<string, any>> = [],
  ): ChartConfig[][] => {
    if (stats.length === 0) return [];

    // 构建 设备UUID → 机型 映射（从明细列表获取）
    const deviceModelMap: Record<string, string> = {};
    detailList.forEach((row) => {
      const deviceId = row[LOGIN_DETAIL_FIELDS.LOGIN_DEVICE];
      const model = row[LOGIN_DETAIL_FIELDS.DEVICE_MODEL];
      if (deviceId && model) {
        deviceModelMap[deviceId] = model;
      }
    });

    // 登录设备：按 rn 排序（rn=99999 的"其他"自动排最后）
    const deviceData = buildChartFromGroupStats(stats, CHART_FIELDS.LOGIN_DEVICE);
    const deviceTooltipNameMap: Record<string, string> = {};
    deviceData.forEach((item) => {
      if (deviceModelMap[item.dim_value]) {
        deviceTooltipNameMap[item.dim_value] = `${deviceModelMap[item.dim_value]}(${item.dim_value})`;
      }
    });

    // 登录地点
    const locationData = buildChartFromGroupStats(stats, CHART_FIELDS.LOGIN_LOCATION);

    // 登录时段：按时间正向排序，只展示有数据的时段
    const rawTimeData = buildChartFromGroupStats(stats, CHART_FIELDS.LOGIN_TIME_PERIOD);
    const timeDataMap: Record<string, ChartDataItem> = {};
    rawTimeData.forEach((item) => {
      timeDataMap[item.dim_value] = item;
    });
    const timeData = ALL_TIME_PERIODS
      .map(period => timeDataMap[period])
      .filter((item): item is ChartDataItem => !!item && item.metric_value > 0);

    // 每个饼图的 total 只计算各自分组的数据之和
    const deviceTotal = deviceData.reduce((s, d) => s + d.metric_value, 0);
    const locationTotal = locationData.reduce((s, d) => s + d.metric_value, 0);
    const timeTotal = timeData.reduce((s, d) => s + d.metric_value, 0);
    const charts: ChartConfig[] = [];
    if (deviceData.length > 0) {
      charts.push({
        title: t('登录设备分析'),
        data: deviceData,
        total: deviceTotal,
        centerLabel: t('登录总数'),
        tooltipNameMap: deviceTooltipNameMap,
      });
    }
    if (locationData.length > 0) charts.push({ title: t('登录地点分布'), data: locationData, total: locationTotal, centerLabel: t('登录总数') });
    if (timeTotal > 0) charts.push({ title: t('登录时段分布'), data: timeData, total: timeTotal, centerLabel: t('登录总数') });
    return charts.length > 0 ? [charts] : [];
  };

  // ========== 赠送记录 tab ==========
  const buildGiveChartRows = (stats: Array<Record<string, any>>): ChartConfig[][] => {
    if (stats.length === 0) return [];
    // 按 metric_type 区分金额和次数
    const targetAmountOnly = buildChartFromGroupStats(stats, CHART_FIELDS.GIFT_TARGET)
      .filter(d => d.metric_type === CHART_FIELDS.GIFT_AMOUNT_YUAN);
    const targetCountData = buildChartFromGroupStats(stats, CHART_FIELDS.GIFT_TARGET)
      .filter(d => d.metric_type === CHART_FIELDS.TIMES);
    const itemAmountOnly = buildChartFromGroupStats(stats, CHART_FIELDS.GIFT_ITEM)
      .filter(d => d.metric_type === CHART_FIELDS.GIFT_AMOUNT_YUAN);
    const itemCountData = buildChartFromGroupStats(stats, CHART_FIELDS.GIFT_ITEM)
      .filter(d => d.metric_type === CHART_FIELDS.GIFT_QUANTITY);
    const rows: ChartConfig[][] = [];
    const row1: ChartConfig[] = [];
    if (targetAmountOnly.length > 0) {
      const total = targetAmountOnly.reduce((s, d) => s + d.metric_value, 0);
      row1.push({ title: t('赠送对象分布（总额）'), data: targetAmountOnly, total, centerLabel: t('总额（元）') });
    }
    if (targetCountData.length > 0) {
      const total = targetCountData.reduce((s, d) => s + d.metric_value, 0);
      row1.push({ title: t('赠送对象分布（次数）'), data: targetCountData, total, centerLabel: t('总次数') });
    }
    if (row1.length > 0) rows.push(row1);
    const row2: ChartConfig[] = [];
    if (itemAmountOnly.length > 0) {
      const total = itemAmountOnly.reduce((s, d) => s + d.metric_value, 0);
      row2.push({ title: t('赠送道具分布（总额）'), data: itemAmountOnly, total, centerLabel: t('总额（元）') });
    }
    if (itemCountData.length > 0) {
      const total = itemCountData.reduce((s, d) => s + d.metric_value, 0);
      row2.push({ title: t('赠送道具分布（数量）'), data: itemCountData, total, centerLabel: t('总数量') });
    }
    if (row2.length > 0) rows.push(row2);
    return rows;
  };

  // ========== 交易记录 tab ==========
  const buildDealChartRows = (stats: Array<Record<string, any>>): ChartConfig[][] => {
    if (stats.length === 0) return [];
    const targetAmountData = buildChartFromGroupStats(stats, CHART_FIELDS.TRADE_TARGET)
      .filter(d => d.metric_type === CHART_FIELDS.TRADE_AMOUNT_YUAN);
    const targetCountData = buildChartFromGroupStats(stats, CHART_FIELDS.TRADE_TARGET)
      .filter(d => d.metric_type === CHART_FIELDS.TRADE_TIMES);
    const itemAmountData = buildChartFromGroupStats(stats, CHART_FIELDS.TRADE_ITEM)
      .filter(d => d.metric_type === CHART_FIELDS.TRADE_AMOUNT_YUAN);
    const itemCountData = buildChartFromGroupStats(stats, CHART_FIELDS.TRADE_ITEM)
      .filter(d => d.metric_type === CHART_FIELDS.TRADE_QUANTITY);
    const rows: ChartConfig[][] = [];
    const row1: ChartConfig[] = [];
    if (targetAmountData.length > 0) {
      const total = targetAmountData.reduce((s, d) => s + d.metric_value, 0);
      row1.push({ title: t('交易对象分布（总额）'), data: targetAmountData, total, centerLabel: t('总额（元）') });
    }
    if (targetCountData.length > 0) {
      const total = targetCountData.reduce((s, d) => s + d.metric_value, 0);
      row1.push({ title: t('交易对象分布（次数）'), data: targetCountData, total, centerLabel: t('总次数') });
    }
    if (row1.length > 0) rows.push(row1);
    const row2: ChartConfig[] = [];
    if (itemAmountData.length > 0) {
      const total = itemAmountData.reduce((s, d) => s + d.metric_value, 0);
      row2.push({ title: t('交易道具分布（总额）'), data: itemAmountData, total, centerLabel: t('总额（元）') });
    }
    if (itemCountData.length > 0) {
      const total = itemCountData.reduce((s, d) => s + d.metric_value, 0);
      row2.push({ title: t('交易道具分布（数量）'), data: itemCountData, total, centerLabel: t('总数量') });
    }
    if (row2.length > 0) rows.push(row2);
    return rows;
  };

  // ========== 发放记录 tab ==========
  const buildSapChartRows = (stats: Array<Record<string, any>>): ChartConfig[][] => {
    if (stats.length === 0) return [];
    const demandTypeData = buildChartFromGroupStats(stats, CHART_FIELDS.DEMAND_TYPE);
    const issuerData = buildChartFromGroupStats(stats, CHART_FIELDS.ISSUER);
    const sourceData = buildChartFromGroupStats(stats, CHART_FIELDS.DEMAND_SOURCE);
    const charts: ChartConfig[] = [];
    if (demandTypeData.length > 0) {
      const total = demandTypeData.reduce((s, d) => s + d.metric_value, 0);
      charts.push({ title: t('需求类型分布统计'), data: demandTypeData, total, centerLabel: t('发放金额（元）') });
    }
    if (issuerData.length > 0) {
      const total = issuerData.reduce((s, d) => s + d.metric_value, 0);
      charts.push({ title: t('发放人分布统计'), data: issuerData, total, centerLabel: t('发放金额（元）') });
    }
    if (sourceData.length > 0) {
      const total = sourceData.reduce((s, d) => s + d.metric_value, 0);
      charts.push({ title: t('需求来源分布统计'), data: sourceData, total, centerLabel: t('发放金额（元）') });
    }
    return charts.length > 0 ? [charts] : [];
  };

  return {
    buildLoginChartRows,
    buildGiveChartRows,
    buildDealChartRows,
    buildSapChartRows,
  };
};

// 图表↔表格 联动 composable
// - tabChartActiveNames: 各饼图当前激活项（key=tabKey, value={chartTitle: activeName}）
// - handleLegendClick: 图例点击 → 转换为表格搜索条件
// - 反向同步：用户在搜索框删除 tag → 复位对应饼图为"全部显示"
export const useChartTableLink = (
  tabSearchConditions: Ref<Record<string, any[]>>,
  searchFieldsMap: Record<string, SearchFieldItem[]>,
) => {
  const { t } = useI18n();
  const chartTitleToFieldIdMap = useChartTitleToFieldIdMap();

  const tabChartActiveNames = ref<Record<string, Record<string, string>>>({
    login: {},
    gift: {},
    trade: {},
    coin: {},
    chat: {},
  });

  const findSearchFieldById = (
    tabKey: string,
    fieldId: string,
  ): SearchFieldItem | undefined => (searchFieldsMap[tabKey] || []).find(f => f.id === fieldId);

  // 图例点击：转换为表格搜索条件（替换该字段已有条件，未选中时清除该字段条件）
  const handleLegendClick = (
    tabKey: string,
    payload: { title: string; name: string; selected: boolean },
  ) => {
    const fieldId = chartTitleToFieldIdMap[tabKey]?.[payload.title];
    if (!fieldId) return;
    const field = findSearchFieldById(tabKey, fieldId);
    if (!field) return;

    if (!tabChartActiveNames.value[tabKey]) {
      tabChartActiveNames.value[tabKey] = {};
    }
    if (payload.selected && payload.name) {
      tabChartActiveNames.value[tabKey][payload.title] = payload.name;
    } else {
      delete tabChartActiveNames.value[tabKey][payload.title];
    }

    // 移除该字段已有条件
    const otherConditions = (tabSearchConditions.value[tabKey] || [])
      .filter((c: any) => c.fieldId !== fieldId);

    if (payload.selected && payload.name) {
      const opItem = (field.conditions || []).find(op => op.id === 'like')
        || (field.conditions || [])[0]
        || { id: 'like', name: t('包含') };
      otherConditions.push({
        fieldId: field.id,
        fieldName: field.name,
        operator: opItem.id,
        operatorName: opItem.name,
        value: payload.name,
      });
    }
    // eslint-disable-next-line no-param-reassign
    tabSearchConditions.value[tabKey] = otherConditions;
  };

  // 反向同步：搜索条件变化时，若激活项已不存在则复位
  watch(tabSearchConditions, (conditionsMap) => {
    Object.keys(tabChartActiveNames.value).forEach((tabKey) => {
      const titleMap = chartTitleToFieldIdMap[tabKey];
      if (!titleMap) return;
      const activeMap = tabChartActiveNames.value[tabKey];
      const tabConds = conditionsMap[tabKey] || [];
      Object.keys(activeMap).forEach((chartTitle) => {
        const fieldId = titleMap[chartTitle];
        if (!fieldId) return;
        const cond = tabConds.find((c: any) => c.fieldId === fieldId);
        if (!cond || cond.value !== activeMap[chartTitle]) {
          delete activeMap[chartTitle];
        }
      });
    });
  }, { deep: true });

  return {
    tabChartActiveNames,
    handleLegendClick,
  };
};
