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

import Request from '@utils/request';

import ModuleBase from './module-base';

import type { IRequestPayload, IRequestResponsePaginationData } from '@/utils/request';

class LinkDataManage extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1/';
  }
  // 获取联表列表
  getLinkDataList(params: Record<string, any>, payload = {} as IRequestPayload) {
    return Request.get<IRequestResponsePaginationData<LInkDataModel>>(`${this.path}/link_table/`, {
      params,
      payload,
    });
  }
  // 获取全部联表
  getLinkTableAll() {
    return Request.get<Array<{
      uid:string,
      name: string,
      version: number,
    }>>(`${this.path}/link_table/all/`);
  }
  // 获取联表标签
  getLinkTableTags() {
    return Request.get<Array<{
      link_table_count: number,
      tag_id: string,
      tag_name: string
    }>>(`${this.path}/link_table/tags/`);
  }
  // 删除联表
  deleteLinkData(params: {
    uid: string
  }) {
    return Request.delete(`${this.path}/link_table/${params.uid}/`, {});
  }
  // 获取联表信息
  getLinkDataDetail(params: { uid: string}) {
    return Request.get<LinkDataDetailModel>(`${this.path}/link_table/${params.uid}/`, {});
  }
  // 新建联表
  addLinkData(params: {
    table_name: string;
    tags: Array<string>;
    links: LinkDataDetailModel['config']['links']
  }) {
    return Request.post(`${this.path}/link_table/`, {
      params,
    });
  }
  // 编辑联表
  updateLinkData(params: {
    uid: string
    name: string;
    tags: Array<string>;
    links: LinkDataDetailModel['config']['links']
  }) {
    return Request.put(`${this.path}/link_table/${params.uid}/`, {
      params,
    });
  }
}
export default new LinkDataManage();
