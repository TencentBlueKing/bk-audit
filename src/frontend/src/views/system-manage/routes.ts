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
  path: '/system-manage',
  component: () => import('@views/system-manage/index.vue'),
  name: 'systemManage',
  redirect: {
    name: 'systemList',
  },
  meta: {
    navName: 'auditConfigurationManage',
  },
  children: [
    {
      path: 'list',
      component: () => import('@views/system-manage/list/index.vue'),
      name: 'systemList',
      meta: {
        title: '系统列表',
        skeleton: 'systemList',
      },
    },
    {
      path: 'detail/:id',
      component: () => import('@views/system-manage/detail/index.vue'),
      name: 'systemDetail',
      meta: {
        title: '系统详情',
      },
    },
    {
      path: 'collector-create/:systemId',
      component: () => import('@views/system-manage/collector-create/index.vue'),
      name: 'collectorCreate',
      meta: {
        title: '新建采集',
      },
    },
    {
      path: 'log-create/:systemId',
      component: () => import('@/views/system-manage/log-create/index.vue'),
      name: 'logCreate',
      meta: {
        title: '新建日志上报',
      },
    },
    {
      path: 'collector-edit/:systemId/:collectorConfigId',
      component: () => import('@views/system-manage/collector-create/index.vue'),
      name: 'collectorEdit',
      meta: {
        title: '编辑采集',
      },
    },
    {
      path: 'dataid-edit/:systemId/:bkDataId',
      component: () => import('@views/system-manage/collector-create/index.vue'),
      name: 'dataIdEdit',
      meta: {
        title: '编辑采集',
      },
    },
    {
      path: 'log-edit/:systemId/:id',
      component: () => import('@views/system-manage/log-create/index.vue'),
      name: 'logDataIdEdit',
      meta: {
        title: '编辑采集',
      },
    },
    {
      path: 'collector-complete/:systemId/:collectorConfigId/:taskIdList?',
      component: () => import('@views/system-manage/collector-complete/index.vue'),
      name: 'collectorComplete',
      meta: {
        title: '采集配置创建完成',
      },
    },
  ],
};
