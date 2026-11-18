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
import { computed } from 'vue';

import type { WhitelistType } from '@model/risk-whitelist/whitelist';

const readRoles = () => {
  try {
    const roles = JSON.parse(sessionStorage.getItem('userRole') || '[]');
    return Array.isArray(roles) ? roles.map(item => String(item)) : [];
  } catch {
    return [];
  }
};

/** 场景管理员自己发起会代审批，规则可直接生效；平台管理员走待审批。 */
const canDirectActivate = () => readRoles().includes('scene_admin');

/** 后端口径：误报加白会先误报关单；冒险加白等审批通过后再关单。 */
export const getWhitelistApplyHint = (type: WhitelistType, isAdmin: boolean) => {
  // 仅场景管理员代审批可直接生效，不展示待审批提示；平台管理员与普通人一致
  if (isAdmin && canDirectActivate()) return '';
  if (type === 'false_positive') {
    return '提交后将按误报关闭当前风险单，加白规则待场景管理员审批通过后生效。';
  }
  return '提交后工单进入加白审批中，场景管理员通过后生效并关单。';
};

export const getWhitelistApplySuccess = (type: WhitelistType, isAdmin: boolean) => {
  if (isAdmin && canDirectActivate()) {
    return type === 'false_positive'
      ? '已按误报关单，白名单已生效'
      : '白名单已生效';
  }
  return type === 'false_positive'
    ? '已按误报关单，加白申请已提交'
    : '加白申请已提交';
};

export const getWhitelistRiskCloseImpact = (type: WhitelistType, _isAdmin: boolean) => {
  if (type === 'false_positive') {
    return '当前风险单将按误报关闭。';
  }
  // 冒险加白：发起时不改风险单，审批通过后才关单（场景管理员代审批也属审批通过）
  return '审批通过后当前风险单将关闭。';
};

export const getWhitelistEffectImpact = (type: WhitelistType, isAdmin: boolean) => {
  if (isAdmin && canDirectActivate()) {
    return '白名单立即生效。后续命中该匹配范围的风险将不再生成新单，已有风险单不再追加事件。';
  }
  if (type === 'false_positive') {
    return '加白规则待审批通过后生效。后续命中该匹配范围的风险将不再生成新单，已有风险单不再追加事件。';
  }
  return '审批通过后白名单生效。后续命中该匹配范围的风险将不再生成新单，已有风险单不再追加事件。';
};

/**
 * 管理员（saas_admin / scene_admin）与处理人、场景用户的加白文案。
 * 同时拥有管理员角色时走管理员入口文案；是否「立即生效」以场景管理员为准。
 */
export default function useWhitelistRoleText() {
  const isAdmin = computed(() => {
    const roles = readRoles();
    return roles.includes('saas_admin') || roles.includes('scene_admin');
  });
  const isDirectActivate = computed(() => canDirectActivate());
  const text = computed(() => (isAdmin.value
    ? {
      method: '加入白名单',
      together: '同时加入白名单',
      confirmTitle: '确定加入白名单？',
      confirmOk: '确定加白',
      misreportAlertTail: '请同时加入白名单',
      misreportSuccess: isDirectActivate.value
        ? '已标记误报，白名单已生效'
        : '已标记误报，加白申请已提交',
      applySuccess: isDirectActivate.value
        ? '白名单已生效'
        : '加白申请已提交',
      applyHint: getWhitelistApplyHint('risk_acceptance', true),
    }
    : {
      method: '申请加白',
      together: '同时申请加白',
      confirmTitle: '确认提交加白申请？',
      confirmOk: '提交申请',
      misreportAlertTail: '请同时申请加白',
      misreportSuccess: '已标记误报，加白申请已提交',
      applySuccess: '加白申请已提交',
      applyHint: getWhitelistApplyHint('risk_acceptance', false),
    }));
  return { isAdmin, text };
}
