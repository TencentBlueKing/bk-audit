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
export default class toolInfo {
  uid: string;
  name: string;
  version: number;
  tool_type: string;
  description: string;
  namespace: string;
  config?: {
    sql: string;
    output_fields: Array<{
      raw_name: string;
      description: string;
      display_name: string;
      drill_config: {
        tool: {
          uid: string;
          version: number;
        };
        config: Array<{
          source_field: string;
          target_field: string;
        }>;
      };
    }>;
    input_variable: Array<{
      choices: Array<string>;
      raw_name: string;
      required: boolean;
      description: string;
      display_name: string;
      field_category: string;
    }>;
    referenced_tables: Array<{
      table_name: string;
    }>;
  };
  permission: {
    use_tool: boolean;
  };
  strategies: Array<string>;
  tags: Array<string>;
  created_by: string;
  created_at: string;
  constructor(payload: toolInfo) {
    this.name = payload.name;
    this.uid = payload.uid;
    this.version = payload.version;
    this.tool_type = payload.tool_type;
    this.description = payload.description;
    this.namespace = payload.namespace;
    this.config = payload.config;
    this.permission = payload.permission;
    this.config = payload.config;
    this.tags = payload.tags;
    this.created_by = payload.created_by;
    this.created_at = payload.created_at;
    this.strategies = payload.strategies;
  }
}
