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

import _ from 'lodash';
import { ref } from 'vue';

import RiskManageService from '@service/risk-manage';
import StrategyManageService from '@service/strategy-manage';

import useRequest from '@hooks/use-request';

import type { INL2RiskFilterResponse } from '../types';

export interface INLParseOptions {
  risk_view_type?: string;
  start_time?: string;
  end_time?: string;
  scope_type?: string;
  scope_id?: string;
  scenes?: Array<{ id: number; name: string }>;
}

const mapStrategyOptions = (list: Array<Record<string, any>>) => list
  .filter(item => item && (item.value ?? item.id))
  .map((item) => {
    const id = Number(item.value ?? item.id);
    const label = String(item.label || item.name || '');
    return {
      id,
      name: `${label}（${id}）`,
    };
  });

const mapTagOptions = (list: Array<Record<string, any>>) => list
  .filter(item => item && item.id && item.name)
  .map(item => ({
    id: Number(item.id),
    name: String(item.name),
  }));

const fetchScopedStrategies = async (options: INLParseOptions) => {
  const list = await StrategyManageService.fetchScopedStrategyList({
    risk_view_type: options.risk_view_type || 'all',
    start_time: options.start_time,
    end_time: options.end_time,
    scope_type: options.scope_type,
    scope_id: options.scope_id,
  });
  return mapStrategyOptions(list);
};

const fetchScopedTags = async (options: INLParseOptions) => {
  const list = await RiskManageService.fetchRiskTags({
    risk_view_type: options.risk_view_type || 'all',
    start_time: options.start_time,
    end_time: options.end_time,
    noNeedSceneParams: true,
    page: 1,
    page_size: 200,
  });
  return mapTagOptions(list);
};

/**
 * 自然语言搜索解析 Hook
 * 负责调用 nl2risk_filter 接口，将用户自然语言转为结构化筛选条件
 */
export default function useNLParse() {
  const parseResult = ref<INL2RiskFilterResponse | null>(null);
  const parseMessage = ref('');

  // 调用 nl2risk_filter 接口
  const {
    loading: isParsing,
    run: runNl2RiskFilter,
  } = useRequest(RiskManageService.nl2RiskFilter, {
    defaultValue: null as unknown as INL2RiskFilterResponse,
  });

  /**
   * 解析自然语言查询
   * @param query 用户输入的自然语言文本
   * @param options 当前风险列表上下文（时间范围、视图类型等），用于拉取策略/标签候选
   */
  const parse = async (
    query: string,
    options: INLParseOptions = {},
  ): Promise<{
    filterConditions: Record<string, any>;
    message: string;
  } | null> => {
    if (!query.trim()) return null;

    try {
      const [tags, strategies] = await Promise.all([
        fetchScopedTags(options),
        fetchScopedStrategies(options),
      ]);

      const params: Record<string, any> = {
        query,
      };
      if (tags.length > 0) {
        params.tags = tags;
      }
      if (strategies.length > 0) {
        params.strategies = strategies;
      }
      if (options.scenes && options.scenes.length > 0) {
        params.scenes = options.scenes;
      }
      if (options.scope_type) {
        params.scope_type = options.scope_type;
      }
      if (options.scope_id) {
        params.scope_id = options.scope_id;
      }
      const result = await runNl2RiskFilter(params);

      if (!result) return null;

      parseResult.value = result;

      const filterConditions = result.filter_conditions || {};
      const message = result.message || '';

      // AI 无法解析：filter_conditions 为空对象，message 有值
      const isEmptyConditions = _.isEmpty(filterConditions);
      if (isEmptyConditions && message) {
        parseMessage.value = message;
        return { filterConditions: {}, message };
      }

      // AI 正常解析：filter_conditions 有值
      if (!isEmptyConditions) {
        parseMessage.value = '';
        return { filterConditions, message: '' };
      }

      // 兜底：两者都为空
      parseMessage.value = '';
      return { filterConditions: {}, message: '' };
    } catch (error) {
      // AI 服务异常（HTTP 503 等）：返回错误提示信息
      parseMessage.value = 'AI 服务暂时不可用，请使用手动筛选';
      return { filterConditions: {}, message: 'AI 服务暂时不可用，请使用手动筛选' };
    }
  };

  // 清除解析结果
  const clearParseResult = () => {
    parseResult.value = null;
    parseMessage.value = '';
  };

  return {
    isParsing,
    parse,
    clearParseResult,
  };
}
