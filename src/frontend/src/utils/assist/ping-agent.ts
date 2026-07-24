/*
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
    10|  software distributed under the License is distributed on
  an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
  either express or implied. See the License for the
  specific language governing permissions and limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
*/

export interface AgentAuthItem {
  code: string;
  enabled?: boolean;
  ping_url?: string;
}

/** 同一 code 会话内只 ping 一次 */
const pingedCodes = new Set<string>();

/**
 * 登录后预热 agents：按 Entry.agent_auth.agents 中的 ping_url 发请求。
 * 不阻塞业务：失败仅打诊断日志，不作为登录/鉴权依据。
 */
export const warmAgents = (agents?: AgentAuthItem[] | null): void => {
  if (!Array.isArray(agents) || !agents.length) return;

  agents.forEach((agent) => {
    const { code, enabled, ping_url: pingUrl } = agent || {};
    if (!code || !enabled || !pingUrl || pingedCodes.has(code)) return;

    pingedCodes.add(code);

    fetch(pingUrl, { credentials: 'include' }).catch((error) => {
      // eslint-disable-next-line no-console
      console.warn(`[agent-ping] code=${code} failed`, error);
    });
  });
};
