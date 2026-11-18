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

import type { TestSendRequest, TicketPreviewRequest } from '@model/bksec/payload';

import Request from '@utils/request';

class BksecManage {
  fetchFeature() {
    return Request.get('/api/v1/feature/bksec/');
  }

  /**
   * 当前用户有权限的项目及其风险类型。name__icontains 按风险类型名称模糊搜索。
   */
  fetchProjects(params: {
    is_formal?: string;
    name__icontains?: string;
  } = {}) {
    const query: Record<string, string> = {};
    const formal = params.is_formal?.trim();
    const keyword = params.name__icontains?.trim();
    if (formal) query.is_formal = formal;
    if (keyword) query.name__icontains = keyword;
    return Request.get('/api/v1/bk_sec/projects/', {
      params: query,
    });
  }

  fetchTicketPreview(params: TicketPreviewRequest) {
    return Request.post('/api/v1/ticket/preview/', { params });
  }

  sendTestTicket(params: TestSendRequest) {
    return Request.post('/api/v1/ticket/test_send/', {
      params,
      payload: { catchError: true },
    });
  }

  fetchTestTaskStatus(params: { task_id?: string; risk_id?: string }) {
    return Request.get('/api/v1/ticket/test_task_status/', {
      params,
      payload: { catchError: true },
    });
  }

  /**
   * 编辑态候选风险。按策略 ID 筛选风险列表。
   */
  fetchEditPreviewRisks(params: { strategy_id: number }) {
    return Request.post('/api/v1/risks/', {
      params: {
        strategy_id: params.strategy_id,
      },
    });
  }
}

export default new BksecManage();
