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

import useRequest from '@hooks/use-request';

import type { INL2RiskFilterResponse } from '../types';

/**
 * 自然语言搜索解析 Hook
 * 负责调用 nl2risk_filter 接口，将用户自然语言转为结构化筛选条件
 * 支持 thread_id 多轮对话
 */
export default function useNLParse() {
  const parseResult = ref<INL2RiskFilterResponse | null>(null);
  const parseMessage = ref('');
  const threadId = ref('');

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
   * @param tags 当前用户有权限的标签列表
   * @param strategies 当前用户有权限的策略列表
   * @returns { filterConditions, message } 或 null
   */
  const parse = async (
    query: string,
    tags?: Array<{ id: number; name: string }>,
    strategies?: Array<{ id: number; name: string }>,
  ): Promise<{
    filterConditions: Record<string, any>;
    message: string;
  } | null> => {
    if (!query.trim()) return null;

    try {
      const params: Record<string, any> = {
        query,
      };
      if (tags && tags.length > 0) {
        params.tags = tags;
      }
      if (strategies && strategies.length > 0) {
        params.strategies = strategies;
      }
      // 多轮对话：传入上次的 thread_id
      if (threadId.value) {
        params.thread_id = threadId.value;
      }

      const result = await runNl2RiskFilter(params);

      if (!result) return null;

      parseResult.value = result;

      // 保存 thread_id，用于后续多轮对话
      if (result.thread_id) {
        threadId.value = result.thread_id;
      }

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

  // 清除解析结果和 thread_id
  const clearParseResult = () => {
    parseResult.value = null;
    parseMessage.value = '';
    threadId.value = '';
  };

  return {
    isParsing,
    parse,
    clearParseResult,
  };
}
