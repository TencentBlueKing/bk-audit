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
import {
  createBaseRiskColumns,
  createRiskIdColumn,
  type RiskColumnDeps,
} from './base-columns';

export interface UseRiskColumnsOptions {
  deps: RiskColumnDeps;
  detailRouteName: string;
  overrides?: Record<string, Record<string, any>>;
  excludeColumns?: string[];
  appendColumns?: any[];
}
export const useRiskColumns = (options: UseRiskColumnsOptions) => {
  const { deps, detailRouteName, overrides, excludeColumns, appendColumns } = options;
  const baseColumns = createBaseRiskColumns(deps);
  const riskIdColumn = createRiskIdColumn(detailRouteName);
  const rowSelectCol = baseColumns.find((c: any) => c.colKey === 'row-select');
  const restColumns = baseColumns.filter((c: any) => c.colKey !== 'row-select');
  let columns: any[] = [
    ...(rowSelectCol ? [rowSelectCol] : []),
    riskIdColumn,
    ...restColumns,
  ];

  if (overrides) {
    columns = columns.map((col: any) => {
      const key = col.colKey || col.type;
      const override = overrides[key];
      return override ? { ...col, ...override } : col;
    });
  }

  if (excludeColumns?.length) {
    columns = columns.filter((col: any) => {
      const key = col.colKey || col.type;
      return !excludeColumns.includes(key);
    });
  }

  if (appendColumns?.length) {
    columns.push(...appendColumns);
  }

  return columns;
};

export type { RiskColumnDeps } from './base-columns';
export { createBaseRiskColumns, createRiskIdColumn } from './base-columns';
