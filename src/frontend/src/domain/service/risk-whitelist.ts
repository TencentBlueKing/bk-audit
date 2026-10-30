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
import type {
  EventFieldRow,
  HitRecord,
  RenewPayload,
  WhitelistPayload,
} from '@model/risk-whitelist/whitelist';
import RiskWhitelist from '@model/risk-whitelist/whitelist';

import RiskWhitelistSource from '../source/risk-whitelist';

import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

const withScene = <T extends Record<string, any>>(params: T) => ({
  ...params,
  scene_id: params.scene_id ?? getSceneSystemParams().scope_id,
});

export default {
  fetchList(params: Record<string, any>) {
    const sort = params.sort?.length ? params.sort : ['-rule_code'];
    return RiskWhitelistSource.getList(withScene({ ...params, sort }), { permission: 'page' })
      .then(({ data }) => ({
        ...data,
        results: (data.results || []).map(item => new RiskWhitelist(item)),
      }));
  },

  fetchDetail(params: { id: number | string }) {
    return RiskWhitelistSource.getDetail(params)
      .then(({ data }) => new RiskWhitelist(data));
  },

  create(params: WhitelistPayload) {
    return RiskWhitelistSource.create(withScene(params))
      .then(({ data }) => new RiskWhitelist(data));
  },

  update(params: WhitelistPayload & { id: number | string }) {
    return RiskWhitelistSource.update(withScene(params))
      .then(({ data }) => new RiskWhitelist(data));
  },

  approve(params: { id: number | string }) {
    return RiskWhitelistSource.approve(params).then(({ data }) => data);
  },

  reject(params: { id: number | string; reason: string }) {
    return RiskWhitelistSource.reject(params).then(({ data }) => data);
  },

  enable(params: { id: number | string }) {
    return RiskWhitelistSource.enable(params)
      .then(({ data }) => (data ? new RiskWhitelist(data) : data));
  },

  disable(params: { id: number | string }) {
    return RiskWhitelistSource.disable(params).then(({ data }) => data);
  },

  renew(params: RenewPayload) {
    return RiskWhitelistSource.renew(params)
      .then(({ data }) => new RiskWhitelist(data));
  },

  remove(params: { id: number | string }) {
    return RiskWhitelistSource.remove(params).then(({ data }) => data);
  },

  fetchHitRecords(params: Record<string, any> & { id: number | string }) {
    return RiskWhitelistSource.getHitRecords(params)
      .then(({ data }) => data as { results: HitRecord[]; total: number; page: number; num_pages: number });
  },

  fetchHitEvent(params: { id: number | string }) {
    return RiskWhitelistSource.getHitEvent(params)
      .then(({ data }) => data as { fields: EventFieldRow[] });
  },

  fetchConditionFields(params: { strategy_id?: string } = {}) {
    return RiskWhitelistSource.getConditionFields(withScene(params))
      .then(({ data }) => data || []);
  },

  applyFromRisk(params: Record<string, any>) {
    return RiskWhitelistSource.applyFromRisk(withScene(params))
      .then(({ data }) => data);
  },
};
