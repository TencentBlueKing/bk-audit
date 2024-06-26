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
  path: '/application-manage',
  name: 'applicationManage',
  component: () => import('@views/process-application-manage/index.vue'),
  redirect: {
    name: 'applicationManageList',
  },
  meta: {
    navName: 'auditConfigurationManage',
  },
  children: [
    {
      path: 'list',
      component: () => import('@views/process-application-manage/list/index.vue'),
      name: 'applicationManageList',
      meta: {
        title: '处理套餐',
      },
    },
    {
      path: 'create',
      component: () => import('@views/process-application-manage/create/index.vue'),
      name: 'processApplicationCreate',
      meta: {
        title: '新建处理套餐',
      },
    },
    {
      path: 'edit/:id',
      component: () => import('@views/process-application-manage/create/index.vue'),
      name: 'processApplicationEdit',
      meta: {
        title: '编辑处理套餐',
      },
    },
    {
      path: 'clone/:id',
      component: () => import('@views/process-application-manage/create/index.vue'),
      name: 'processApplicationClone',
      meta: {
        title: '克隆处理套餐',
      },
    },
    // {
    //   path: 'detail/:riskId',
    //   component: () => import('@views/risk-manage/detail/index.vue'),
    //   name: 'riskManageDetail',
    //   meta: {
    //     title: '风险详情',
    //   },
    // },
  ],
};
