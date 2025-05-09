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
export default class RtzMeta  {
  result_table_id: string;
  result_table_name: string;
  result_table_name_alias: string;
  managers: Array<string>;
  processing_type: string;
  formatted_fields:  Array<{
    value: string;
    label: string;
    field_type: string;
    spec_field_type: string;
  }>;
  sensitivity_info: {
    biz_role_memebers: Array<string>;
  };

  constructor(payload = {} as RtzMeta) {
    this.result_table_id = payload.result_table_id;
    this.result_table_name = payload.result_table_name;
    this.result_table_name_alias = payload.result_table_name_alias;
    this.managers = payload.managers;
    this.processing_type = payload.processing_type;
    this.formatted_fields = payload.formatted_fields;
    this.sensitivity_info = payload.sensitivity_info;
  }
}
