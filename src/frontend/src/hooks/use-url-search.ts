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
import { buildURLParams } from '@utils/assist';

export default function () {
  const searchParams = new URLSearchParams(window.location.search);
  const notifyUrlChange = () => {
    window.dispatchEvent(new PopStateEvent('popstate'));
  };
  const getSearchParams = () => {
    const dangerousKeys = ['__proto__', 'constructor', 'prototype'];
    const curSearchParams = new URLSearchParams(window.location.search);
    const params = Object.create(null);
    Array.from(curSearchParams.keys()).forEach((key) => {
      if (dangerousKeys.includes(key)) return;
      params[key] = curSearchParams.get(key) || '';
    });
    return params;
  };
  const parseUrlParamValue = (value: string, escapedField: string, key: string) => {
    const trimmed = value.trim();
    // 仅解析 JSON 对象/数组，避免纯数字字符串（如超长 risk_id）被 JSON.parse 成 Number 后精度丢失
    if (!trimmed.startsWith('{') && !trimmed.startsWith('[')) {
      return value || '';
    }
    try {
      const parsed = JSON.parse(trimmed);
      if (typeof parsed === 'object' && parsed !== null && escapedField !== key) {
        return [parsed];
      }
      return parsed;
    } catch {
      return value || '';
    }
  };
  const getSearchParamsPost = (escapedField: string) => {
    const dangerousKeys = ['__proto__', 'constructor', 'prototype'];
    const curSearchParams = new URLSearchParams(window.location.search);
    const params = Object.create(null);
    Array.from(curSearchParams.keys()).forEach((key) => {
      if (dangerousKeys.includes(key)) return;

      // 处理参数名：如果以[]结尾，去掉[]
      const processedKey = key.endsWith('[]') ? key.slice(0, -2) : key;

      // 获取该key的所有值
      const values = curSearchParams.getAll(key);

      // 如果只有一个值，直接存储；如果有多个值，存储为数组
      if (values.length === 1) {
        params[processedKey] = parseUrlParamValue(values[0], escapedField, key);
      } else {
        params[processedKey] = values.map((value: string) => parseUrlParamValue(value, escapedField, key));
      }
    });
    return params;
  };

  const appendSearchParams = (params: Record<string, any>) => {
    const curSearchParams = new URLSearchParams(window.location.search);
    Object.keys(params).forEach((key) => {
      if (curSearchParams.has(key)) {
        curSearchParams.set(key, params[key]);
      } else {
        curSearchParams.append(key, params[key]);
      }
    });
    window.history.replaceState({}, '', `?${curSearchParams.toString()}`);
    notifyUrlChange();
  };

  const removeSearchParam = (paramKey: string | Array<string>) => {
    const keyList = Array.isArray(paramKey) ? paramKey : [paramKey];
    const curSearchParams = new URLSearchParams(window.location.search);
    keyList.forEach((key) => {
      curSearchParams.delete(key);
    });
    window.history.replaceState({}, '', `?${curSearchParams.toString()}`);
    notifyUrlChange();
  };

  const replaceSearchParams = (params: Record<string, any>) => {
    window.history.replaceState({}, '', `?${buildURLParams(params)}`);
    notifyUrlChange();
  };

  const mergeAndReplaceSearchParams = (params: Record<string, any>) => {
    replaceSearchParams({
      ...getSearchParams(),
      ...params,
    });
  };

  return {
    searchParams,
    getSearchParams,
    getSearchParamsPost,
    appendSearchParams,
    removeSearchParam,
    replaceSearchParams,
    mergeAndReplaceSearchParams,
  };
}
