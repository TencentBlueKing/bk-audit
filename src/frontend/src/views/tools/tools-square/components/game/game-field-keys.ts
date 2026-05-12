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

/**
 * 后端数据字段名映射常量
 * 用于统一管理后端接口返回数据中的中文字段名，避免中文字面量散落在代码中
 * 如果后端字段名变更，只需修改此文件即可
 */

// ========== 角色总览相关字段 ==========
export const ROLE_FIELDS = {
  ROLE_NAME: '角色名称',
  ROLE_ID: '角色ID',
  PLATFORM: '平台',
  ZONE: '大区',
  LOGIN_LOCATION_MONTH: '登录地点（月）',
  LOGIN_LOCATION_YEAR: '登录地点（年）',
  LOGIN_COUNT_MONTH: '登录次数（月）',
  LOGIN_COUNT_YEAR: '登录次数（年）',
  TRADE_TARGET_MONTH: '交易对象（月）',
  TRADE_TARGET_YEAR: '交易对象（年）',
  CHAT_TARGET_MONTH: '聊天对象（月）',
  CHAT_TARGET_YEAR: '聊天对象（年）',
  CHAT_COUNT_MONTH: '聊天数量（月）',
  CHAT_COUNT_YEAR: '聊天数量（年）',
  TRADE_COUNT_MONTH: '交易数量（月）',
  TRADE_COUNT_YEAR: '交易数量（年）',
} as const;

// ========== 登录统计相关字段 ==========
export const LOGIN_STAT_FIELDS = {
  DAYS_CLASS: 'days_class',
  LOGIN_COUNT: '登录次数',
  LOGIN_LOCATION_COUNT: '登录地点数',
  LOGIN_DEVICE_COUNT: '登录设备数',
  LOGIN_IP_COUNT: '登录IP数',
} as const;

// ========== 登录明细相关字段 ==========
export const LOGIN_DETAIL_FIELDS = {
  LOGIN_TIME: '登录时间',
  LOGIN_LOCATION: '登录地点',
  LOGIN_IP: '登录IP',
  ZONE: '大区',
  ROLE_ID: '角色ID',
  ROLE_NAME: '角色名称',
  LEVEL: '等级',
  LOGIN_DEVICE: '登录设备',
  DEVICE_MODEL: '机型',
} as const;

// ========== 赠送明细相关字段 ==========
export const GIFT_DETAIL_FIELDS = {
  TARGET_OPENID: '赠送对象',
  NICKNAME: '昵称',
  IS_EMPLOYEE: '是否员工(严格版1,10)',
  TIME: '赠送时间',
  ZONE: '大区',
  ITEM_ID: '道具ID',
  ITEM_NAME: '道具名称',
  GIFT_AMOUNT: '赠送总额（元）',
  GIFT_UNIT_PRICE: '赠送单价（元）',
  ITEM_COUNT: '赠送数量',
  GIFT_TIMES: '赠送次数',
} as const;

// ========== 交易明细相关字段 ==========
export const TRADE_DETAIL_FIELDS = {
  TRADE_TARGET: '交易对象',
  NICKNAME: '昵称',
  IS_EMPLOYEE: '是否员工',
  TRADE_TIME: '交易时间',
  ZONE_ID: '大区ID',
  ITEM_ID: '道具id',
  ITEM_NAME: '道具名称',
  TRADE_AMOUNT: '交易总额',
  TRADE_UNIT_PRICE: '交易单价',
  TRADE_COUNT: '交易数量',
  TRADE_TIMES: '交易次数',
  TRADE_TOTAL: '交易金额',
} as const;

// ========== 代币发放明细相关字段 ==========
export const COIN_DETAIL_FIELDS = {
  ISSUE_TIME: '发放时间',
  ISSUER: '发放人',
  ZONE: '大区',
  ISSUE_COUNT: '发放数量',
  ISSUE_AMOUNT: '发放金额（元）',
  ISSUE_AMOUNT_SHORT: '发放金额',
  OPERATION_REASON: '操作原因',
  DEMAND_TYPE: '需求类型',
  DEMAND_SOURCE: '需求来源',
} as const;

// ========== 聊天明细相关字段 ==========
export const CHAT_DETAIL_FIELDS = {
  SENDER: '发起方',
  RECEIVER_OPENID: '接收方openid',
  RECEIVER_NICKNAME: '接收方昵称',
  CHAT_TIME: '聊天时间',
  CHAT_CONTENT: '聊天内容',
  ZONE_ID: '大区ID',
  IS_EMPLOYEE: '是否员工',
  MESSAGE_TYPE: '信息类型',
  CHAT_TARGET: '聊天对象',
  INITIATOR: '发起人',
} as const;

// ========== 图表分组统计相关字段 ==========
export const CHART_FIELDS = {
  GROUP: '分组',
  DIMENSION: '维度',
  LOGIN_TOTAL: '登录总数',
  LOGIN_DEVICE: '登录设备',
  LOGIN_LOCATION: '登录地点',
  LOGIN_TIME_PERIOD: '登录时段',
  GIFT_TARGET: '赠送对象',
  GIFT_ITEM: '赠送道具',
  GIFT_AMOUNT_YUAN: '赠送金额（元）',
  TIMES: '次数',
  TRADE_TARGET: '交易对象',
  TRADE_ITEM: '交易道具',
  ISSUE_AMOUNT_YUAN: '发放金额（元）',
  DEMAND_TYPE: '需求类型',
  ISSUER: '发放人',
  DEMAND_SOURCE: '需求来源',
} as const;

// ========== 导出用户信息相关字段 ==========
export const EXPORT_USER_FIELDS = {
  GAME_NAME: '游戏名称',
  OPENID: 'openid',
  WECHAT: '微信',
  COIN_BALANCE: '代币存量',
  TOTAL_RECHARGE: '累计充值',
  TOTAL_GIFT: '累计赠送',
  TOTAL_ISSUE: '累计发放',
} as const;

// ========== 用户画像相关字段 ==========
export const PROFILE_FIELDS = {
  // 用户信息字段
  AVATAR: '头像',
  WECOM: '企业微信',
  USERNAME: '用户名',
  STATUS: '在职状态',
  DEPARTMENT: '部门',
  ACCOUNT_TYPE: '账号类型',
  ACCOUNT_LIST: '账号列表',
  RESPONSIBILITY_COUNT: '责任单数',
  RISK_LEVEL: '风险系数',
  // 游戏列表字段
  GAME_NAME: '游戏名称',
  COIN_BALANCE_UNIT: '代币存量（代）',
  TOTAL_RECHARGE_UNIT: '累计充值（代）',
  TOTAL_GIFT_YUAN: '累计赠送（¥）',
  TOTAL_ISSUE_YUAN: '累计发放（¥）',
  LOGIN_COUNT_MONTH: '登录次数/月',
  TOTAL_GIFT: '总支出',
  TOTAL_ISSUE: '总入账',
  TOTAL_BALANCE: '总余额',
  TOTAL_TOPUP: '总充值',
  PLATFORM_ACCOUNT: '平台账号',
  EXCHANGE_RATE: '人民币代币兑换比',
  // 账号宽表新增字段（main_openid_list 调整后返回）
  PLATFORM_ACCOUNT_TYPE: '平台账号类型',
  TOTAL_RECHARGE_YUAN: '总充值（元）',
  ACCOUNT_NATURE: '账号性质',
} as const;
