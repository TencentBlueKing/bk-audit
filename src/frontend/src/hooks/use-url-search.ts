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
  };

  const removeSearchParam = (paramKey: string | Array<string>) => {
    const keyList = Array.isArray(paramKey) ? paramKey : [paramKey];
    const curSearchParams = new URLSearchParams(window.location.search);
    keyList.forEach((key) => {
      curSearchParams.delete(key);
    });
    window.history.replaceState({}, '', `?${curSearchParams.toString()}`);
  };

  const replaceSearchParams = (params: Record<string, any>) => {
    window.history.replaceState({}, '', `?${buildURLParams(params)}`);
  };

  return {
    searchParams,
    getSearchParams,
    appendSearchParams,
    removeSearchParam,
    replaceSearchParams,
  };
}
