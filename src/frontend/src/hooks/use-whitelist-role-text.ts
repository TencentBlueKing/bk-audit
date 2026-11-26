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
import {
  computed,
  type MaybeRefOrGetter,
  toValue,
} from 'vue';

import type { WhitelistType } from '@model/risk-whitelist/whitelist';

import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

type SceneListItem = {
  id?: string | number;
  scene_id?: string | number;
  permission?: {
    manage_scene?: boolean;
  };
};

const readManagePlatform = () => {
  try {
    const permission = JSON.parse(sessionStorage.getItem('userScenePermission') || '{}');
    return permission.manage_platform === true;
  } catch {
    return false;
  }
};

const readCachedSceneList = (): SceneListItem[] => {
  try {
    const list = JSON.parse(localStorage.getItem('scene-system-selector:sceneList') || '[]');
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
};

const normalizeSceneId = (sceneId?: string | number | null) => {
  const value = String(sceneId ?? '').trim();
  return value || '';
};

const resolveSceneId = (sceneId?: string | number | null) => {
  const explicit = normalizeSceneId(sceneId);
  if (explicit) return explicit;
  return normalizeSceneId(getSceneSystemParams().scope_id);
};

/**
 * 与白名单菜单一致：平台管理员，或「指定场景」具备 manage_scene。
 * 不再用全局 userRole.scene_admin（任意场景管理权都会误判）。
 */
const canManageTargetScene = (sceneId?: string | number | null) => {
  if (readManagePlatform()) return true;
  const targetId = normalizeSceneId(sceneId);
  if (!targetId) return false;
  const current = readCachedSceneList().find(item => (
    String(item.id ?? '') === targetId || String(item.scene_id ?? '') === targetId
  ));
  return current?.permission?.manage_scene === true;
};

/**
 * 管理员（平台/该场景）发起时规则可直接生效。
 * 验收口径：管理员确认后立即生效/关单，确认框不得再提示「待审批」。
 */
const canDirectActivate = (sceneId?: string | number | null) => (
  canManageTargetScene(resolveSceneId(sceneId))
);

/** 后端口径：误报加白会先误报关单；非管理员冒险加白等审批通过后再关单。 */
export const getWhitelistApplyHint = (type: WhitelistType, isAdmin: boolean) => {
  // isAdmin 由调用方按「平台 / 该场景」判权后传入
  if (isAdmin) return '';
  if (type === 'false_positive') {
    return '提交后将按误报关闭当前风险单，加白规则待场景管理员审批通过后生效。';
  }
  return '提交后工单进入加白审批中，场景管理员通过后生效并关单。';
};

export const getWhitelistApplySuccess = (type: WhitelistType, isAdmin: boolean) => {
  if (isAdmin) {
    return type === 'false_positive'
      ? '已按误报关单，白名单已生效'
      : '白名单已生效';
  }
  return type === 'false_positive'
    ? '已按误报关单，加白申请已提交'
    : '加白申请已提交';
};

export const getWhitelistRiskCloseImpact = (type: WhitelistType, isAdmin: boolean) => {
  if (type === 'false_positive') {
    return '当前风险单将按误报关闭。';
  }
  if (isAdmin) {
    return '确认后当前风险单将立即关闭。';
  }
  return '审批通过后当前风险单将关闭。';
};

export const getWhitelistEffectImpact = (type: WhitelistType, isAdmin: boolean) => {
  if (isAdmin) {
    return '确认后立即生效。后续命中该匹配范围的风险将不再生成新单，已有风险单不再追加事件。';
  }
  if (type === 'false_positive') {
    return '加白规则待审批通过后生效。后续命中该匹配范围的风险将不再生成新单，已有风险单不再追加事件。';
  }
  return '审批通过后白名单生效。后续命中该匹配范围的风险将不再生成新单，已有风险单不再追加事件。';
};

/** 风险单冒险加白 + 管理员：合并关单与生效说明 */
export const getWhitelistAdventureAdminImpact = () => (
  '确认后立即关单并生效。后续命中该匹配范围的风险将不再生成新单，已有风险单不再追加事件。'
);

/**
 * 管理员与处理人、场景用户的加白文案。
 * 是否管理员 / 立即生效：按「平台管理员或该场景 manage_scene」判定（与菜单一致）。
 * sceneId 优先用调用方传入（风险所属场景）；未传时回落到当前场景选择器。
 */
export default function useWhitelistRoleText(
  sceneId?: MaybeRefOrGetter<string | number | null | undefined>,
) {
  const resolvedSceneId = computed(() => resolveSceneId(toValue(sceneId)));
  const isAdmin = computed(() => canManageTargetScene(resolvedSceneId.value));
  const isDirectActivate = computed(() => canDirectActivate(resolvedSceneId.value));
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
