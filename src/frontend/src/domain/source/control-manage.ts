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
import type ControlModel from '@model/control/control';

import Request from '@utils/request';

import ModuleBase from './module-base';

class ControlManage extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1';
  }
  // 控件
  getControlTypes(params: {
    control_type_id: string
  }) {
    return Request.get<Array<{
      control_type_id: string,
      control_id: string,
      control_name: string,
      versions: Array<{
        control_id: string,
        control_version: number,
      }>
    }>>(`${this.module}/control_types/${params.control_type_id}/`, {
      params,
    });
  }
  // 控件版本详情
  getControlDetail(params: {
    control_id: string,
    control_version: string,
  }) {
    return Request.get<ControlModel>(`${this.module}/controls/${params.control_id}/`, {
      params,
    });
  }
}
export default new ControlManage();
