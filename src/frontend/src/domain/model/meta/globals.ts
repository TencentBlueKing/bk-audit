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
export default class Globals {
  app_info: {
    app_code: string
  };
  data_delimiter: Array<Record<'id'|'name', string>>;
  data_encoding: Array<Record<'id'|'name', string>>;
  es_source_type: Array<Record<'id'|'name', string>>;
  etl_config: Array<Record<'id'|'name', string>>;
  param_conditions_match: Array<Record<'id'|'name', string>>;
  param_conditions_type: Array<Record<'id'|'name', string>>;
  storage_duration_time: Array<{
    id: number,
    name: string,
    default: boolean
  }>;
  bcs_log_type: Array<Record<'id'|'name', string>>;

  constructor(payload = {} as Globals) {
    this.app_info = payload.app_info;
    this.data_delimiter = payload.data_delimiter || [];
    this.data_encoding = payload.data_encoding || [];
    this.es_source_type = payload.es_source_type;
    this.etl_config = payload.etl_config || [];
    this.param_conditions_match = payload.param_conditions_match || [];
    this.param_conditions_type = payload.param_conditions_type || [];
    this.storage_duration_time = payload.storage_duration_time;
    this.bcs_log_type = payload.bcs_log_type || [];
  }
}
