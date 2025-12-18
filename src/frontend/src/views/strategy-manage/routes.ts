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
  path: '/strategy-manage',
  component: () => import('@views/strategy-manage/index.vue'),
  name: 'strategyManage',
  redirect: {
    name: 'strategyList',
  },
  meta: {
    navName: 'auditConfigurationManage',
  },
  children: [
    {
      path: 'list',
      component: () => import('@views/strategy-manage/list/index.vue'),
      name: 'strategyList',
      meta: {
        title: '审计策略',
        skeleton: 'strategyList',
      },
    },
    {
      path: 'create',
      component: () => import('@views/strategy-manage/strategy-create/index.vue'),
      name: 'strategyCreate',
      meta: {
        title: '新建策略',
        skeleton: 'strategyCreate',
      },
    },
    {
      path: 'edit/:id',
      component: () => import('@views/strategy-manage/strategy-create/index.vue'),
      name: 'strategyEdit',
      meta: {
        title: '编辑策略',
        skeleton: 'strategyEdit',
      },
    },
    {
      path: 'clone/:id',
      component: () => import('@views/strategy-manage/strategy-create/index.vue'),
      name: 'strategyClone',
      meta: {
        title: '克隆策略',
        skeleton: 'strategyClone',
      },
    },
    {
      path: 'upgrade/:strategyId/:controlId',
      component: () => import('@views/strategy-manage/strategy-create/upgrade/index.vue'),
      name: 'strategyUpgrade',
      meta: {
        title: '升级详情',
        skeleton: 'strategyUpgrade',
      },
    },
  ],
};
