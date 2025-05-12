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
import EsQuerySource from '../source/es-query';


export default {
  /**
   * @desc 字段列表
   * @param { Object } params
   */
  fetchFieldMap(params: { fields: Array<string>, timedelta?: number }) {
    return EsQuerySource.getFieldMap(params, {
      permission: 'page',
      cache: true,
    })
      .then(({ data }) => data);
  },
  /**
   * @desc 搜索
   * @param { Object } params
   */
  fetchSearchList(params:
    {
      start_time: string,
      end_time: string,
      query_string?: string
      sort_list?: string,
      page: number,
      page_size: number
    }) {
    return EsQuerySource.getSearchList(params, {
      permission: 'page',
    })
      .then(({ data }) =>  ({
        ...data,
        results: data.results,
      }));
  },
  /**
   * @desc Doris新版搜索
   * @param { Object } params
   */
  fetchCollectorSearchList(params: Record<string, any>) {
    return EsQuerySource.getCollectorSearchList(params, {
      permission: 'page',
    })
      .then(({ data }) =>  ({
        ...data,
        results: data.results,
      }));
  },
  /**
   * @desc 获取日志检索字段
   */
  fetchSearchConfig() {
    return EsQuerySource.getSearchConfig()
      .then(({ data }) => data.map(item => ({
        ...item.field,
        allow_operators: item.allow_operators,
      })));
  },
  /**
   * @desc 获取日志统计
   */
  fetchSearchStatistic(params: Record<string, any>) {
    return EsQuerySource.getSearchStatistic(params)
      .then(({ data }) => data);
  },
};
