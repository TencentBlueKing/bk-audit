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

import { ref } from 'vue';

import RiskManageService from '@service/risk-manage';

import useRequest from '@hooks/use-request';

import type { IFieldConfig } from '@components/search-box/components/render-field-config/config';

import type { INLParseResponse } from '../types';

/**
 * 自然语言搜索解析 Hook
 * 负责将用户输入的自然语言文本发送给后端 NLP 接口进行解析，
 * 返回结构化的搜索条件
 */
export default function useNLParse(fieldConfig: Record<string, IFieldConfig>) {
  const parseResult = ref<INLParseResponse | null>(null);
  const parseMessage = ref('');

  // 构建可用字段列表，传给后端帮助 NLP 理解
  const buildAvailableFields = () => Object.entries(fieldConfig).map(([name, config]) => ({
    name,
    label: config.label,
    type: config.type,
  }));

  // 调用后端 NLP 解析接口
  const {
    loading: isParsing,
    run: runParse,
  } = useRequest(RiskManageService.nlSearchParse, {
    defaultValue: null,
    onSuccess(data: INLParseResponse) {
      parseResult.value = data;
      parseMessage.value = data?.message || '';
    },
  });

  /**
   * 解析自然语言查询
   * @param query 用户输入的自然语言文本
   * @returns 解析后的结构化条件
   */
  const parse = async (query: string): Promise<Record<string, any> | null> => {
    if (!query.trim()) return null;

    const result = await runParse({
      query,
      available_fields: buildAvailableFields(),
    });

    if (result?.conditions) {
      return result.conditions;
    }
    return null;
  };

  // 清除解析结果
  const clearParseResult = () => {
    parseResult.value = null;
    parseMessage.value = '';
  };

  return {
    isParsing,
    parseResult,
    parseMessage,
    parse,
    clearParseResult,
  };
}
