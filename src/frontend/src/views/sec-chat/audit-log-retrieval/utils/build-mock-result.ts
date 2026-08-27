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
import type { RetrievalFilterCondition, RetrievalResultPayload } from '../../types';

/** 仅保留给本地演示/兜底；主路径已切真实接口 */
export const buildMockRetrievalResult = (query: string): RetrievalResultPayload => {
  const conditions: RetrievalFilterCondition[] = [
    { field: 'query', value: query },
  ];
  const columns = [
    { rawName: 'username', displayName: '操作人' },
    { rawName: 'system_id', displayName: '来源系统' },
    { rawName: 'result_code', displayName: '操作结果' },
  ];
  const rows = Array.from({ length: 5 }).map((_, index) => ({
    username: `user_${index}`,
    system_id: 'bk_log',
    result_code: index % 2 === 0 ? '0' : '1',
  }));
  return {
    conditions,
    toolCount: 2,
    thinkSeconds: 1,
    title: '审计日志检索结果',
    totalHit: rows.length,
    previewCount: rows.length,
    showPreviewHint: false,
    columns,
    rows,
  };
};
