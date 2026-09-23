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

import BksecPreviewRisk from '@model/bksec/preview-risk';
import BksecRiskType from '@model/bksec/risk-type';
import BksecRiskTypeField from '@model/bksec/risk-type-field';
import BksecTicketPreview from '@model/bksec/ticket-preview';

import type { PreviewRiskPayload, TicketPreviewPayload } from '@model/bksec/payload';

import BksecManageSource from '../source/bksec-manage';

export type { PreviewRiskPayload, TicketPreviewPayload };

export default {
  fetchRiskTypes() {
    return BksecManageSource.fetchRiskTypes()
      .then(({ data }) => data.map(item => new BksecRiskType(item)));
  },
  fetchRiskTypeFields(params: { risk_type_id: number }) {
    return BksecManageSource.fetchRiskTypeFields(params)
      .then(({ data }) => (data || []).map((item: {
        id: string;
        name: string;
        required?: boolean;
        tips?: string;
      }) => new BksecRiskTypeField(item)));
  },
  fetchPreviewRiskList(params: PreviewRiskPayload) {
    return BksecManageSource.fetchPreviewRiskList(params)
      .then(({ data }) => (data || []).map((item: {
        id: string;
        title: string;
        source: 'real' | 'debug';
        risk_id?: string;
        created_at?: string;
        sample?: Record<string, string>;
      }) => new BksecPreviewRisk(item)));
  },
  fetchTicketPreview(params: TicketPreviewPayload) {
    return BksecManageSource.fetchTicketPreview(params)
      .then(({ data }) => new BksecTicketPreview(data));
  },
  sendTestTicket(params: {
    handler: string;
    risk_type_id: number | null;
    field_values: Record<string, string>;
    risk_id?: string;
  }) {
    return BksecManageSource.sendTestTicket(params)
      .then(({ data }) => data);
  },
};
