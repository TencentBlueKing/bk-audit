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
export default class Control {
  id: number;
  created_at: string;
  created_by: string;
  updated_at: string;
  updated_by: string;
  is_deleted: boolean;
  control_id: string;
  control_version: number;
  input_config: Record<string, any>;
  output_config: Record<string, any>;
  variable_config: Record<string, any>;
  extra_config: Record<string, any>;

  constructor(payload = {} as Control) {
    this.id = payload.id;
    this.created_at = payload.created_at;
    this.created_by = payload.created_by;
    this.updated_at = payload.updated_at;
    this.updated_by = payload.updated_by;
    this.is_deleted = payload.is_deleted;
    this.control_id = payload.control_id;
    this.control_version = payload.control_version;
    this.input_config = payload.input_config;
    this.output_config = payload.output_config;
    this.variable_config = payload.variable_config;
    this.extra_config = payload.extra_config;
  }
}
