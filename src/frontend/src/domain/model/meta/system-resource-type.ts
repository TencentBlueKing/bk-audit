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
const STATUS_CLOSED = 'closed';
const STATUS_RUNNING = 'running';
const STATUS_PREPARING = 'preparing';
const STATUS_FAILED = 'failed';
export default class SystemResourceType {
  bkbase_url: string;
  name: string;
  name_en: string;
  resource_type_id: string;
  description: string;
  sensitivity: number;
  provider_config: {
    path: string;
  };
  version: number;
  status: string;
  // 权限
  permission: {
    manage_global_setting: boolean
  };

  static switchMap: Record<string, boolean> = {
    [STATUS_CLOSED]: false,
    [STATUS_RUNNING]: true,
  };

  static textMap: Record<string, string> = {
    [STATUS_CLOSED]: '停用',
    [STATUS_RUNNING]: '启用',
    [STATUS_PREPARING]: '停用',
    [STATUS_FAILED]: '停用',
  };

  constructor(payload: SystemResourceType) {
    this.resource_type_id = payload.resource_type_id;
    this.description = payload.description;
    this.name = payload.name;
    this.name_en = payload.name_en;
    this.sensitivity = payload.sensitivity;
    this.provider_config = payload.provider_config;
    this.version = payload.version;
    this.status = payload.status;
    this.bkbase_url = payload.bkbase_url;
    this.permission = payload.permission;
  }

  get swithValue() {
    return SystemResourceType.switchMap[this.status];
  }

  get statusText() {
    return SystemResourceType.textMap[this.status];
  }
}
