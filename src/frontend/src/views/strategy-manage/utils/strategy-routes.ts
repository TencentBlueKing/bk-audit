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
import type { RouteLocationNormalizedLoaded } from 'vue-router';

import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

export type StrategyRouteKind = 'list' | 'create' | 'edit' | 'clone' | 'upgrade';

export interface StrategyRouteNames {
  list: string;
  create: string;
  edit: string;
  clone: string;
  upgrade: string;
}

const SCENE_ROUTE_NAMES: StrategyRouteNames = {
  list: 'strategyList',
  create: 'strategyCreate',
  edit: 'strategyEdit',
  clone: 'strategyClone',
  upgrade: 'strategyUpgrade',
};

const PLATFORM_ROUTE_NAMES: StrategyRouteNames = {
  list: 'platformStrategyList',
  create: 'platformStrategyCreate',
  edit: 'platformStrategyEdit',
  clone: 'platformStrategyClone',
  upgrade: 'platformStrategyUpgrade',
};

const PLATFORM_ROUTE_NAME_SET = new Set(Object.values(PLATFORM_ROUTE_NAMES));

type RouteNameInput = string | symbol | null | undefined;

const toRouteName = (routeName: RouteNameInput): string => {
  if (typeof routeName === 'string') return routeName;
  return '';
};

export const isPlatformStrategyRoute = (routeName: RouteNameInput): boolean => (
  PLATFORM_ROUTE_NAME_SET.has(toRouteName(routeName))
);

export const getStrategyRouteNames = (route?: Pick<RouteLocationNormalizedLoaded, 'name' | 'meta'> | null): StrategyRouteNames => {
  const routeName = toRouteName(route?.name);
  if (isPlatformStrategyRoute(routeName) || route?.meta?.navName === 'platformManage') {
    return PLATFORM_ROUTE_NAMES;
  }
  return SCENE_ROUTE_NAMES;
};

export const isStrategyListRoute = (routeName: RouteNameInput): boolean => (
  [SCENE_ROUTE_NAMES.list, PLATFORM_ROUTE_NAMES.list].includes(toRouteName(routeName))
);

export const isStrategyCreateRoute = (routeName: RouteNameInput): boolean => (
  [SCENE_ROUTE_NAMES.create, PLATFORM_ROUTE_NAMES.create].includes(toRouteName(routeName))
);

export const isStrategyEditRoute = (routeName: RouteNameInput): boolean => (
  [SCENE_ROUTE_NAMES.edit, PLATFORM_ROUTE_NAMES.edit].includes(toRouteName(routeName))
);

export const isStrategyCloneRoute = (routeName: RouteNameInput): boolean => (
  [SCENE_ROUTE_NAMES.clone, PLATFORM_ROUTE_NAMES.clone].includes(toRouteName(routeName))
);

export const isStrategyUpgradeRoute = (routeName: RouteNameInput): boolean => (
  [SCENE_ROUTE_NAMES.upgrade, PLATFORM_ROUTE_NAMES.upgrade].includes(toRouteName(routeName))
);

/**
 * 列表/标签/创建提交共用的绑定作用域：
 * - 全局策略（平台）：binding_type=platform_binding，scene_id 为空
 * - 审计策略（场景）：binding_type=scene_binding，传当前 scene_id
 */
export const getStrategyBindingScope = (
  route?: Pick<RouteLocationNormalizedLoaded, 'name' | 'meta'> | null,
): {
  binding_type: 'platform_binding' | 'scene_binding';
  scene_id: string | number | null;
  isPlatform: boolean;
} => {
  const isPlatform = isPlatformStrategyRoute(route?.name) || route?.meta?.navName === 'platformManage';
  if (isPlatform) {
    return {
      binding_type: 'platform_binding',
      scene_id: null,
      isPlatform: true,
    };
  }
  const { scope_id: scopeId } = getSceneSystemParams();
  return {
    binding_type: 'scene_binding',
    scene_id: (scopeId === undefined || scopeId === null || scopeId === '') ? null : scopeId,
    isPlatform: false,
  };
};

/** 列表/标签等接口的作用域参数（兼容旧调用） */
export const getStrategyListScopeParams = (
  route?: Pick<RouteLocationNormalizedLoaded, 'name' | 'meta'> | null,
) => {
  const { binding_type: bindingType, scene_id: sceneId } = getStrategyBindingScope(route);
  return { binding_type: bindingType, scene_id: sceneId };
};
