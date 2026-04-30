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

// 搜索字段配置接口
export interface SearchFieldItem {
  name: string;       // 显示名称
  id: string;         // 字段标识
  placeholder?: string;
  children?: Array<{ id: string; name: string }>;
  onlyRecommendChildren?: boolean;
  multiple?: boolean;
  conditions?: Array<{ id: string; name: string }>; // 字段级别操作符配置
}

/**
 * 创建所有游戏详情页的搜索字段配置
 */
export const useGameSearchFields = () => {
  const { t } = useI18n();

  // ========== 操作符配置 ==========
  // 文本类型默认操作符：包含
  const textConditions = [
    { id: 'like', name: t('包含') },
    { id: 'eq', name: t('等于') },
    { id: 'neq', name: t('不等于') },
    { id: 'in', name: 'IN' },
    { id: 'not_in', name: 'NOT IN' },
  ];
  // 数字类型默认操作符：等于
  const numberConditions = [
    { id: 'eq', name: t('等于') },
    { id: 'neq', name: t('不等于') },
    { id: 'gt', name: t('大于') },
    { id: 'lt', name: t('小于') },
    { id: 'gte', name: t('大于等于') },
    { id: 'lte', name: t('小于等于') },
    { id: 'in', name: 'IN' },
    { id: 'not_in', name: 'NOT IN' },
  ];
  // 枚举值类型默认操作符：等于（值为下拉选择）
  const enumConditions = [
    { id: 'eq', name: t('等于') },
    { id: 'neq', name: t('不等于') },
  ];

  // ========== 登录记录搜索字段 ==========
  const loginSearchFields: SearchFieldItem[] = [
    { id: '登录IP', name: t('登录IP'), placeholder: t('请输入登录IP'), conditions: textConditions },
    { id: '登录地点', name: t('登录地点'), placeholder: t('请输入登录地点，多个值之间用逗号分隔'), conditions: textConditions },
    { id: '大区', name: t('大区ID'), placeholder: t('请输入大区ID'), conditions: numberConditions },
    { id: '角色ID', name: t('角色ID'), placeholder: t('请输入角色ID'), conditions: numberConditions },
    { id: '角色名称', name: t('角色名'), placeholder: t('请输入角色名'), conditions: textConditions },
    { id: '等级', name: t('等级'), placeholder: t('请输入等级'), conditions: numberConditions },
    { id: '登录设备', name: t('登录设备'), placeholder: t('请输入登录设备'), conditions: textConditions },
    { id: '机型', name: t('机型'), placeholder: t('请输入机型'), conditions: textConditions },
  ];

  // ========== 赠送记录搜索字段 ==========
  const giftSearchFields: SearchFieldItem[] = [
    { id: '对方openid', name: t('赠送对象'), placeholder: t('请输入赠送对象openid'), conditions: textConditions },
    { id: '昵称', name: t('昵称'), placeholder: t('请输入昵称'), conditions: textConditions },
    { id: '是否员工', name: t('是否员工'), placeholder: t('请选择'), conditions: enumConditions,
      children: [{ id: '是', name: t('是') }, { id: '否', name: t('否') }], onlyRecommendChildren: true },
    { id: '大区', name: t('大区'), placeholder: t('请输入大区'), conditions: numberConditions },
    { id: '道具id', name: t('道具ID'), placeholder: t('请输入道具ID'), conditions: numberConditions },
    { id: '道具名称', name: t('道具名称'), placeholder: t('请输入道具名称'), conditions: textConditions },
    { id: '赠送金额', name: t('赠送总额'), placeholder: t('请输入赠送总额'), conditions: numberConditions },
    { id: '赠送单价', name: t('赠送单价'), placeholder: t('请输入赠送单价'), conditions: numberConditions },
    { id: '道具数量', name: t('赠送数量'), placeholder: t('请输入赠送数量'), conditions: numberConditions },
    { id: '赠送次数', name: t('赠送次数'), placeholder: t('请输入赠送次数'), conditions: numberConditions },
  ];

  // ========== 交易记录搜索字段 ==========
  const tradeSearchFields: SearchFieldItem[] = [
    { id: '交易对象', name: t('交易对象'), placeholder: t('请输入交易对象'), conditions: textConditions },
    { id: '昵称', name: t('昵称'), placeholder: t('请输入昵称'), conditions: textConditions },
    { id: '是否员工', name: t('是否员工'), placeholder: t('请选择'), conditions: enumConditions,
      children: [{ id: '是', name: t('是') }, { id: '否', name: t('否') }], onlyRecommendChildren: true },
    { id: '大区ID', name: t('大区'), placeholder: t('请输入大区ID'), conditions: numberConditions },
    { id: '道具id', name: t('道具ID'), placeholder: t('请输入道具ID'), conditions: numberConditions },
    { id: '道具名称', name: t('道具名称'), placeholder: t('请输入道具名称'), conditions: textConditions },
    { id: '交易总额', name: t('交易总额'), placeholder: t('请输入交易总额'), conditions: numberConditions },
    { id: '交易单价', name: t('交易单价'), placeholder: t('请输入交易单价'), conditions: numberConditions },
    { id: '交易数量', name: t('交易数量'), placeholder: t('请输入交易数量'), conditions: numberConditions },
    { id: '交易次数', name: t('交易次数'), placeholder: t('请输入交易次数'), conditions: numberConditions },
  ];

  // ========== 代币发放记录搜索字段 ==========
  const coinSearchFields: SearchFieldItem[] = [
    { id: '发放人', name: t('发放人'), placeholder: t('请输入发放人'), conditions: textConditions },
    { id: '大区', name: t('大区'), placeholder: t('请输入大区'), conditions: numberConditions },
    { id: '发放数量', name: t('发放数量'), placeholder: t('请输入发放数量'), conditions: numberConditions },
    { id: '发放金额（元）', name: t('发放金额'), placeholder: t('请输入发放金额'), conditions: numberConditions },
    { id: '操作原因', name: t('操作原因'), placeholder: t('请输入操作原因'), conditions: textConditions },
    { id: '需求类型', name: t('需求类型'), placeholder: t('请输入需求类型'), conditions: textConditions },
    { id: '需求来源', name: t('需求来源'), placeholder: t('请输入需求来源'), conditions: textConditions },
  ];

  // ========== 聊天记录搜索字段 ==========
  const chatSearchFields: SearchFieldItem[] = [
    { id: '发起方', name: t('发起方'), placeholder: t('请输入发起方'), conditions: textConditions },
    { id: '接收方openid', name: t('接收方openid'), placeholder: t('请输入接收方openid'), conditions: textConditions },
    { id: '接收方昵称', name: t('接收方昵称'), placeholder: t('请输入接收方昵称'), conditions: textConditions },
    { id: '聊天内容', name: t('聊天内容'), placeholder: t('请输入聊天内容'), conditions: textConditions },
    { id: '大区ID', name: t('大区'), placeholder: t('请输入大区ID'), conditions: numberConditions },
    { id: '是否员工', name: t('是否员工'), placeholder: t('请选择'), conditions: enumConditions,
      children: [{ id: '是', name: t('是') }, { id: '否', name: t('否') }], onlyRecommendChildren: true },
    { id: '信息类型', name: t('信息类型'), placeholder: t('请输入信息类型'), conditions: textConditions },
  ];

  return {
    textConditions,
    numberConditions,
    enumConditions,
    loginSearchFields,
    giftSearchFields,
    tradeSearchFields,
    coinSearchFields,
    chatSearchFields,
  };
};
