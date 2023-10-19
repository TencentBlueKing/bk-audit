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


import NoticeGroupsModel from '@model/notice/notice-group';

import NoticeGroupSource from '../source/notice-group';

export default {

  /**
   * @desc 获取消息类型
   */
  fetchMsgType() {
    return NoticeGroupSource.getMsgType()
      .then(({ data }) => data);
  },
  /**
   * @desc 获取通知组列表
   */
  fetchGroupList(params: {
    page: number,
    page_size : number
  }) {
    return NoticeGroupSource.getGroupList(
      params,
      {
        permission: 'page',
      },
    )
      .then(({ data }) =>  ({
        ...data,
        results: data.results.map(item => new NoticeGroupsModel(item)),
      }));
  },
  /**
   * @desc 新建通知组
   */
  addGroup(params: {
    group_name: string;
    group_member: Array<string>,
    notice_config: Array<{
      msg_type: string;
    }>;
    description: string;
  }) {
    return NoticeGroupSource.addGroup(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取通知组下拉列表
   */
  fetchGroupSelectList() {
    return NoticeGroupSource.getGroupSelectList()
      .then(({ data }) => data);
  },

  /**
   * @desc 获取通知组下拉列表
   */
  getGroupDetail(params: {
    group_id :string
  }) {
    return NoticeGroupSource.getGroupDetail(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取通知组下拉列表
   */
  updateGroup(params: NoticeGroupsModel) {
    return NoticeGroupSource.updateGroup(params)
      .then(({ data }) => data);
  },

  /**
   * @desc 获取通知组下拉列表
   */
  deleteGroup(params: {
    group_id:number
  }) {
    return NoticeGroupSource.deleteGroup(params)
      .then(({ data }) => data);
  },
};
