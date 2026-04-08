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
        title: '报表管理',
        nodeSideContent: false,
      },
    },
    {
      path: 'platform-tool-config',
      component: () => import('@views/platform-manage/tool-manage/index.vue'),
      name: 'platformToolConfig',
      meta: {
        title: '工具管理',
        nodeSideContent: false,
      },
    },
  ],
};

