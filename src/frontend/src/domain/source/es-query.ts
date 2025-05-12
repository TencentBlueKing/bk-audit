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
import type FieldMapModel from '@model/es-query/field-map';
import type SearchModel from '@model/es-query/search';
import type SearchStatisticModel from '@model/es-query/search_statistic';
import type StandardFieldModel from '@model/meta/standard-field';

import Request, {
  type IRequestPayload,
  type IRequestResponsePaginationData,
} from '@utils/request';

import ModuleBase from './module-base';

class EsQuery extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1/query';
  }
  // 字段列表
  getFieldMap(params: { fields: Array<string> }, payload = {} as IRequestPayload) {
    return Request.get<FieldMapModel>(`${this.path}/es_query/field_map/`, {
      params,
      payload,
    });
  }
  // 搜索
  getSearchList(params: {
    start_time: string,
    end_time: string,
    query_string?: string
    sort_list?: string,
    page: number,
    page_size : number
  }, payload = {} as IRequestPayload) {
    return Request.get<IRequestResponsePaginationData<SearchModel>>(`${this.path}/es_query/search/`, {
      params,
      payload,
    });
  }
  // Doris新版搜索
  getCollectorSearchList(params: Record<string, any>, payload = {} as IRequestPayload) {
    return Request.post<IRequestResponsePaginationData<SearchModel>>(`${this.path}/collector_query/search/`, {
      params,
      payload,
    });
  }
  // 获取日志检索字段
  getSearchConfig() {
    return Request.get<Array<{
      allow_operators: Array<string>,
      field: StandardFieldModel,
    }>>(`${this.path}/collector_query/search_config/`);
  }
  // 获取日志统计
  getSearchStatistic(params: Record<string, any>) {
    return Request.post<SearchStatisticModel>(`${this.path}/collector_query/search_statistic/`, {
      params,
    });
  }
}

export default new EsQuery();
