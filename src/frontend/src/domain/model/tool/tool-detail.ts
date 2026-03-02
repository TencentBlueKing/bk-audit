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

export interface OutputFields {
  raw_name: string;
  display_name: string;
  description: string;
  drill_config: Array<{
    tool: {
      uid: string;
      version: number;
    };
    drill_name: string;
    config: Array<{
      source_field: string;
      target_value_type: string;
      target_value: string;
    }>
  }>;
  enum_mappings: {
    collection_id: string;
    mappings: Array<{
      key: string;
      name: string;
    }>;
  };
}
export default class ToolDetail {
  uid: string;
  name: string;
  version: number;
  area?: string;
  bkVersion?: string;
  radioGroupValue?: string;
  users?: string[];
  tool_type: string;
  description: string;
  namespace: string;
  tags: Array<string>;
  created_at: string;
  created_by: string;
  permission:{
    use_tool: boolean;
    manage_tool: boolean;
  };
  strategies: Array<string>;
  updated_at: string;
  updated_by: string;
  updated_time: string;
  data_search_config_type: string;
  is_bkvision: boolean;
  config: {
    referenced_tables: Array<{
      table_name: string | null;
      alias: string | null;
      permission: {
        result: boolean;
      };
    }>;
    input_variable: Array<{
      raw_name: string;
      display_name: string;
      description: string;
      is_default_value?: boolean;
      required: boolean;
      raw_default_value?: string;
      field_category: string;
      default_value: string | Array<string>;
      choices: Array<{
        key: string,
        name: string
      }>
    }>;
    // SQL 类工具
    output_fields?: Array<OutputFields>;
    // API 类工具
    output_config?: {
      enable_grouping: boolean;
      groups: Array<{
        name: string;
        output_fields: {
          raw_name: string;
          display_name: string;
          description: string;
          json_path: string;
          field_config: Array<{
            field_type: string;
            output_fields ?: Array<OutputFields>; // 表格类型才有
          }>;
        };
      }>;
    };
    sql: string;
    uid: string;
    updated_at: string;
    updated_by: string;
    updated_time: string;
  };
  constructor(payload = {} as ToolDetail) {
    this.name = payload.name;
    this.uid = payload.uid;
    this.version = payload.version;
    this.tool_type = payload.tool_type;
    this.description = payload.description;
    this.namespace = payload.namespace;
    this.config = payload.config;
    this.tags = payload.tags;
    this.data_search_config_type = payload.data_search_config_type;
    this.config = payload.config;
    this.permission = payload.permission;
    this.strategies = payload.strategies;
    this.created_by = payload.created_by;
    this.created_at = payload.created_at;
    this.updated_at = payload.updated_at;
    this.updated_by = payload.updated_by;
    this.updated_time = payload.updated_time;
    this.is_bkvision = payload.is_bkvision;
  }
}
