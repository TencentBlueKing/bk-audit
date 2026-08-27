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
import { resolveSecChatEntryRoute } from './utils/last-route';

export default {
  path: '/sec-chat',
  name: 'secChat',
  component: () => import('@views/sec-chat/index.vue'),
  // 顶栏点「AI助手」进父路由时，恢复离开前的会话页（新对话仅由侧栏「新对话」进入首页）
  redirect: () => resolveSecChatEntryRoute(),
  meta: {
    title: 'AI助手',
    navName: 'secChat',
    nodeSideContent: true,
    keepAlive: true,
    // 与子路由共用 key，避免首页/会话页切换时整页（含侧栏）被拆成两份缓存并反复挂载
    keepAliveKey: 'secChat',
  },
  children: [
    {
      path: '',
      name: 'secChatHome',
      component: () => import('@views/sec-chat/home/index.vue'),
      meta: {
        title: 'AI助手',
        navName: 'secChat',
        nodeSideContent: true,
        keepAlive: true,
        keepAliveKey: 'secChat',
      },
    },
    {
      path: 'audit-log-retrieval/:conversationId?',
      name: 'secChatAuditLog',
      component: () => import('@views/sec-chat/audit-log-retrieval/index.vue'),
      meta: {
        title: '审计日志检索',
        navName: 'secChat',
        nodeSideContent: true,
        keepAlive: true,
        keepAliveKey: 'secChat',
      },
    },
  ],
};
