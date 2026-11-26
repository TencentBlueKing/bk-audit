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
  ContainsFieldOption,
  EventFieldRow,
  HitRecord,
  RenewPayload,
  WhitelistFlow,
  WhitelistPayload,
} from '@model/risk-whitelist/whitelist';
import RiskWhitelist, {
  fromMatchScopeBody,
  toMatchScopeBody,
  toWhitelistBody,
  toWhitelistFlow,
} from '@model/risk-whitelist/whitelist';

import RiskWhitelistSource from '../source/risk-whitelist';

import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

/** 后端 scene_id 是整数，取不到时不传，避免空串校验失败 */
const sceneParams = (sceneId?: string | number) => {
  const value = sceneId ?? getSceneSystemParams().scope_id;
  return /^\d+$/.test(String(value ?? '')) ? { scene_id: Number(value) } : {};
};

/** 列表接口仅接受文档约定字段，避免 URL/表格残留参数触发「参数验证失败」 */
const LIST_QUERY_KEYS = [
  'scene_id',
  'id',
  'status',
  'whitelist_type',
  'reason',
  'match_scope',
  'updated_by',
  'keyword',
  'contains_fields',
  'sort',
  'page',
  'page_size',
] as const;

/** 规则标识列按后端整数主键 id 排序 */
const toSortField = (field: string) => field.replace(/^(-?)rule_code$/, '$1id');

/**
 * 包含条件多选：整理为逗号分隔字符串。
 * 不用数组，避免 paramsSerializer 把 key 写成 contains_fields[]。
 */
const toContainsFieldsParam = (value?: string | string[]) => {
  const list = Array.isArray(value)
    ? value.map(item => String(item).trim()).filter(Boolean)
    : String(value || '')
      .split(/[,\s]+/)
      .map(item => item.trim())
      .filter(Boolean);
  return list.join(',');
};

/**
 * 搜索框字段映射：规则标识 → id；匹配范围 → keyword；包含条件 → contains_fields。
 */
const normalizeListParams = (params: Record<string, any>): Record<string, any> => {
  const {
    rule_code: ruleCode,
    match_scope: matchScope,
    condition_keyword: conditionKeyword,
    contains_fields: containsFieldsRaw,
    sort,
    keyword: rawKeyword,
    ...rest
  } = params;
  const containsFields = toContainsFieldsParam(containsFieldsRaw ?? conditionKeyword);
  const keyword = [rawKeyword, matchScope].filter(Boolean).join(' ');
  const normalized: Record<string, any> = {
    ...rest,
    ...(ruleCode ? { id: ruleCode } : {}),
    ...(keyword ? { keyword } : {}),
    ...(containsFields ? { contains_fields: containsFields } : {}),
    ...(sort ? { sort: Array.isArray(sort) ? sort.map(toSortField) : toSortField(String(sort)) } : {}),
  };
  return LIST_QUERY_KEYS.reduce((result, key) => {
    const value = normalized[key];
    if (value !== undefined && value !== null && value !== '') {
      result[key] = value;
    }
    return result;
  }, {} as Record<string, any>);
};

export default {
  fetchList(params: Record<string, any>) {
    const normalized = normalizeListParams(params);
    const { scene_id: sceneId, ...rest } = normalized;
    const withScene = { ...rest, ...sceneParams(sceneId) };
    // 列表必须带合法 scene_id，否则后端会直接「参数验证失败」
    if (withScene.scene_id === undefined) {
      return Promise.resolve({ results: [], total: 0, count: 0 });
    }
    return RiskWhitelistSource.getList(withScene, { permission: 'page' })
      .then(({ data }) => ({
        ...data,
        results: (data.results || []).map(item => new RiskWhitelist(item)),
      }));
  },

  /**
   * 批量回显 ITSM flow：入参 id 列表 + scene_id。
   * 兼容 results/items 数组，或 id → payload 的对象映射。
   */
  fetchDetailInfo(params: { id: Array<number | string>; scene_id?: string | number }) {
    const ids = (params.id || [])
      .map(item => Number(item))
      .filter(item => Number.isFinite(item) && item > 0);
    const withScene = { ...sceneParams(params.scene_id) };
    if (withScene.scene_id === undefined || !ids.length) {
      return Promise.resolve({} as Record<string, WhitelistFlow>);
    }
    return RiskWhitelistSource.getDetailInfo({
      scene_id: withScene.scene_id,
      id: ids,
    }, { permission: 'page' })
      .then(({ data }) => {
        const rows: Array<Record<string, any>> = (() => {
          if (Array.isArray(data)) return data;
          if (data && typeof data === 'object') {
            if (Array.isArray((data as any).results)) return (data as any).results;
            if (Array.isArray((data as any).items)) return (data as any).items;
            return Object.entries(data as Record<string, any>).map(([key, value]) => {
              if (value && typeof value === 'object') {
                return { id: (value as any).id ?? key, ...(value as object) };
              }
              return { id: key };
            });
          }
          return [];
        })();
        return rows.reduce((result, item) => {
          const id = item?.id;
          if (id === undefined || id === null || id === '') return result;
          result[String(id)] = toWhitelistFlow(item, {
            itsm_sn: item.itsm_sn || '',
            itsm_url: item.itsm_url || '',
            applicant: item.applicant || '',
          });
          return result;
        }, {} as Record<string, WhitelistFlow>);
      });
  },

  /** 菜单新建，或风险单上单独加白（带 risk_id，场景以风险单为准） */
  create(params: WhitelistPayload & { risk_id?: string }) {
    return RiskWhitelistSource.create({
      ...sceneParams(params.scene_id),
      ...(params.risk_id ? { risk_id: params.risk_id } : {}),
      ...toWhitelistBody(params),
    })
      .then(({ data }) => new RiskWhitelist(data));
  },

  batchCreate(params: WhitelistPayload & { risk_ids: string[] }) {
    return RiskWhitelistSource.batchCreate({
      ...sceneParams(params.scene_id),
      risk_ids: params.risk_ids,
      ...toWhitelistBody(params),
    })
      .then(({ data }) => data);
  },

  /** 编辑只改匹配范围和原因；带 duration_days/expire_at 时后端按续期处理 */
  update(params: WhitelistPayload & { id: number | string; renew?: boolean }) {
    const mode = params.validity_mode;
    const renewParams = params.renew && mode
      ? {
        duration_days: mode,
        ...(mode === 'custom' && params.expire_at ? { expire_at: params.expire_at } : {}),
      }
      : {};
    return RiskWhitelistSource.update({
      id: params.id,
      match_scope: toMatchScopeBody(params.match_scope),
      reason: params.reason,
      ...renewParams,
    })
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
    return RiskWhitelistSource.renew({
      id: params.id,
      duration_days: params.validity_mode,
      ...(params.validity_mode === 'custom' && params.expire_at ? { expire_at: params.expire_at } : {}),
      ...(params.remark ? { remark: params.remark } : {}),
    })
      .then(({ data }) => new RiskWhitelist(data));
  },

  remove(params: { id: number | string }) {
    return RiskWhitelistSource.remove(params).then(({ data }) => data);
  },

  fetchHitRecords(params: Record<string, any> & { id: number | string }) {
    return RiskWhitelistSource.getHitRecords(params)
      .then(({ data }) => ({
        ...data,
        results: (data.results || []).map(item => ({
          ...item,
          match_scope: fromMatchScopeBody(item.match_scope),
        })),
      }) as { results: HitRecord[]; total: number; page: number; num_pages: number });
  },

  fetchHitEvents(params: { id: number | string; hit_id: number | string }) {
    return RiskWhitelistSource.getHitEvents(params)
      .then(({ data }): EventFieldRow[] => data?.fields || []);
  },

  /** 列表「包含条件」下拉：按 scene 拉全量已用字段 */
  fetchContainsFields(sceneId?: string | number) {
    const { scene_id: id } = sceneParams(sceneId);
    if (id === undefined) {
      return Promise.resolve([] as ContainsFieldOption[]);
    }
    return RiskWhitelistSource.getContainsFields({ scene_id: id }, { permission: 'page' })
      .then(({ data }): ContainsFieldOption[] => data?.results || []);
  },
};
