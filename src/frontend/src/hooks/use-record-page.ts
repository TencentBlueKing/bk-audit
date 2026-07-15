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
import useUrlSearch from './use-url-search';

const AUDIT_PAGE_PARAMS = 'audit-page-params';

/** 按页面隔离，避免不同列表间串用搜索条件 */
const getStorageKey = (pageKey?: string) => (
  pageKey ? `${AUDIT_PAGE_PARAMS}:${pageKey}` : AUDIT_PAGE_PARAMS
);

const getRecordPageParams = (pageKey?: string) => {
  const tempPagination = sessionStorage.getItem(getStorageKey(pageKey));
  if (tempPagination) {
    return JSON.parse(tempPagination);
  }
  return null;
};
const recordPageParams = (pageKey?: string) => {
  const { getSearchParams } = useUrlSearch();
  const params = getSearchParams();
  const filterParams: Record<string, any> = {};
  Object.keys(params).forEach((key) => {
    if (params[key]) {
      filterParams[key] = params[key];
    }
  });
  sessionStorage.setItem(getStorageKey(pageKey), JSON.stringify(filterParams));
};
const removePageParams = (pageKey?: string) => {
  sessionStorage.removeItem(getStorageKey(pageKey));
};
export default {
  removePageParams,
  recordPageParams,
  getRecordPageParams,

};
