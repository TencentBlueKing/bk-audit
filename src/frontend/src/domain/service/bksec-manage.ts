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

import type { BksecConfigPayload } from '@model/bksec/config';
import BksecPreviewRisk from '@model/bksec/preview-risk';
import BksecProject from '@model/bksec/project';
import BksecTestTaskStatus from '@model/bksec/task-status';

import BksecManageSource from '../source/bksec-manage';

export default {
  fetchFeature() {
    return BksecManageSource.fetchFeature()
      .then(({ data }) => ({ enabled: !!data?.enabled }));
  },
  fetchProjects(params?: {
    is_formal?: string;
    name__icontains?: string;
  }) {
    return BksecManageSource.fetchProjects(params)
      .then(({ data }) => (data || []).map((item: Record<string, any>) => new BksecProject(item)));
  },
  fetchRiskTypes(params?: {
    is_formal?: string;
    name__icontains?: string;
  }) {
    return this.fetchProjects(params)
      .then(projects => projects.flatMap(project => project.riskTypes));
  },
  fetchTicketPreview(params: { risk_id: string; bksec_config: BksecConfigPayload }) {
    return BksecManageSource.fetchTicketPreview(params)
      .then(({ data }) => data);
  },
  sendTestTicket(params: {
    risk_id: string;
    test_receivers: string[];
    bksec_config: BksecConfigPayload;
  }) {
    return BksecManageSource.sendTestTicket(params)
      .then(({ data }) => ({ taskId: String(data?.task?.task_id || '') }));
  },
  fetchTestTaskStatus(params: { task_id?: string; risk_id?: string }) {
    return BksecManageSource.fetchTestTaskStatus(params)
      .then(({ data }) => new BksecTestTaskStatus(data || {}));
  },
  fetchEditPreviewRisks(strategyId?: string | number) {
    const id = Number(strategyId);
    if (!Number.isFinite(id) || id <= 0) return Promise.resolve([] as BksecPreviewRisk[]);
    return BksecManageSource.fetchEditPreviewRisks({ strategy_id: id })
      .then(({ data }) => {
        const rows = Array.isArray(data) ? data : (data?.results || []);
        return rows.map((item: Record<string, any>) => new BksecPreviewRisk({
          id: String(item.risk_id || item.id || ''),
          title: item.title || '',
          source: item.source || 'real',
          risk_id: String(item.risk_id || ''),
          created_at: item.created_at || item.event_time || '',
          sample: item.sample || {},
        }));
      });
  },
};
