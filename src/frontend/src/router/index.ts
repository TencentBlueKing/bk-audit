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
  createRouter,
  createWebHistory,
  type RouteLocationNormalized,
  type RouteRecordRaw,
} from 'vue-router';

import IamManageService from '@service/iam-manage';
import RootManageService from '@service/root-manage';
import SceneManageService from '@service/scene-manage';

import type ConfigModel from '@model/root/config';

import NotFound from '@views/404.vue';
import AnalysisManage from '@views/analysis-manage/routes'; // 检索
import AttentionManage from '@views/attention-manege/routes'; // 我的关注
import ConfirmManage from '@views/confirm-manage/routes'; // 待我确认
import EventManage from '@views/event-manage/routes'; // 审计风险
import HandleManage from '@views/handle-manage/routes'; // 待我处理
import LinkDataManage from '@views/link-data-manage/routes'; // 联表管理
import NewSystemManage from '@views/new-system-manage/routes'; // 系统接入
import NoticeGroup from '@views/notice-group/routes'; // 通知组
import PlatformManage from '@views/platform-manage/routes'; // 平台管理
import ApplicationManage from '@views/process-application-manage/routes'; // 处理套餐
import ProcessedManage from '@views/processed-manage/routes'; // 处理历史
import RiskManage from '@views/risk-manage/routes'; // 所有风险
import RiskWhitelist from '@views/risk-whitelist/routes'; // 风险白名单
import RuleManage from '@views/rule-manage/routes'; // 处理规则
import SceneResources from '@views/scene-config/routes'; // 场景配置
import SceneRiskManage from '@views/scene-risk-manage/routes'; // 场景风险
import SecChat from '@views/sec-chat/routes'; // SecChat
import StatementManage from '@views/statement-manage/routes'; // 报表
import StorageManage from '@views/storage-manage/routes'; // 数据存储
import StrategyManage from '@views/strategy-manage/routes'; // 审计策略
import SystemManage from '@views/system-manage/routes'; // 系统列表
import Tools from '@views/tools/routes'; // 工具广场

import { changeConfirm } from '@utils/assist';

import { isSystemScopedContextQuery, setActiveSceneSelection } from '@/utils/assist/scene-system-params';


let lastRouterHrefCache = '/';

/** 场景配置引导页，不校验场景管理权限 */
const SCENE_CONFIG_LANDING_NAMES = new Set(['landingPage', 'userLandingPage']);

/** 单条访问限制规则 */
interface AccessRule {
  /** 受限路径前缀列表 */
  paths: string[];
  /** 拦截后重定向的路由 name */
  redirect: string;
  /** 当前路由 name 与此值相等时不拦截（用于 landing 页自身） */
  excludeName?: string;
}

/** 角色 -> 访问限制规则表（按优先级排列） */
const ROLE_ACCESS_MAP: Record<string, AccessRule[]> = {
  risk_handler: [
    { paths: ['/strategy-manage', '/link-data-manage', '/scene-config', '/application-manage', '/rule-manage', '/notice-group', '/risk-whitelist'], redirect: 'landingPage', excludeName: 'landingPage' },
    { paths: ['/nwe-system-manage', '/system-manage'], redirect: 'systemLandingPage', excludeName: 'systemLandingPage' },
    { paths: ['/analysis-manage', '/statement-manage', '/tools', '/platform'], redirect: '404' },
  ],
  scene_user: [
    { paths: ['/strategy-manage', '/link-data-manage', '/scene-config', '/application-manage', '/rule-manage', '/notice-group', '/risk-whitelist'], redirect: 'userLandingPage', excludeName: 'userLandingPage' },
    { paths: ['/nwe-system-manage', '/system-manage'], redirect: 'systemLandingPage', excludeName: 'systemLandingPage' },
    { paths: ['/platform'], redirect: '404' },
  ],
  scene_admin: [
    { paths: ['/nwe-system-manage', '/system-manage'], redirect: 'systemLandingPage', excludeName: 'systemLandingPage' },
    { paths: ['/platform'], redirect: '404' },
  ],
  system_admin: [
    { paths: ['/strategy-manage', '/link-data-manage', '/scene-config', '/application-manage', '/rule-manage', '/notice-group', '/risk-whitelist'], redirect: 'userLandingPage', excludeName: 'userLandingPage' },
    { paths: ['/statement-manage', '/tools', '/platform'], redirect: '404' },
  ],
};

/**
 * 选择器里没有可使用场景、也没有系统权限时，
 * 工具广场、日志检索、报表带具体场景才去申请页。
 */
const SCENE_APPLY_PATHS = ['/tools', '/analysis-manage', '/statement-manage'];

const firstQueryValue = (value: unknown) => {
  if (Array.isArray(value)) {
    return value[0] ? String(value[0]) : '';
  }
  if (value === undefined || value === null || value === '') {
    return '';
  }
  return String(value);
};

const isIntegerSceneId = (value: string) => /^[1-9]\d*$/.test(value);

/**
 * 申请页只接受整数场景 ID。
 * scope_type=system 时 scene_id / scope_id 都是系统 ID，不能拿去申请场景。
 */
const getConcreteSceneId = (to: RouteLocationNormalized) => {
  const scopeType = firstQueryValue(to.query.scope_type);
  if (scopeType === 'system' || scopeType === 'cross_system' || scopeType === 'cross_scene') {
    return '';
  }
  const sceneId = firstQueryValue(to.query.scene_id);
  if (isIntegerSceneId(sceneId)) {
    return sceneId;
  }
  const scopeId = firstQueryValue(to.query.scope_id);
  if ((scopeType === 'scene' || scopeType === '') && isIntegerSceneId(scopeId)) {
    return scopeId;
  }
  return '';
};

/**
 * 根据规则检查目标路径是否被拦截
 * @returns 需重定向的路由 name，null 表示放行
 */
function checkAccessRedirect(
  toPath: string,
  toName: string | symbol | undefined | null,
  rules: AccessRule[],
): string | null {
  for (const rule of rules) {
    const matched = rule.paths.some(p => toPath.startsWith(p));
    const excluded = rule.excludeName ? toName === rule.excludeName : false;
    if (matched && !excluded) return rule.redirect;
  }
  return null;
}

/**
 * 判断是否进入场景配置业务页（不含引导页）
 * 风险白名单虽挂在场景配置导航下，但有独立权限校验，不走场景配置分享链接分流
 */
function isSceneConfigBusinessRoute(to: RouteLocationNormalized) {
  if (SCENE_CONFIG_LANDING_NAMES.has(String(to.name || ''))) {
    return false;
  }
  if (to.path.startsWith('/risk-whitelist')) {
    return false;
  }
  return to.path.startsWith('/scene-config')
    || to.matched.some(record => record.meta?.navName === 'sceneConfiguration');
}

/** 分享链接 / 地址栏直开（SPA 首次导航，无上一页路由记录） */
function isSharedLinkEntry(from: RouteLocationNormalized) {
  return !from.name && from.matched.length === 0;
}

const buildSceneContextQuery = (sceneId: string) => ({
  scene_id: sceneId,
  scope_id: sceneId,
  scope_type: 'scene',
});

const persistSceneSelection = (sceneId: string) => {
  const selection = { id: sceneId, type: 'scene' as const };
  setActiveSceneSelection(selection);
  localStorage.setItem('scene-system-selector:selected', JSON.stringify(selection));
};

const readManagePlatform = () => {
  try {
    const permission = JSON.parse(sessionStorage.getItem('userScenePermission') || '{}');
    return permission.manage_platform === true;
  } catch {
    return false;
  }
};

/**
 * 场景配置页进入前权限分流：
 * - manage_platform / 当前场景 manage_scene=true：放行
 * - 无 scene_id：自动落到第一个可管理场景；一个都没有则进引导/申请页
 * - 仅 view_scene + 分享链接进入：跳转 user-landing-page 申请
 * - 仅 view_scene + 应用内其他模块进入：改选第一个有管理权限的场景并放行
 */
async function resolveSceneConfigSceneAccess(
  to: RouteLocationNormalized,
  from: RouteLocationNormalized,
) {
  if (!isSceneConfigBusinessRoute(to)) {
    return null;
  }

  // 系统范围的 scene_id 是系统 id。不在这里鉴权，也不改写全局选中，交给选择器按原兜底处理。
  if (isSystemScopedContextQuery(to.query)) {
    return null;
  }

  const urlSceneId = (to.query.scene_id || to.query.scope_id) as string | undefined;
  let sceneId = urlSceneId;
  if (!sceneId || sceneId === 'allSecen') {
    try {
      const saved = JSON.parse(localStorage.getItem('scene-system-selector:selected') || 'null');
      if (saved?.type === 'scene' && saved?.id && saved.id !== 'allSecen') {
        sceneId = String(saved.id);
      }
    } catch {
      // ignore
    }
  }

  try {
    const sceneList = await SceneManageService.fetchSceneAll({ status: 'enabled' });
    const firstManageable = (sceneList || []).find(item => item.permission?.manage_scene === true);
    const redirectToManageable = (manageableSceneId: string) => {
      persistSceneSelection(manageableSceneId);
      return {
        path: to.path,
        query: {
          ...to.query,
          ...buildSceneContextQuery(manageableSceneId),
        },
        hash: to.hash,
        replace: true,
      };
    };

    // 地址 / 缓存都没有可用场景：落到第一个可管理场景，否则进引导页
    if (!sceneId || sceneId === 'allSecen') {
      if (firstManageable) {
        return redirectToManageable(String(firstManageable.scene_id));
      }
      const firstViewable = (sceneList || []).find(item => item.permission?.view_scene === true);
      if (firstViewable) {
        return {
          name: 'userLandingPage',
          query: buildSceneContextQuery(String(firstViewable.scene_id)),
        };
      }
      return {
        name: 'permissionsPage',
        query: { role: 'manager' },
      };
    }

    const redirectQuery = buildSceneContextQuery(String(sceneId));
    const target = (sceneList || []).find(item => String(item.scene_id) === String(sceneId));
    const permission = target?.permission || {};

    if (permission.manage_scene === true || readManagePlatform()) {
      persistSceneSelection(String(sceneId));
      return null;
    }

    if (permission.view_scene === true) {
      if (isSharedLinkEntry(from)) {
        return {
          name: 'userLandingPage',
          query: redirectQuery,
        };
      }

      if (firstManageable) {
        return redirectToManageable(String(firstManageable.scene_id));
      }

      return {
        name: 'userLandingPage',
        query: redirectQuery,
      };
    }

    return {
      name: 'permissionsPage',
      query: {
        ...redirectQuery,
        role: 'manager',
      },
    };
  } catch {
    // 列表拉取失败时也拦截，避免页面先打业务接口弹出权限申请窗
  }

  return {
    name: 'permissionsPage',
    query: {
      ...(sceneId && sceneId !== 'allSecen' ? buildSceneContextQuery(String(sceneId)) : {}),
      role: 'manager',
    },
  };
}

export default (config: ConfigModel) => {
  const routes: Array<RouteRecordRaw> = [
    {
      // redirect 放到空 path 子路由，避免子页懒加载失败时被父级 `/` redirect 带到待我处理
      path: '/',
      children: [
        {
          path: '',
          redirect: {
            name: 'handleManage',
          },
        },
        AttentionManage,
        AnalysisManage,
        SystemManage,
        StrategyManage,
        LinkDataManage,
        EventManage,
        NoticeGroup,
        RiskWhitelist,
        RiskManage,
        ProcessedManage,
        HandleManage,
        ApplicationManage,
        RuleManage,
        StatementManage,
        Tools,
        NewSystemManage,
        PlatformManage,
        SceneResources,
        SceneRiskManage,
        SecChat,
        ConfirmManage,
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      name: '404',
      component: NotFound,
    },
    {
      path: '/permissions-page',
      component: () => import('@views/scene-config/permissions-page/index.vue'),
      name: 'permissionsPage',
      meta: {
        title: '申请权限',
        nodeSideContent: true,
      },
    },
  ];

  // 注册 super_manager 权限路由
  if (config.super_manager) {
    routes[0].children?.push(StorageManage);
  }
  const router =  createRouter({
    history: createWebHistory(import.meta.env.AUDIT_VITE_BUILD_BASE_DIR),
    routes,
  });

  // 全局前置守卫（统一处理所有路由跳转）
  router.beforeEach(async (to, from, next) => {
    try {
      const userRole = JSON.parse(sessionStorage.getItem('userRole') || '["risk_handler"]') as string[];

      // 场景角色（scene_user / scene_admin）可访问报表和工具，不受其他角色限制
      const hasSceneRole = userRole.some(r => r === 'scene_user' || r === 'scene_admin');
      // 包含 system_admin 或 saas_admin 时可访问系统管理页面
      const hasSystemOrSaasAdmin = userRole.includes('system_admin') || userRole.includes('saas_admin');

      // 从 systemLanding页 发起的子路由跳转应放行（如接入新系统、选择已有系统）
      const fromSystemLanding = (from.name as string) === 'systemLandingPage';
      const toChildOfNewSystem = to.path.startsWith('/nwe-system-manage');
      const concreteSceneId = getConcreteSceneId(to);

      if (
        (hasSceneRole && ['/statement-manage', '/tools'].some(p => to.path.startsWith(p)))
        || (hasSystemOrSaasAdmin && ['/nwe-system-manage', '/system-manage'].some(p => to.path.startsWith(p)))
        || (fromSystemLanding && toChildOfNewSystem)
      ) {
        // 放行，继续后续检查
      } else if (
        userRole.includes('risk_handler')
        && !hasSceneRole
        && !hasSystemOrSaasAdmin
        && concreteSceneId
        && SCENE_APPLY_PATHS.some(path => to.path.startsWith(path))
      ) {
        next({
          name: 'permissionsPage',
          query: {
            role: 'user',
            scene_id: concreteSceneId,
          },
        });
        return;
      } else {
        // 基于角色策略表进行访问控制
        // saas_admin / scene_admin 可进场景配置业务页（含 /risk-whitelist）；
        // 同账号常兼有 risk_handler，不能再被其 landingPage / userLandingPage 规则踢走
        const hasAdminPrivilege = userRole.includes('saas_admin') || userRole.includes('scene_admin');
        for (const role of userRole) {
          let rules = ROLE_ACCESS_MAP[role];
          if (!rules) continue;
          if (hasAdminPrivilege) {
            rules = rules.filter(r => (
              r.redirect !== 'userLandingPage' && r.redirect !== 'landingPage'
            ));
          }
          const redirect = checkAccessRedirect(to.path, to.name, rules);
          if (redirect) {
            next({ name: redirect });
            return;
          }
        }
      }

      // 检查权限：如果路由需要权限且用户没有权限，则重定向到首页
      // 平台管理（manage_platform）走 my_role_permissions，其余仍走 IAM check
      if (to.meta?.permission) {
        const permission = to.meta.permission as string;
        let allowed = false;
        if (permission === 'manage_platform') {
          const rolePermission = await RootManageService.getUserPermission();
          allowed = Boolean(rolePermission.manage_platform);
        } else {
          const hasPermission = await IamManageService.checkAny({ action_ids: permission });
          allowed = Boolean(hasPermission[permission]);
        }
        if (!allowed) {
          next({ name: 'handleManage' });
          return;
        }
      }

      // 场景配置业务页：URL 场景仅使用权限时，按进入方式分流
      const sceneConfigRedirect = await resolveSceneConfigSceneAccess(to, from);
      if (sceneConfigRedirect) {
        next(sceneConfigRedirect);
        return;
      }

      // 离开确认取消会 reject，不能进外层 catch，否则首屏 next(false) 可能回退到 /
      let confirmed = true;
      try {
        confirmed = await changeConfirm({ route: from, router });
      } catch {
        confirmed = false;
      }
      if (confirmed) {
        lastRouterHrefCache = to.fullPath;
        next();
      } else {
        next(false);
      }
    } catch (error) {
      // 首屏导航失败时 next(false) 会把地址回成 /，再被父级 redirect 到待我处理
      if (isSharedLinkEntry(from) && to.fullPath && to.fullPath !== '/') {
        lastRouterHrefCache = to.fullPath;
        next();
        return;
      }
      next(false);
    }
  });

  router.onError((error: any) => {
    const message = String(error?.message || '');
    if (!/Failed to fetch dynamically imported module|error loading dynamically imported module/i.test(message)) {
      return;
    }
    // 懒加载失败时：优先回到本次导航目标，避免被根路径 redirect 吞进待我处理
    const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    const fallback = (lastRouterHrefCache && lastRouterHrefCache !== '/')
      ? lastRouterHrefCache
      : current;
    if (fallback && fallback !== '/' && !fallback.startsWith('/handle-manage')) {
      window.location.replace(fallback);
      return;
    }
    if (current && current !== '/') {
      window.location.reload();
      return;
    }
    window.location.reload();
  });

  return router;
};
