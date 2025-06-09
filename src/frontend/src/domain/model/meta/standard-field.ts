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
export default class StandardField {
  alias_name: string;
  description: string;
  field_name: string;
  field_type: string;
  is_analyzed: boolean;
  is_delete: boolean;
  is_dimension: boolean;
  is_json: boolean;
  is_required: boolean;
  is_text: boolean;
  is_time: boolean;
  option: Record<string, any>;
  priority_index: number;
  property: {
    dynamic_content: boolean;
    sub_keys: Record<string, any>[];
  };
  allow_operators: string[];
  category: string;

  constructor(payload = {} as StandardField) {
    this.alias_name = payload.alias_name;
    this.description = payload.description;
    this.field_name = payload.field_name;
    this.field_type = payload.field_type;
    this.is_analyzed = payload.is_analyzed;
    this.is_delete = payload.is_delete;
    this.is_dimension = payload.is_dimension;
    this.is_json = payload.is_json;
    this.is_required = payload.is_required;
    this.is_text = payload.is_text;
    this.is_time = payload.is_time;
    this.option = payload.option || {};
    this.priority_index = payload.priority_index;
    this.property = payload.property || {
      dynamic_content: false,
      sub_keys: [],
    };
    this.allow_operators = payload.allow_operators || [];
    this.category = payload.category;
  }
}
