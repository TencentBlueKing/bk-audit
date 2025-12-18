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

import type EventModel from '@model/event/event';
import type RiskModel from '@model/event/risk';

import Request, {
  type IRequestPayload,
  type IRequestResponsePaginationData,
} from '@utils/request';

import ModuleBase from './module-base';

class EventManage extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1';
  }

  // 获取事件列表
  getEventList(params: {
    page: number,
    page_size : number
  }, payload = {} as IRequestPayload) {
    return Request.get<IRequestResponsePaginationData<EventModel>>(`${this.module}/events/`, {
      params,
      payload,
    });
  }

  create(params : EventModel) {
    return Request.post(`${this.module}/events/`, {
      params,
    });
  }
  // 获取风险列表
  getRiskList(params: {
      page: number,
      page_size : number
    }, payload = {} as IRequestPayload) {
    return Request.get<IRequestResponsePaginationData<RiskModel>>(`${this.module}/risks/`, {
      params,
      payload,
    });
  }
}

export default new EventManage();
