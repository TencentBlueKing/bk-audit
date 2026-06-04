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

export interface ConditionFilterValue {
  operator: string;
  filter: string;
  filters: string[];
  field?: { raw_name?: string };
}

const filtersToFilterString = (filters: string[]) => (
  filters.length === 1 ? String(filters[0]) : filters.join(',')
);

/**
 * 接口存储：eq → filter，非 eq → filters
 * 编辑回填：eq 取 filter 并清空 filters；非 eq 取 filters 并清空 filter
 */
export const normalizeConditionValueForDisplay = (c: ConditionFilterValue) => {
  const { operator } = c;
  if (!operator || ['isnull', 'notnull'].includes(operator)) {
    return c;
  }

  if (operator === 'eq') {
    const filter = !c.filter && c.filters?.length ? filtersToFilterString(c.filters) : c.filter;
    return {
      ...c,
      filter,
      filters: [],
    };
  }

  const filters = c.filter && (!c.filters?.length) ? c.filter.split(',').filter(Boolean) : c.filters;
  return {
    ...c,
    filter: '',
    filters,
  };
};

interface WhereLike {
  conditions: Array<{
    conditions: Array<{
      condition: ConditionFilterValue;
    }>;
  }>;
}

export const normalizeWhereForDisplay = (whereData?: WhereLike) => {
  if (!whereData?.conditions) return whereData;

  return {
    ...whereData,
    conditions: whereData.conditions.map(group => ({
      ...group,
      conditions: group.conditions?.map(item => ({
        ...item,
        condition: normalizeConditionValueForDisplay(item.condition),
      })),
    })),
  };
};
