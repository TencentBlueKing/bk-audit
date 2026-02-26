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
  path: '/tools',
  name: 'tools',
  component: () => import('@views/tools/index.vue'),
  redirect: {
    name: 'toolsSquare',
  },
  meta: {
    navName: 'toolsSquare',
  },
  children: [
    {
      path: 'tools-square',
      component: () => import('@views/tools/tools-square/index.vue'),
      name: 'toolsSquare',
      meta: {
        title: '工具广场',
        nodeSideContent: true,
      },
    },
    {
      path: 'tools-add',
      component: () => import('@views/tools/tools-square/add/index.vue'),
      name: 'toolsAdd',
      meta: {
        title: '创建工具',
      },
    },
    {
      path: 'tools-edit/:id',
      component: () => import('@views/tools/tools-square/add/index.vue'),
      name: 'toolsEdit',
      meta: {
        title: '编辑工具',
        skeleton: 'strategyEdit',
      },
    },
  ],
};

