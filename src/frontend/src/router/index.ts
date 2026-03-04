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
import AnalysisManage from '@views/analysis-manage/routes';
import AttentionManage from '@views/attention-manege/routes';
import EventManage from '@views/event-manage/routes';
import HandleManage from '@views/handle-manage/routes';
import LinkDataManage from '@views/link-data-manage/routes';
import NewSystemManage from '@views/new-system-manage/routes';
import NoticeGroup from '@views/notice-group/routes';
import ApplicationManage from '@views/process-application-manage/routes';
import ProcessedManage from '@views/processed-manage/routes';
import RiskManage from '@views/risk-manage/routes';
import RuleManage from '@views/rule-manage/routes';
import StatementManage from '@views/statement-manage/routes';
import StorageManage from '@views/storage-manage/routes';
import StrategyManage from '@views/strategy-manage/routes';
import SystemManage from '@views/system-manage/routes';
import Tools from '@views/tools/routes';

import { changeConfirm } from '@utils/assist';


let lastRouterHrefCache = '/';

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
      // 检查权限：如果路由需要权限且用户没有权限，则重定向到首页
      if (to.meta?.permission) {
        const permission = to.meta.permission as string;
        const hasPermission = await IamManageService.checkAny({ action_ids: permission });

        if (!hasPermission[permission]) {
          // 没有权限，重定向到首页
          next({ name: 'handleManage' });
          return;
        }
      }

      // 显示确认弹窗
      const confirmed = await changeConfirm();
      if (confirmed) {
        lastRouterHrefCache = to.fullPath;
        next();
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


