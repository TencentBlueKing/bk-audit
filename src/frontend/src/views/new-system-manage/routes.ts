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
import type { RouteLocationNormalized } from 'vue-router';

const sideMenus = [
  {
    pathName: 'systemInfo',
    title: '系统信息',
    groupName: '接入',
    icon: 'daiwochuli',
  },
  {
    pathName: 'systemDiagnose',
    title: '系统诊断',
    groupName: '分析',
    icon: 'daiwochuli',
  },
];
export default {
  path: '/nwe-system-manage/:id',
  component: () => import('@views/new-system-manage/index.vue'),
  name: 'nweSystemManage',
  redirect: (to: RouteLocationNormalized) => {
    // 获取当前路由的所有参数
    const currentParams = to.params;
    return {
      name: 'systemInfo',
      params: {
        ...currentParams,
      },
    };
  },
  meta: {
    navName: 'nweSystemManage',
    isGroup: true,
    headerTips: 'systemInfo',
    sideMenus,
  },
  children: [
    {
      path: 'system-info/:id',
      component: () => import('@views/new-system-manage/system-info/index.vue'),
      name: 'systemInfo',
      meta: {
        title: '系统信息',
        skeleton: 'system-info',
        headerTips: 'systemInfo',
        groupName: '接入',
      },
    },
    {
      path: 'system-diagnose/:id',
      component: () => import('@views/new-system-manage/system-diagnose/index.vue'),
      name: 'systemDiagnose',
      meta: {
        title: '系统诊断',
        skeleton: 'system-diagnose',
        headerTips: 'systemDiagnose',
      },
    },
    {
      path: 'system-access',
      component: () => import('@views/new-system-manage/system-access/index.vue'),
      name: 'systemAccess',
      meta: {
        title: '系统接入',
        skeleton: 'system-access',
        headerTips: 'systemAccess',
        nodeSideContent: true,
      },
    },
    {
      path: 'system-access-steps',
      component: () => import('@views/new-system-manage/system-access/steps/index.vue'),
      name: 'systemAccessSteps',
      meta: {
        title: '系统接入步骤',
        skeleton: 'system-access-steps',
        headerTips: 'systemAccessSteps',
        nodeSideContent: true,
      },
    },
  ],
};

