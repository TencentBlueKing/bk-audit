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
  path: '/platform',
  name: 'platformManage',
  component: () => import('@views/platform-manage/index.vue'),
  redirect: {
    name: 'platformSceneConfig',
  },
  meta: {
    navName: 'platformManage',
    permission: 'manage_platform', // 平台管理权限
  },
  children: [
    {
      path: 'platform-scene-config',
      component: () => import('@views/platform-manage/scene-manage/index.vue'),
      name: 'platformSceneConfig',
      meta: {
        title: '场景管理',
        nodeSideContent: false,
      },
    },
    {
      path: 'platform-report-config',
      component: () => import('@views/platform-manage/report-config/index.vue'),
      name: 'platformReportConfig',
      meta: {
        title: '全局报表',
        nodeSideContent: false,
      },
    },
    {
      path: 'platform-tool-config',
      component: () => import('@views/platform-manage/tool-manage/index.vue'),
      name: 'platformToolConfig',
      meta: {
        title: '全局工具',
        nodeSideContent: false,
      },
    },
    {
      path: 'platform-tool-create',
      component: () => import('@views/platform-manage/tool-manage/create-tool/index.vue'),
      name: 'platformToolCreate',
      meta: {
        title: '新建工具',
        nodeSideContent: false,
      },
    },
    {
      path: 'platform-tool-edit/:id',
      component: () => import('@views/platform-manage/tool-manage/create-tool/index.vue'),
      name: 'platformToolEdit',
      meta: {
        title: '编辑工具',
        skeleton: 'strategyEdit',
        nodeSideContent: false,
      },
    },
    {
      path: 'platform-strategy-list',
      component: () => import('@views/strategy-manage/list/index.vue'),
      name: 'platformStrategyList',
      meta: {
        title: '全局策略',
        skeleton: 'strategyList',
        nodeSideContent: false,
      },
    },
    {
      path: 'platform-strategy-create',
      component: () => import('@views/strategy-manage/strategy-create/index.vue'),
      name: 'platformStrategyCreate',
      meta: {
        title: '新建策略',
        skeleton: 'strategyCreate',
        nodeSideContent: false,
        changeSceneIsBackedList: true,
        ListPageName: 'platformStrategyList',
      },
    },
    {
      path: 'platform-strategy-edit/:id',
      component: () => import('@views/strategy-manage/strategy-create/index.vue'),
      name: 'platformStrategyEdit',
      meta: {
        title: '编辑策略',
        skeleton: 'strategyEdit',
        nodeSideContent: false,
        changeSceneIsBackedList: true,
        ListPageName: 'platformStrategyList',
      },
    },
    {
      path: 'platform-strategy-clone/:id',
      component: () => import('@views/strategy-manage/strategy-create/index.vue'),
      name: 'platformStrategyClone',
      meta: {
        title: '克隆策略',
        skeleton: 'strategyClone',
        nodeSideContent: false,
        changeSceneIsBackedList: true,
        ListPageName: 'platformStrategyList',
      },
    },
    {
      path: 'platform-strategy-upgrade/:strategyId/:controlId',
      component: () => import('@views/strategy-manage/strategy-create/upgrade/index.vue'),
      name: 'platformStrategyUpgrade',
      meta: {
        title: '升级详情',
        skeleton: 'strategyUpgrade',
        nodeSideContent: false,
        changeSceneIsBackedList: true,
        ListPageName: 'platformStrategyList',
      },
    },
  ],
};
