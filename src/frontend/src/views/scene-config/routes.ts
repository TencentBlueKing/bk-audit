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

export default {
  path: '/scene-config',
  component: () => import('@views/scene-config/index.vue'),
  redirect: {
    name: 'sceneInfo',
  },
  meta: {
    navName: 'sceneConfiguration',
  },
  children: [
    {
      path: 'landing-page',
      component: () => import('@views/scene-config/landing-page/index.vue'),
      name: 'landingPage',
      meta: {
        title: '引导页',
        nodeSideContent: true,
      },
    },
    {
      path: 'user-landing-page',
      component: () => import('@views/scene-config/landing-page/user-landing.vue'),
      name: 'userLandingPage',
      meta: {
        title: '引导页',
        nodeSideContent: true,
      },
    },
    // {
    //   path: 'permissions-page',
    //   component: () => import('@views/scene-config/permissions-page/index.vue'),
    //   name: 'permissionsPage',
    //   meta: {
    //     title: '申请权限',
    //     nodeSideContent: true,
    //   },
    // },
    {
      path: 'scene-info',
      component: () => import('@views/scene-config/scene-info/index.vue'),
      name: 'sceneInfo',
      meta: {
        title: '场景信息',
        nodeSideContent: false,
      },
    },
    {
      path: 'scene-report-config',
      component: () => import('@views/scene-config/report-config/index.vue'),
      name: 'sceneReportConfig',
      meta: {
        title: '报表管理',
        nodeSideContent: false,
      },
    },
    {
      path: 'scene-tool-manege',
      component: () => import('@views/scene-config/tool-manege/index.vue'),
      name: 'sceneToolManege',
      meta: {
        title: '工具管理',
        nodeSideContent: false,
      },
    },
    {
      path: 'scene-tool-create',
      component: () => import('@views/scene-config/tool-manege/create-tool/index.vue'),
      name: 'sceneToolCreate',
      meta: {
        title: '新建工具',
        hideSidebar: true,
      },
    },
    {
      path: 'scene-tool-edit/:id',
      component: () => import('@views/scene-config/tool-manege/create-tool/index.vue'),
      name: 'sceneToolEdit',
      meta: {
        title: '编辑工具',
        skeleton: 'strategyEdit',
        hideSidebar: true,
      },
    },
  ],
};
