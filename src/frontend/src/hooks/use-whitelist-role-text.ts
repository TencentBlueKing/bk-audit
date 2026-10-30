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

const readRoles = () => {
  try {
    const roles = JSON.parse(sessionStorage.getItem('userRole') || '[]');
    return Array.isArray(roles) ? roles.map(item => String(item)) : [];
  } catch {
    return [];
  }
};

/**
 * 管理员（saas_admin / scene_admin）与处理人、场景用户的加白文案。
 * 同时拥有管理员角色时走管理员文案。
 */
export default function useWhitelistRoleText() {
  const isAdmin = computed(() => {
    const roles = readRoles();
    return roles.includes('saas_admin') || roles.includes('scene_admin');
  });
  const text = computed(() => (isAdmin.value
    ? {
      method: '加入白名单',
      together: '同时加入白名单',
      confirmTitle: '确定加入白名单？',
      confirmOk: '确定加白',
      misreportAlertTail: '请同时加入白名单',
      misreportSuccess: '已标记误报，白名单已生效',
      applySuccess: '白名单已生效',
      applyHint: '提交后工单进入加白审批中，场景管理员通过后生效并关单。',
    }
    : {
      method: '申请加白',
      together: '同时申请加白',
      confirmTitle: '确认提交加白申请？',
      confirmOk: '提交申请',
      misreportAlertTail: '请同时申请加白',
      misreportSuccess: '已标记误报，加白申请已提交',
      applySuccess: '加白申请已提交',
      applyHint: '提交后工单进入加白审批中，场景管理员通过后生效并关单。',
    }));
  return { isAdmin, text };
}
