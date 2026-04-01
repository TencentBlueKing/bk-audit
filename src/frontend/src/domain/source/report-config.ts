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


import Request from '@utils/request';

import PanelModel from './../model/report-config/panel';
import ModuleBase from './module-base';

class PanelManage extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1';
  }
  // 获取分组列表
  fetchGroups(params: {
    page: number,
    page_size: number,
  }) {
    return Request.get(`bkvision${this.module}/manage/group_manage/`, {
      params,
    });
  }
  // 获取分组Panel列表
  fetchPanels(params: {
    page: number,
    page_size: number,
    is_enabled?: boolean,
    keyword?: string,
  }) {
    return Request.get<PanelModel[]>(`bkvision${this.module}/manage/panel_manage/`, {
      params,
    });
  }
  // 创建Panel
  createPanel(params: {
    vision_id: string,
    name: string,
    group_name: string,
    description?: string,
    is_enabled?: boolean,
  }) {
    return Request.post(`bkvision${this.module}/manage/panel_manage/`, {
      params,
    });
  }
  // 更新Panel
  updatePanel(params: {
    id: string,
    name?: string,
    description?: string,
    group_name?: string,
    vision_id?: string,
    is_enabled?: boolean,
  }) {
    const { id, ...rest } = params;
    return Request.put(`bkvision${this.module}/manage/panel_manage/${id}/`, {
      params: rest,
    });
  }
  // 删除Panel
  deletePanel(params: { id: string }) {
    return Request.delete(`bkvision${this.module}/manage/panel_manage/${params.id}/`);
  }
  // 更新Panel排序
  orderPanels(params: {
    panels: Array<{
      id: string,
      group_id: number,
      priority_index: number,
    }>,
  }) {
    return Request.post(`bkvision${this.module}/manage/panel_manage/order/`, {
      params,
    });
  }
  // 更新分组排序
  orderGroups(params: {
    groups: Array<{
      id: number,
      priority_index: number,
    }>,
  }) {
    return Request.post(`bkvision${this.module}/manage/group_manage/order/`, {
      params,
    });
  }
}
export default new PanelManage();

