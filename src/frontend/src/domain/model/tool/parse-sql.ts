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
export default class ParseSql {
  referenced_tables: Array<{
    table_name: string;
    alias: string | null;
    permission: {
      result: boolean
    };
  }>;
  sql_variables: Array<{
    raw_name: string,
    display_name: string,
    description: string,
    required: boolean,
  }>;
  result_fields: Array<{
    raw_name: string,
    display_name: string,
  }>;
  original_sql: string;

  constructor(payload = {} as ParseSql) {
    this.referenced_tables = payload.referenced_tables;
    this.sql_variables = payload.sql_variables;
    this.result_fields = payload.result_fields;
    this.original_sql = payload.original_sql;
  }
}
