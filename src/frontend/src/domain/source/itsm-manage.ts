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

import type ServiceManageModel from '@model/itsm/service-detail';

import Request  from '@utils/request';

import ModuleBase from './module-base';

class ItsmManage  extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1/itsm/service';
  }
  // 获取服务列表
  getList() {
    return Request.get<Array<{
      id: number,
      name: string,
      url: string,
    }>>(`${this.module}/`);
  }
  // 单据状态常量
  getStatusCommon() {
    return Request.get<Array<{
      id: string,
      name: string
    }>>(`${this.module}/status_common/`);
  }
  // 获取服务详情
  getServiceDetail(params: {
    id: string
  }) {
    return Request.get<ServiceManageModel>(`${this.module}/${params.id}/`, {
      params,
    });
  }
}
export default new ItsmManage();
