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

import type ConfigModel from '@model/root/config';

import NotFound from '@views/404.vue';
import AnalysisManage from '@views/analysis-manage/routes';
import EventManage from '@views/event-manage/routes';
import HandleManage from '@views/handle-manage/routes';
import LinkDataManage from '@views/link-data-manage/routes';
import NoticeGroup from '@views/notice-group/routes';
import ApplicationManage from '@views/process-application-manage/routes';
import RiskManage from '@views/risk-manage/routes';
import RuleManage from '@views/rule-manage/routes';
import StatementManage from '@views/statement-manage/routes';
import StorageManage from '@views/storage-manage/routes';
import StrategyManage from '@views/strategy-manage/routes';
import SystemManage from '@views/system-manage/routes';

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
        AnalysisManage,
        SystemManage,
        StrategyManage,
        LinkDataManage,
        EventManage,
        NoticeGroup,
        RiskManage,
        HandleManage,
        ApplicationManage,
        RuleManage,
        StatementManage,
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

  const routerPush = router.push;
  const routerReplace = router.replace;

  router.push = (params) => {
    lastRouterHrefCache = router.resolve(params).href;
    return changeConfirm().then(() => routerPush(params));
  };
  router.replace = (params) => {
    lastRouterHrefCache = router.resolve(params).href;
    return changeConfirm().then(() => routerReplace(params));
  };

  router.onError((error: any) => {
    if (/Failed to fetch dynamically imported module/.test(error.message)) {
      window.location.href = lastRouterHrefCache;
    }
  });

  return router;
};


