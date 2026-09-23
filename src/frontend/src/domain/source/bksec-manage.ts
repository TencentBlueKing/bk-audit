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

import type { PreviewRiskPayload, TicketPreviewPayload } from '@model/bksec/payload';

import Request from '@utils/request';

import ModuleBase from './module-base';

class BksecManage extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1/bksec';
  }

  fetchRiskTypes() {
    return Request.get<Array<{ id: number; name: string }>>(`${this.module}/risk_types/`);
  }

  fetchRiskTypeFields(params: { risk_type_id: number }) {
    return Request.get(`${this.module}/risk_types/${params.risk_type_id}/fields/`);
  }

  fetchPreviewRiskList(params: PreviewRiskPayload) {
    return Request.get(`${this.module}/preview_risks/`, { params });
  }

  fetchTicketPreview(params: TicketPreviewPayload) {
    return Request.post(`${this.module}/ticket_preview/`, { params });
  }

  sendTestTicket(params: {
    handler: string;
    risk_type_id: number | null;
    field_values: Record<string, string>;
    risk_id?: string;
  }) {
    return Request.post(`${this.module}/test_tickets/`, { params });
  }
}

export default new BksecManage();
