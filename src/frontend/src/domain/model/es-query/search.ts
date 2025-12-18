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
import _ from 'lodash';

export default class Search {
  access_source_ip: string;
  access_type: string;
  access_user_agent: string;
  action_id: number;
  bk_app_code: string;
  bk_data_id: number;
  bk_receive_time: number;
  cloudId: number;
  collector_config_id: string;
  dtEventTimeStamp: string;
  end_time: string;
  event_content: string;
  event_id: string;
  extend_data: {
    [key: string]: string
  };
  gseIndex: number;
  instance_data: {
    [key: string]: string
  } | string;
  instance_id: number;
  instance_name: string;
  instance_origin_data: {
    [key: string]: string
  } | string;
  iterationIndex: number;
  log: string;
  path: string;
  request_id: number;
  resource_type_id: string;
  result_code: number;
  result_content: string;
  serverIp: string;
  snapshot_action_info: {
    [key: string]: any;
  };
  snapshot_user_info: {
    username: string;
    display_name: string;
    leader_username: string;
    gender: string;
    department_id: number;
    department_name: string;
    department_full_name: string;
    department_path: string;
    staff_status: string;
    staff_type: number;
    manager_unit_name: number;
    manage_level: number;
    workplace: string;
    aisle: string;
    hire_date: string;
    dimission_date: string;
    birthday: string;
    telephone: string;
    qq: string;
    weixin: string;
  };
  snapshot_instance_data: {
    [key: string]: string
  };
  snapshot_instance_name: string;
  snapshot_resource_type_info: {
    [key: string]: any
  };
  start_time: string;
  system_id: string;
  system_info: {
    id: number;
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
    system_id: string;
    system_url: string;
  };
  time: string;
  username: string;
  user_identify_type: string;
  user_identify_tenant_id: number;
  __ext: {
    [key: string]: string
  };
  _iteration_idx: number;

  constructor(payload = {} as Search) {
    this.event_id = payload.event_id;
    this.event_content = payload.event_content;
    this.action_id = payload.action_id;
    this.bk_app_code = payload.bk_app_code;
    this.bk_data_id = payload.bk_data_id;
    this.bk_receive_time = payload.bk_receive_time;
    this.collector_config_id = payload.collector_config_id;
    this.dtEventTimeStamp = payload.dtEventTimeStamp;
    this.request_id = payload.request_id;
    this.username = payload.username;
    this.start_time = payload.start_time;
    this.end_time = payload.end_time;
    this.extend_data = payload.extend_data;
    this.access_type = payload.access_type;
    this.access_source_ip = payload.access_source_ip;
    this.cloudId = payload.cloudId;
    this.instance_id = payload.instance_id;
    this.instance_name = payload.instance_name;
    this.instance_data = payload.instance_data || {};
    this.instance_origin_data = payload.instance_origin_data || {};
    this.result_code = payload.result_code;
    this.result_content = payload.result_content;
    this.iterationIndex =  payload.iterationIndex;
    this.resource_type_id = payload.resource_type_id;
    this.time = payload.time;
    this.system_id = payload.system_id;
    this.system_info = payload.system_info;
    this.snapshot_action_info = payload.snapshot_action_info || {};
    this.snapshot_user_info = payload.snapshot_user_info || {};
    this.snapshot_resource_type_info = payload.snapshot_resource_type_info || {};
    this.log = payload.log;
    this.gseIndex = payload.gseIndex;
    this.serverIp = payload.serverIp;
    this.snapshot_instance_data = payload.snapshot_instance_data;
    this.snapshot_instance_name = payload.snapshot_instance_name;
    this.user_identify_type = payload.user_identify_type;
    this.user_identify_tenant_id = payload.user_identify_tenant_id;
    this.access_user_agent = payload.access_user_agent;
    this.path = payload.path;
    // eslint-disable-next-line no-underscore-dangle
    this.__ext = payload.__ext;
    // eslint-disable-next-line no-underscore-dangle
    this._iteration_idx = payload._iteration_idx;

    this.snapshot_action_info = this.initSnapshotActionInfo(payload.snapshot_action_info);
    this.snapshot_resource_type_info = this.initSnapshotResourceTypeInfo(payload.snapshot_resource_type_info);
  }

  initSnapshotActionInfo(params: Search['snapshot_action_info']) {
    if (!_.isObject(params)) {
      return {
        snapshot_action_info: {
          action_id: '',
          description: '',
          type: '',
          sensitivity: '',
          name: '',
          updated_at: '',
          version: '',
        },
      };
    }
    return params;
  }

  initSnapshotResourceTypeInfo(params: Search['snapshot_resource_type_info']) {
    if (!_.isObject(params)) {
      return {
        snapshot_action_info: {
          resource_type_id: '',
          description: '',
          sensitivity: '',
          name: '',
          updated_at: '',
          version: '',
        },
      };
    }
    return params;
  }
}

