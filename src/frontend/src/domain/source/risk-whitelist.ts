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
import type RiskWhitelist from '@model/risk-whitelist/whitelist';
import type {
  ConditionFieldOption,
  EventFieldRow,
  HitRecord,
  RenewPayload,
  WhitelistPayload,
} from '@model/risk-whitelist/whitelist';

import Request, {
  type IRequestPayload,
  type IRequestResponsePaginationData,
} from '@utils/request';

import ModuleBase from './module-base';

/**
 * 前端按需求文档起草的契约。路径和字段名等后端（138663193）出接口后对齐。
 */
class RiskWhitelistSource extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1/risk_whitelists';
  }

  getList(params: Record<string, any>, payload = {} as IRequestPayload) {
    return Request.get<IRequestResponsePaginationData<RiskWhitelist>>(`${this.module}/`, {
      params,
      payload,
    });
  }

  getDetail(params: { id: number | string }) {
    return Request.get<RiskWhitelist>(`${this.module}/${params.id}/`);
  }

  create(params: WhitelistPayload) {
    return Request.post<RiskWhitelist>(`${this.module}/`, { params });
  }

  update(params: WhitelistPayload & { id: number | string }) {
    const { id, ...rest } = params;
    return Request.put<RiskWhitelist>(`${this.module}/${id}/`, { params: rest });
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
    return Request.post<RiskWhitelist>(`${this.module}/${params.id}/enable/`);
  }

  disable(params: { id: number | string }) {
    return Request.post(`${this.module}/${params.id}/disable/`);
  }

  renew(params: RenewPayload) {
    const { id, ...rest } = params;
    return Request.post<RiskWhitelist>(`${this.module}/${id}/renew/`, { params: rest });
  }

  remove(params: { id: number | string }) {
    return Request.delete(`${this.module}/${params.id}/`);
  }

  getHitRecords(params: Record<string, any> & { id: number | string }, payload = {} as IRequestPayload) {
    const { id, ...rest } = params;
    return Request.get<IRequestResponsePaginationData<HitRecord>>(`${this.module}/${id}/hit_records/`, {
      params: rest,
      payload,
    });
  }

  getHitEvent(params: { id: number | string }) {
    return Request.get<{ fields: EventFieldRow[] }>(`${this.module}/hit_events/${params.id}/`);
  }

  getConditionFields(params: { strategy_id?: string; scene_id?: string | number }) {
    return Request.get<ConditionFieldOption[]>(`${this.module}/condition_fields/`, { params });
  }

  applyFromRisk(params: Record<string, any>) {
    return Request.post(`${this.module}/apply/`, { params });
  }
}

export default new RiskWhitelistSource();
