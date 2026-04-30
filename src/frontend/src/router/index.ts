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
  type RouteRecordRaw,
} from 'vue-router';

import IamManageService from '@service/iam-manage';

import type ConfigModel from '@model/root/config';

import NotFound from '@views/404.vue';
import AnalysisManage from '@views/analysis-manage/routes'; // 检索
import AttentionManage from '@views/attention-manege/routes'; // 我的关注
import EventManage from '@views/event-manage/routes'; // 审计风险
import HandleManage from '@views/handle-manage/routes'; // 待我处理
import LinkDataManage from '@views/link-data-manage/routes'; // 联表管理
import NewSystemManage from '@views/new-system-manage/routes'; // 系统接入
import NoticeGroup from '@views/notice-group/routes'; // 通知组
import PlatformManage from '@views/platform-manage/routes'; // 平台管理
import ApplicationManage from '@views/process-application-manage/routes'; // 处理套餐
import ProcessedManage from '@views/processed-manage/routes'; // 处理历史
import RiskManage from '@views/risk-manage/routes'; // 所有风险
import RuleManage from '@views/rule-manage/routes'; // 处理规则
import SceneResources from '@views/scene-config/routes'; // 场景配置
import SceneRiskManage from '@views/scene-risk-manage/routes'; // 场景风险
import StatementManage from '@views/statement-manage/routes'; // 报表
import StorageManage from '@views/storage-manage/routes'; // 数据存储
import StrategyManage from '@views/strategy-manage/routes'; // 审计策略
import SystemManage from '@views/system-manage/routes'; // 系统列表
import Tools from '@views/tools/routes'; // 工具广场

import { changeConfirm } from '@utils/assist';


let lastRouterHrefCache = '/';

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
    { paths: ['/strategy-manage', '/link-data-manage', '/scene-config', '/application-manage', '/rule-manage', '/notice-group'], redirect: 'landingPage', excludeName: 'landingPage' },
    { paths: ['/nwe-system-manage', '/system-manage'], redirect: 'systemLandingPage', excludeName: 'systemLandingPage' },
    { paths: ['/analysis-manage', '/statement-manage', '/tools', '/platform'], redirect: '404' },
  ],
  scene_user: [
    { paths: ['/strategy-manage', '/link-data-manage', '/scene-config', '/application-manage', '/rule-manage', '/notice-group'], redirect: 'userLandingPage', excludeName: 'userLandingPage' },
    { paths: ['/nwe-system-manage', '/system-manage'], redirect: 'systemLandingPage', excludeName: 'systemLandingPage' },
  ],
  scene_admin: [
    { paths: ['/nwe-system-manage', '/system-manage'], redirect: 'systemLandingPage', excludeName: 'systemLandingPage' },
  ],
  system_admin: [
    { paths: ['/strategy-manage', '/link-data-manage', '/scene-config', '/application-manage', '/rule-manage', '/notice-group'], redirect: 'userLandingPage', excludeName: 'userLandingPage' },
  ],
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

export default (config: ConfigModel) => {
  const routes: Array<RouteRecordRaw> = [
    {
      path: '/',
      redirect: {
        name: 'handleManage',
      },
      children: [
        AttentionManage,
        AnalysisManage,
        SystemManage,
        StrategyManage,
        LinkDataManage,
        EventManage,
        NoticeGroup,
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
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      name: '404',
      component: NotFound,
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

      // 基于角色策略表进行访问控制
      for (const role of userRole) {
        const rules = ROLE_ACCESS_MAP[role];
        if (!rules) continue;
        const redirect = checkAccessRedirect(to.path, to.name, rules);
        if (redirect) {
          next({ name: redirect });
          return;
        }
      }

      // 检查权限：如果路由需要权限且用户没有权限，则重定向到首页
      if (to.meta?.permission) {
        const permission = to.meta.permission as string;
        const hasPermission = await IamManageService.checkAny({ action_ids: permission });

        if (!hasPermission[permission]) {
          next({ name: 'handleManage' });
          return;
        }
      }

      // 显示确认弹窗
      const confirmed = await changeConfirm();
      if (confirmed) {
        lastRouterHrefCache = to.fullPath;
        next();
      } else {
        next(false);
      }
    } catch (error) {
      next(false);
    }
  });

  router.onError((error: any) => {
    if (/Failed to fetch dynamically imported module/.test(error.message)) {
      window.location.href = lastRouterHrefCache;
    }
  });

  return router;
};
