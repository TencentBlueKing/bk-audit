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
import dayjs from 'dayjs';
import { computed, ref } from 'vue';

import StrategyManageService from '@service/strategy-manage';

import useRequest from '@hooks/use-request';
import type { RiskViewType } from '@hooks/use-risk-export-types';

type StrategyOption = {
  label: string;
  value: number | string;
};

const DETAIL_ROUTE_RISK_VIEW_TYPE_MAP: Record<string, RiskViewType> = {
  handleManageDetail: 'todo',
  processedManageDetail: 'processed',
  attentionManageDetail: 'watch',
  confirmManageDetail: 'confirm',
  sceneRiskManageDetail: 'all',
  riskManageDetail: 'all',
};

export const getRiskViewTypeByDetailRoute = (routeName?: string | null): RiskViewType => (
  DETAIL_ROUTE_RISK_VIEW_TYPE_MAP[routeName || ''] || 'all'
);

const mergeStrategyOptions = (
  target: Record<string, string>,
  list: StrategyOption[] = [],
) => {
  const next = { ...target };
  list.forEach((item) => {
    const id = item?.value;
    const label = String(item?.label || '').trim();
    if (id !== undefined && id !== null && id !== '' && label) {
      next[String(id)] = label;
    }
  });
  return next;
};

/**
 * 风险列表策略名称映射：合并全量策略与当前视图下的策略，用于表格列展示。
 */
export const useRiskListStrategyList = (riskViewType: RiskViewType) => {
  const strategyMap = ref<Record<string, string>>({});

  const updateStrategyMap = (list: StrategyOption[]) => {
    strategyMap.value = mergeStrategyOptions(strategyMap.value, list);
  };

  const scopedDefaultParams = {
    risk_view_type: riskViewType,
    start_time: dayjs(Date.now() - (86400000 * 182)).format('YYYY-MM-DD HH:mm:ss'),
    end_time: dayjs().format('YYYY-MM-DD HH:mm:ss'),
    isNeedSceneParams: true,
  };

  const {
    loading: allStrategyLoading,
  } = useRequest(StrategyManageService.fetchAllStrategyList, {
    manual: true,
    defaultValue: [],
    onSuccess: updateStrategyMap,
  });

  const {
    loading: scopedStrategyLoading,
  } = useRequest(StrategyManageService.fetchScopedStrategyList, {
    manual: true,
    defaultValue: [],
    defaultParams: scopedDefaultParams,
    onSuccess: updateStrategyMap,
  });

  const strategyList = computed<StrategyOption[]>(() => Object.entries(strategyMap.value)
    .map(([value, label]) => ({
      value: Number.isNaN(Number(value)) ? value : Number(value),
      label,
    })));

  const strategyLoading = computed(() => allStrategyLoading.value || scopedStrategyLoading.value);

  return {
    strategyList,
    strategyLoading,
  };
};
