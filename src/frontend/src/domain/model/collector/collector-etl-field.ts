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
export default class CollectorEtlField {
  field_name: string;
  created_at: string;
  created_by: string;
  updated_at: string;
  updated_by: string;
  field_type: string;
  alias_name: string;
  is_text: boolean;
  is_time: boolean;
  is_json: boolean;
  is_analyzed: boolean;
  is_dimension: boolean;
  is_delete: boolean;
  is_required: boolean;
  is_display: boolean;
  is_built_in: boolean;
  description: string;
  priority_index: number;
  constructor(payload = {} as CollectorEtlField) {
    this.field_name = payload.field_name;
    this.created_at = payload.created_at;
    this.created_by = payload.created_by;
    this.updated_at = payload.updated_at;
    this.updated_by = payload.updated_by;
    this.field_type = payload.field_type;
    this.alias_name = payload.alias_name;
    this.is_text = payload.is_text;
    this.is_time = payload.is_time;
    this.is_json = payload.is_json;
    this.is_analyzed = payload.is_analyzed;
    this.is_dimension = payload.is_dimension;
    this.is_delete = payload.is_delete;
    this.is_required = payload.is_required;
    this.is_display = payload.is_display;
    this.is_built_in = payload.is_built_in;
    this.description = payload.description;
    this.priority_index = payload.priority_index;
  }
}
