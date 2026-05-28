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
import { useI18n } from 'vue-i18n';

import {
  CHAT_DETAIL_FIELDS,
  COIN_DETAIL_FIELDS,
  GIFT_DETAIL_FIELDS,
  LOGIN_DETAIL_FIELDS,
  LOGIN_STAT_FIELDS,
  ROLE_FIELDS,
  TRADE_DETAIL_FIELDS,
} from './game-field-keys';

/**
 * 将后端返回的 ISO 8601 时间字符串（如 "2026-04-29T08:09:09Z"）格式化为本地时间
 * 输出格式：YYYY-MM-DD HH:mm:ss
 * 若入参非 ISO 格式或无法解析，则原样返回
 */
export const formatIsoDateTime = (val: any): string => {
  if (val === null || val === undefined || val === '') return '--';
  const str = String(val);
  // 仅处理 ISO 8601 格式（包含 T 和 Z 或时区偏移），其他格式原样返回
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(str)) {
    return str;
  }
  const d = new Date(str);
  if (Number.isNaN(d.getTime())) return str;
  const pad = (n: number) => String(n).padStart(2, '0');
  const y = d.getFullYear();
  const m = pad(d.getMonth() + 1);
  const day = pad(d.getDate());
  const hh = pad(d.getHours());
  const mm = pad(d.getMinutes());
  const ss = pad(d.getSeconds());
  return `${y}-${m}-${day} ${hh}:${mm}:${ss}`;
};

/**
 * 创建所有游戏详情页的表格列配置
 */
export const useGameTableColumns = () => {
  const { t } = useI18n();

  // ========== 概览 - 角色总览列 ==========
  // 数值统计列空数据展示为 0（而非默认的 --）
  const renderNumberOrZero = (field: string) => ({ data }: { data: Record<string, any> }) => {
    const v = data?.[field];
    return v === null || v === undefined || v === '' ? 0 : v;
  };
  const roleColumns = [
    { label: () => t('角色名称'), field: ROLE_FIELDS.ROLE_NAME },
    { label: () => t('角色ID'), field: ROLE_FIELDS.ROLE_ID },
    { label: () => t('平台'), field: ROLE_FIELDS.PLATFORM },
    { label: () => t('大区'), field: ROLE_FIELDS.ZONE },
    {
      label: () => `${t('登录地点数')}/${t('月')}`,
      field: ROLE_FIELDS.LOGIN_LOCATION_MONTH,
      sort: true,
      render: renderNumberOrZero(ROLE_FIELDS.LOGIN_LOCATION_MONTH),
    },
    {
      label: () => `${t('登录地点数')}/${t('年')}`,
      field: ROLE_FIELDS.LOGIN_LOCATION_YEAR,
      sort: true,
      render: renderNumberOrZero(ROLE_FIELDS.LOGIN_LOCATION_YEAR),
    },
    {
      label: () => `${t('登录次数')}/${t('月')}`,
      field: ROLE_FIELDS.LOGIN_COUNT_MONTH,
      sort: true,
      render: renderNumberOrZero(ROLE_FIELDS.LOGIN_COUNT_MONTH),
    },
    {
      label: () => `${t('登录次数')}/${t('年')}`,
      field: ROLE_FIELDS.LOGIN_COUNT_YEAR,
      sort: true,
      render: renderNumberOrZero(ROLE_FIELDS.LOGIN_COUNT_YEAR),
    },
    {
      label: () => `${t('交易对象数')}/${t('月')}`,
      field: ROLE_FIELDS.TRADE_TARGET_MONTH,
      sort: true,
      render: renderNumberOrZero(ROLE_FIELDS.TRADE_TARGET_MONTH),
    },
    {
      label: () => `${t('交易对象数')}/${t('年')}`,
      field: ROLE_FIELDS.TRADE_TARGET_YEAR,
      sort: true,
      render: renderNumberOrZero(ROLE_FIELDS.TRADE_TARGET_YEAR),
    },
    {
      label: () => `${t('聊天对象')}/${t('月')}`,
      field: ROLE_FIELDS.CHAT_TARGET_MONTH,
      sort: true,
      render: renderNumberOrZero(ROLE_FIELDS.CHAT_TARGET_MONTH),
    },
    {
      label: () => `${t('聊天对象')}/${t('年')}`,
      field: ROLE_FIELDS.CHAT_TARGET_YEAR,
      sort: true,
      render: renderNumberOrZero(ROLE_FIELDS.CHAT_TARGET_YEAR),
    },
    {
      label: () => `${t('聊天数量')}/${t('月')}`,
      field: ROLE_FIELDS.CHAT_COUNT_MONTH,
      sort: true,
      render: renderNumberOrZero(ROLE_FIELDS.CHAT_COUNT_MONTH),
    },
    {
      label: () => `${t('聊天数量')}/${t('年')}`,
      field: ROLE_FIELDS.CHAT_COUNT_YEAR,
      sort: true,
      render: renderNumberOrZero(ROLE_FIELDS.CHAT_COUNT_YEAR),
    },
  ];

  // ========== 概览 - 登录统计列 ==========
  const loginStatColumns = [
    { label: () => t('统计频率'), field: LOGIN_STAT_FIELDS.DAYS_CLASS },
    { label: () => t('登录次数'), field: LOGIN_STAT_FIELDS.LOGIN_COUNT },
    { label: () => t('登录地点数'), field: LOGIN_STAT_FIELDS.LOGIN_LOCATION_COUNT },
    { label: () => t('登录设备数'), field: LOGIN_STAT_FIELDS.LOGIN_DEVICE_COUNT },
    { label: () => `${t('登录IP')}${t('数')}`, field: LOGIN_STAT_FIELDS.LOGIN_IP_COUNT },
  ];

  // ========== 登录记录明细列 ==========
  const loginDetailColumns = [
    { label: () => t('登录时间'), field: LOGIN_DETAIL_FIELDS.LOGIN_TIME, sort: true },
    { label: () => t('登录地点'), field: LOGIN_DETAIL_FIELDS.LOGIN_LOCATION, filter: true },
    { label: () => t('登录IP'), field: LOGIN_DETAIL_FIELDS.LOGIN_IP },
    { label: () => t('大区'), field: LOGIN_DETAIL_FIELDS.ZONE },
    { label: () => t('角色ID'), field: LOGIN_DETAIL_FIELDS.ROLE_ID },
    { label: () => t('角色名称'), field: LOGIN_DETAIL_FIELDS.ROLE_NAME },
    { label: () => t('等级'), field: LOGIN_DETAIL_FIELDS.LEVEL },
    { label: () => t('登录设备'), field: LOGIN_DETAIL_FIELDS.LOGIN_DEVICE, filter: true },
    { label: () => t('机型'), field: LOGIN_DETAIL_FIELDS.DEVICE_MODEL, filter: true },
  ];

  // ========== 赠送记录明细列 ==========
  const giveDetailColumns = [
    { label: () => t('赠送对象'), field: GIFT_DETAIL_FIELDS.TARGET_OPENID },
    { label: () => t('昵称'), field: GIFT_DETAIL_FIELDS.NICKNAME },
    { label: () => t('是否员工'), field: GIFT_DETAIL_FIELDS.IS_EMPLOYEE, filter: true },
    { label: () => t('赠送时间'), field: GIFT_DETAIL_FIELDS.TIME, sort: true },
    { label: () => t('大区'), field: GIFT_DETAIL_FIELDS.ZONE },
    { label: () => `${t('道具')} ID`, field: GIFT_DETAIL_FIELDS.ITEM_ID },
    { label: () => t('道具名称'), field: GIFT_DETAIL_FIELDS.ITEM_NAME },
    { label: () => `${t('赠送总额')}(${t('元')})`, field: GIFT_DETAIL_FIELDS.GIFT_AMOUNT, sort: true },
    { label: () => `${t('赠送单价')}(${t('元')})`, field: GIFT_DETAIL_FIELDS.GIFT_UNIT_PRICE, sort: true },
    { label: () => t('赠送数量'), field: GIFT_DETAIL_FIELDS.ITEM_COUNT, sort: true },
  ];

  // ========== 交易记录明细列 ==========
  const dealDetailColumns = [
    { label: () => t('交易对象'), field: TRADE_DETAIL_FIELDS.TRADE_TARGET },
    { label: () => t('昵称'), field: TRADE_DETAIL_FIELDS.NICKNAME },
    { label: () => t('是否员工'), field: TRADE_DETAIL_FIELDS.IS_EMPLOYEE },
    { label: () => t('交易时间'), field: TRADE_DETAIL_FIELDS.TRADE_TIME, sort: true },
    { label: () => t('大区'), field: TRADE_DETAIL_FIELDS.ZONE_ID },
    { label: () => t('道具ID'), field: TRADE_DETAIL_FIELDS.ITEM_ID },
    { label: () => t('道具名称'), field: TRADE_DETAIL_FIELDS.ITEM_NAME },
    { label: () => `${t('交易总额')}(${t('元')})`, field: TRADE_DETAIL_FIELDS.TRADE_AMOUNT, sort: true },
    { label: () => `${t('交易单价')}(${t('元')})`, field: TRADE_DETAIL_FIELDS.TRADE_UNIT_PRICE, sort: true },
    { label: () => t('交易数量'), field: TRADE_DETAIL_FIELDS.TRADE_COUNT, sort: true },
  ];

  // ========== 代币发放记录明细列 ==========
  const sapDetailColumns = [
    {
      label: () => t('发放时间'),
      field: COIN_DETAIL_FIELDS.ISSUE_TIME,
      sort: true,
      render: ({ data }: { data: Record<string, any> }) => formatIsoDateTime(data?.[COIN_DETAIL_FIELDS.ISSUE_TIME]),
    },
    { label: () => t('发放人'), field: COIN_DETAIL_FIELDS.ISSUER },
    { label: () => t('大区'), field: COIN_DETAIL_FIELDS.ZONE },
    { label: () => t('发放数量'), field: COIN_DETAIL_FIELDS.ISSUE_COUNT, sort: true },
    { label: () => `${t('发放金额')}(${t('元')})`, field: COIN_DETAIL_FIELDS.ISSUE_AMOUNT, sort: true },
    { label: () => t('操作原因'), field: COIN_DETAIL_FIELDS.OPERATION_REASON },
    { label: () => t('需求类型'), field: COIN_DETAIL_FIELDS.DEMAND_TYPE, filter: true },
    { label: () => t('需求来源'), field: COIN_DETAIL_FIELDS.DEMAND_SOURCE, filter: true },
  ];

  // ========== 聊天记录明细列 ==========
  const chatDetailColumns = [
    { label: () => t('发起方'), field: CHAT_DETAIL_FIELDS.SENDER },
    { label: () => t('接收方openid'), field: CHAT_DETAIL_FIELDS.RECEIVER_OPENID },
    { label: () => t('接收方昵称'), field: CHAT_DETAIL_FIELDS.RECEIVER_NICKNAME },
    { label: () => t('聊天时间'), field: CHAT_DETAIL_FIELDS.CHAT_TIME, sort: true },
    { label: () => t('聊天内容'), field: CHAT_DETAIL_FIELDS.CHAT_CONTENT },
    { label: () => t('大区'), field: CHAT_DETAIL_FIELDS.ZONE_ID },
    { label: () => t('是否员工'), field: CHAT_DETAIL_FIELDS.IS_EMPLOYEE, filter: true },
    { label: () => t('信息类型'), field: CHAT_DETAIL_FIELDS.MESSAGE_TYPE, filter: true },
  ];

  return {
    roleColumns,
    loginStatColumns,
    loginDetailColumns,
    giveDetailColumns,
    dealDetailColumns,
    sapDetailColumns,
    chatDetailColumns,
  };
};
