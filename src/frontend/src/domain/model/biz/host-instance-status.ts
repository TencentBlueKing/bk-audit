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
export default class HostInstanceStatus {
  agent_status: string;
  agent_status_name: string;
  bk_cloud_id: number;
  bk_cloud_name: string;
  bk_os_type: string;
  bk_supplier_id: string;
  ip: string;
  is_innerip: boolean;

  constructor(payload = {} as HostInstanceStatus) {
    this.agent_status = payload.agent_status;
    this.agent_status_name = payload.agent_status_name;
    this.bk_cloud_id = payload.bk_cloud_id;
    this.bk_cloud_name = payload.bk_cloud_name;
    this.bk_os_type = payload.bk_os_type;
    this.bk_supplier_id = payload.bk_supplier_id;
    this.ip = payload.ip;
    this.is_innerip = payload.is_innerip;
  }

  get primaryKey() {
    return  `#${this.bk_cloud_id}#${this.ip}`;
  }
}
