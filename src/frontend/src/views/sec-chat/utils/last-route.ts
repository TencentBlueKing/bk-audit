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
import { getQueryFromLocation } from '@utils/assist/scene-system-params';

/** 顶栏切回 AI 助手时，恢复离开前的会话页（与工具广场 keep-alive 记忆一致） */
const STORAGE_KEY = 'sec-chat:last-route';
const SCENE_QUERY_KEYS = ['scene_id', 'scope_id', 'scope_type'] as const;

export type SecChatLastRoute = {
  name: 'secChatHome' | 'secChatAuditLog';
  params?: Record<string, string>;
  query?: Record<string, string | string[]>;
};

const normalizeQuery = (query: Record<string, unknown> = {}) => {
  const next: Record<string, string> = {};
  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    next[key] = Array.isArray(value) ? String(value[0]) : String(value);
  });
  return next;
};

/**
 * AI 助手内跳转必须保留场景 query。
 * 否则场景选择器会在 keep-alive 下再触发 router.replace 补参，触发 parentNode 空引用并打断导航。
 */
export const preserveSecChatQuery = (
  routeQuery: Record<string, unknown> = {},
  extraQuery: Record<string, unknown> = {},
) => {
  const fromLocation = getQueryFromLocation();
  const merged = {
    ...fromLocation,
    ...normalizeQuery(routeQuery),
    ...normalizeQuery(extraQuery),
  };
  // 地址栏有场景参数时优先保证不丢
  SCENE_QUERY_KEYS.forEach((key) => {
    if (!merged[key] && fromLocation[key]) {
      merged[key] = fromLocation[key];
    }
  });
  return merged;
};

export const saveSecChatLastRoute = (route: {
  name: string | symbol | null | undefined;
  params?: Record<string, unknown>;
  query?: Record<string, unknown>;
}) => {
  if (route.name !== 'secChatHome' && route.name !== 'secChatAuditLog') return;
  const params: Record<string, string> = {};
  Object.entries(route.params || {}).forEach(([key, value]) => {
    if (value === undefined || value === null) return;
    params[key] = Array.isArray(value) ? String(value[0]) : String(value);
  });
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
      name: route.name,
      params,
      query: preserveSecChatQuery(route.query || {}),
    } satisfies SecChatLastRoute));
  } catch {
    // sessionStorage 不可用时忽略
  }
};

export const readSecChatLastRoute = (): SecChatLastRoute | null => {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as SecChatLastRoute;
    if (parsed?.name === 'secChatHome' || parsed?.name === 'secChatAuditLog') {
      return {
        ...parsed,
        query: preserveSecChatQuery(parsed.query || {}),
      };
    }
  } catch {
    // ignore
  }
  return null;
};

export const resolveSecChatEntryRoute = (): SecChatLastRoute | { name: 'secChatHome'; query: Record<string, string> } => (
  readSecChatLastRoute() || {
    name: 'secChatHome',
    query: preserveSecChatQuery(),
  }
);
