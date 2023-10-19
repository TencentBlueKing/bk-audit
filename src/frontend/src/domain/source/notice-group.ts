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
import type NoticeGroupsModel from '@model/notice/notice-group';

import Request, {
  type IRequestPayload,
  type IRequestResponsePaginationData,
} from '@utils/request';

import ModuleBase from './module-base';

class NoticeGroup extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1/notice_groups';
  }
  // 消息类型
  getMsgType() {
    return Request.get('/api/v1/notice/msg_type/');
  }

  // 获取通知组列表
  getGroupList(params: {
    page: number,
    page_size: number
  }, payload = {} as IRequestPayload) {
    return Request.get<IRequestResponsePaginationData<NoticeGroupsModel>>(`${this.module}/`, {
      params,
      payload,
    });
  }
  // 新建通知组
  addGroup(params: {
    group_name: string;
    group_member: Array<string>,
    notice_config: Array<{
      msg_type: string;
    }>;
    description: string;
  }) {
    return Request.post(`${this.module}/`, {
      params,
    });
  }

  // 获取通知组下拉列表
  getGroupSelectList() {
    return Request.get<Array<{
      id: string;
      name: string
    }>>(`${this.module}/all/`);
  }

  // 获取通知组详情
  getGroupDetail(params: {
    group_id: string
  }) {
    return Request.get<NoticeGroupsModel>(`${this.module}/${params.group_id}/`, {
      params,
    });
  }

  // 更新通知组
  updateGroup(params: NoticeGroupsModel) {
    return Request.put(`${this.module}/${params.group_id}/`, {
      params,
    });
  }

  // 更新通知组
  deleteGroup(params: {
    group_id: number
  }) {
    return Request.delete(`${this.module}/${params.group_id}/`, {
      params,
    });
  }
}
export default new NoticeGroup();
