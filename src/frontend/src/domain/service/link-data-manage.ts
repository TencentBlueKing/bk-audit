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
import LInkDataModel from '@model/link-data/link-data';
import LinkDataDetailModel from '@model/link-data/link-data-detail';

import LinkDataSource from '../source/link-data-manage';

export default {

  /**
   * @desc 联表列表
   * @param { Object } params
   */
  fetchStrategyList(params: {
    label?: string
    name?: string,
    page: number,
    page_size: number
  }) {
    return LinkDataSource.getLinkDataList(
      params,
      {
        permission: 'page',
      },
    )
      .then(({ data }) => ({
        ...data,
        results: data.results.map(item => new LInkDataModel(item)),
      }));
  },
  /**
   * @desc 获取全部联表
   */
  fetchLinkTableAll() {
    return LinkDataSource.getLinkTableAll()
      .then(({ data }) => data);
  },
  /**
   * @desc 获取联表标签
   */
  fetchLinkTableTags() {
    return LinkDataSource.getLinkTableTags()
      .then(({ data }) => data);
  },
  /**
   * @desc 删除联表
   * @param { Number } id
   */
  deleteLinkData(params: { uid: string }) {
    return LinkDataSource.deleteLinkData(params)
      .then(({ data }) => data);
  },
  /**
  * @desc 获取联表详情
  * @param { String } id
  */
  fetchLinkDataDetail(params: { uid: string, version: number }) {
    return LinkDataSource.getLinkDataDetail(params)
      .then(({ data }) => new LinkDataDetailModel(data));
  },
  /**
   * @desc 新建联表
   * @param { Object } params
   */
  addLinkData(params: {
    table_name: string;
    tags: Array<string>;
    links: LinkDataDetailModel['config']['links']
  }) {
    return LinkDataSource.addLinkData(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 编辑联表
   */
  updateLinkData(params: {
    uid: string
    name: string;
    tags: Array<string>;
    links: LinkDataDetailModel['config']['links']
  }) {
    return LinkDataSource.updateLinkData(params)
      .then(({ data }) => data);
  },
};
