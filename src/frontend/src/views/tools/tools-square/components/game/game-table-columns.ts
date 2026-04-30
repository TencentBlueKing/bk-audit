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

/**
 * 创建所有游戏详情页的表格列配置
 */
export const useGameTableColumns = () => {
  const { t } = useI18n();

  // ========== 概览 - 角色总览列 ==========
  const roleColumns = [
    { label: () => t('角色名称'), field: '角色名称' },
    { label: () => t('角色ID'), field: '角色ID' },
    { label: () => t('平台'), field: '平台' },
    { label: () => t('大区'), field: '大区' },
    { label: () => `${t('登录地点数')}/${t('月')}`, field: '登录地点（月）', sort: true },
    { label: () => `${t('登录地点数')}/${t('年')}`, field: '登录地点（年）', sort: true },
    { label: () => `${t('登录次数')}/${t('月')}`, field: '登录次数（月）', sort: true },
    { label: () => `${t('登录次数')}/${t('年')}`, field: '登录次数（年）', sort: true },
    { label: () => `${t('交易对象数')}/${t('月')}`, field: '交易对象（月）', sort: true },
    { label: () => `${t('交易对象数')}/${t('年')}`, field: '交易对象（年）', sort: true },
  ];

  // ========== 概览 - 登录统计列 ==========
  const loginStatColumns = [
    { label: () => t('统计频率'), field: 'days_class' },
    { label: () => t('登录次数'), field: '登录次数', sort: true },
    { label: () => t('登录地点数'), field: '登录地点数', sort: true },
    { label: () => t('登录设备数'), field: '登录设备数', sort: true },
    { label: () => `${t('登录IP')}${t('数')}`, field: '登录IP数', sort: true },
  ];

  // ========== 登录记录明细列 ==========
  const loginDetailColumns = [
    { label: () => t('登录时间'), field: '登录时间', sort: true },
    { label: () => t('登录地点'), field: '登录地点', filter: true },
    { label: () => t('登录IP'), field: '登录IP' },
    { label: () => t('大区'), field: '大区' },
    { label: () => t('角色ID'), field: '角色ID' },
    { label: () => t('角色名称'), field: '角色名称' },
    { label: () => t('等级'), field: '等级' },
    { label: () => t('登录设备'), field: '登录设备', filter: true },
    { label: () => t('机型'), field: '机型', filter: true },
  ];

  // ========== 赠送记录明细列 ==========
  const giveDetailColumns = [
    { label: () => t('赠送对象'), field: '对方openid' },
    { label: () => t('昵称'), field: '昵称' },
    { label: () => t('是否员工'), field: '是否员工' },
    { label: () => t('赠送时间'), field: '时间', sort: true },
    { label: () => t('大区'), field: '大区' },
    { label: () => t('道具ID'), field: '道具id' },
    { label: () => t('道具名称'), field: '道具名称' },
    { label: () => `${t('赠送总额')}(${t('元')})`, field: '赠送金额', sort: true },
    { label: () => `${t('赠送单价')}(${t('元')})`, field: '赠送单价', sort: true },
    { label: () => t('赠送数量'), field: '道具数量', sort: true },
    { label: () => t('赠送次数'), field: '赠送次数', sort: true },
  ];

  // ========== 交易记录明细列 ==========
  const dealDetailColumns = [
    { label: () => t('交易对象'), field: '交易对象' },
    { label: () => t('昵称'), field: '昵称' },
    { label: () => t('是否员工'), field: '是否员工' },
    { label: () => t('交易时间'), field: '交易时间', sort: true },
    { label: () => t('大区'), field: '大区ID' },
    { label: () => t('道具ID'), field: '道具id' },
    { label: () => t('道具名称'), field: '道具名称' },
    { label: () => `${t('交易总额')}(${t('元')})`, field: '交易总额', sort: true },
    { label: () => `${t('交易单价')}(${t('元')})`, field: '交易单价', sort: true },
    { label: () => t('交易数量'), field: '交易数量', sort: true },
    { label: () => t('交易次数'), field: '交易次数', sort: true },
  ];

  // ========== 代币发放记录明细列 ==========
  const sapDetailColumns = [
    { label: () => t('发放时间'), field: '发放时间', sort: true },
    { label: () => t('发放人'), field: '发放人' },
    { label: () => t('大区'), field: '大区' },
    { label: () => t('发放数量'), field: '发放数量', sort: true },
    { label: () => `${t('发放金额')}(${t('元')})`, field: '发放金额（元）', sort: true },
    { label: () => t('操作原因'), field: '操作原因' },
    { label: () => t('需求类型'), field: '需求类型', filter: true },
    { label: () => t('需求来源'), field: '需求来源', filter: true },
  ];

  // ========== 聊天记录明细列 ==========
  const chatDetailColumns = [
    { label: () => t('发起方'), field: '发起方' },
    { label: () => t('接收方openid'), field: '接收方openid' },
    { label: () => t('接收方昵称'), field: '接收方昵称' },
    { label: () => t('聊天时间'), field: '聊天时间', sort: true },
    { label: () => t('聊天内容'), field: '聊天内容' },
    { label: () => t('大区'), field: '大区ID' },
    { label: () => t('是否员工'), field: '是否员工', filter: true },
    { label: () => t('信息类型'), field: '信息类型', filter: true },
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
