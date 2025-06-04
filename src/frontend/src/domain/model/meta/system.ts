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
const NORMAL = 'normal';
const NODATA = 'nodata';
const UNSET = 'unset';
export default class System {
  id: number;
  callback_url: string;
  clients: string;
  description: string;
  logo_url: string;
  managers: Array<string>;
  name: string;
  name_en: string;
  namespace: string;
  provider_config: {
    healthz: string
    host: string
  };
  source_type: string;
  system_id: string;
  system_url: string;

  // 权限
  permission: {
    edit_system: boolean,
    view_system: boolean
  };

  static iconMap: Record<string, string> = {
    [NORMAL]: 'normal',
    [NODATA]: 'abnormal',
    [UNSET]: 'unknown',
  };
  status_msg: string;
  status: string;
  last_time: string;
  model: {
    resources: number;
    operations: number;
  } | null;
  app_code: string;
  system_domain: string;
  created_at: string;
  created_by: string;

  constructor(payload = {} as System) {
    this.id = payload.id;
    this.callback_url = payload.callback_url;
    this.clients = payload.clients;
    this.description = payload.description;
    this.logo_url = payload.logo_url;
    this.managers = payload.managers || [];
    this.name = payload.name;
    this.name_en = payload.name_en;
    this.namespace = payload.namespace;
    this.system_id = payload.system_id;
    this.system_url = payload.system_url;
    this.permission = payload.permission;
    this.status_msg = payload.status_msg;
    this.status = payload.status;
    this.source_type = payload.source_type;
    this.last_time = payload.last_time;

    this.provider_config = this.initProviderConfig(payload.provider_config);
    this.model = {
      resources: 10,
      operations: 10,
    };
    this.app_code = payload.app_code;
    this.system_domain = payload.system_domain;
    this.created_at = payload.created_at;
    this.created_by = payload.created_by;
  }

  initProviderConfig(providerConfig: System['provider_config']) {
    if (!providerConfig) {
      return {
        healthz: '',
        host: '',
      };
    }
    return providerConfig;
  }

  get statusIcon() {
    return System.iconMap[this.status];
  }

  get managersText() {
    return this.managers.join(',');
  }
}
