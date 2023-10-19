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
import type ApplicationManageModel from '@model/application/application';
import type ApplicationCreateManageModel from '@model/application/application-create';

import Request, {
  type IRequestPayload,
  type IRequestResponsePaginationData,
} from '@utils/request';

import ModuleBase from './module-base';

class ProcessApplicationManage extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1/process_applications';
  }
  // 获取处理套餐列表
  getApplicationList(params: {
    page: number,
    page_size: number
  }, payload = {} as IRequestPayload) {
    return Request.get<IRequestResponsePaginationData<ApplicationManageModel>>(`${this.module}/`, {
      params,
      payload,
    });
  }

  // 创建处理套餐
  create(params: ApplicationCreateManageModel) {
    return Request.post(`${this.module}/`, {
      params,
    });
  }
  // 获取处理套餐下拉列表
  getApplicationsAll() {
    return Request.get<Array<{
      id: string,
      name: string,
      sops_template_id: number,
      is_enabled: boolean,
    }>>(`${this.module}/all/`);
  }

  // 获取审批内置字段
  getInFields() {
    return Request.get<Array<{
      id: string,
      name: string,
    }>>(`${this.module}/approve_build_in_fields/`);
  }

  // 更新处理套餐
  update(params: ApplicationCreateManageModel) {
    return Request.put(`${this.module}/${params.id}/`, {
      params,
    });
  }

  // 获取处理套餐中的命中风险
  getRisks(params: {
    page: number,
    page_size: number,
    id: string
  }) {
    return Request.get(`${this.module}/${params.id}/risks/`, {
      params,
    });
  }

  // 获取处理套餐关联的规则
  getRuleList(params: {
    page: number,
    page_size: number,
    id: string
  }, payload = {} as IRequestPayload) {
    return Request.get(`${this.module}/${params.id}/rules/`, {
      params,
      payload,
    });
  }

  // 启停处理套餐
  toggleApplication(params: {
    id: string,
    is_enabled: boolean
  }) {
    return Request.put(`${this.module}/${params.id}/toggle/`, {
      params,
    });
  }
}
export default new ProcessApplicationManage();
