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
import type { EventFieldRow } from '@model/risk-whitelist/whitelist';

import Request, {
  type IRequestPayload,
  type IRequestResponsePaginationData,
} from '@utils/request';

import ModuleBase from './module-base';

class RiskWhitelistSource extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1/risk_whitelists';
  }

  getList(params: Record<string, any>, payload = {} as IRequestPayload) {
    return Request.get<IRequestResponsePaginationData<Record<string, any>>>(`${this.module}/`, {
      params,
      payload,
    });
  }

  create(params: Record<string, any>) {
    return Request.post<Record<string, any>>(`${this.module}/`, { params });
  }

  batchCreate(params: Record<string, any>) {
    return Request.post(`${this.module}/batch/`, { params });
  }

  update(params: Record<string, any> & { id: number | string }) {
    const { id, ...rest } = params;
    return Request.put<Record<string, any>>(`${this.module}/${id}/`, { params: rest });
  }

  approve(params: { id: number | string }) {
    return Request.post(`${this.module}/${params.id}/approve/`);
  }

  reject(params: { id: number | string; reason: string }) {
    return Request.post(`${this.module}/${params.id}/reject/`, {
      params: { reason: params.reason },
    });
  }

  enable(params: { id: number | string }) {
    return Request.post<Record<string, any>>(`${this.module}/${params.id}/enable/`);
  }

  disable(params: { id: number | string }) {
    return Request.post(`${this.module}/${params.id}/disable/`);
  }

  renew(params: Record<string, any> & { id: number | string }) {
    const { id, ...rest } = params;
    return Request.post<Record<string, any>>(`${this.module}/${id}/renew/`, { params: rest });
  }

  remove(params: { id: number | string }) {
    return Request.delete(`${this.module}/${params.id}/`);
  }

  getHitRecords(params: Record<string, any> & { id: number | string }, payload = {} as IRequestPayload) {
    const { id, ...rest } = params;
    return Request.get<IRequestResponsePaginationData<Record<string, any>>>(`${this.module}/${id}/hit_records/`, {
      params: rest,
      payload,
    });
  }

  getHitEvents(params: { id: number | string; hit_id: number | string }) {
    const { id, ...rest } = params;
    return Request.get<{ fields: EventFieldRow[] }>(`${this.module}/${id}/hit_events/`, { params: rest });
  }
}

export default new RiskWhitelistSource();
