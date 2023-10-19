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
export default class ServiceField {
  id: number;
  key: string;
  type: string;
  default: string;
  name: string;
  desc: string;
  choice: Array<{
    key: string,
    name: string,
  }>;
  layout: string;
  source_type: string;
  source_uri: string;
  api_instance_id: number;
  kv_relation: Record<string, any>;
  validate_type: string;
  regex: string;
  regex_config: Record<string, any>;
  custom_regex: string;
  show_type: number;
  show_conditions: Record<string, any>;
  constructor(payload = {} as ServiceField) {
    this.id = payload.id;
    this.key = payload.key;
    this.type = payload.type;
    this.default = payload.default;
    this.name = payload.name;
    this.desc = payload.desc;
    this.choice = payload.choice;
    this.layout = payload.layout;
    this.source_type = payload.source_type;
    this.source_uri = payload.source_uri;
    this.api_instance_id = payload.api_instance_id;
    this.kv_relation = payload.kv_relation;
    this.validate_type = payload.validate_type;
    this.regex = payload.regex;
    this.regex_config = payload.regex_config;
    this.custom_regex = payload.custom_regex;
    this.show_type = payload.show_type;
    this.show_conditions = payload.show_conditions;
  }
}
