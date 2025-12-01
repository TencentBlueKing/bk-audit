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
export default class DataIdDetail {
  bk_data_id: string;
  bk_biz_id: number;
  raw_data_name: string;// 数据源名称
  raw_data_alias: string;
  custom_type: string;
  sensitivity: string;
  data_encoding: string;
  bk_app_code: string;
  created_by: string;
  created_at: string;
  updated_by: string;
  updated_at: string;
  bkbase_url: string;
  description: string;
  active: boolean;
  etl_params:{
    es_unique_field_list: Array<string>;
    etl_flat: boolean;
    retain_original_text: boolean;
    separator_fields_remove: string;
    separator_node_action: string;
    separator_node_name: string;
    separator_node_source: string;
    regexp: string;
    regexp_keys?: Array<string>;
    delimiter: string;
  };
  custom_collector_ch_name: string;
  custom_collector_en_name: string;
  constructor(payload = {} as DataIdDetail) {
    this.bk_data_id = payload.bk_data_id;
    this.bk_biz_id = payload.bk_biz_id;
    this.etl_params = payload.etl_params;
    this.raw_data_name = payload.raw_data_name;
    this.raw_data_alias = payload.raw_data_alias;
    this.custom_type = payload.custom_type;
    this.sensitivity = payload.sensitivity;
    this.data_encoding = payload.data_encoding;
    this.bk_app_code = payload.bk_app_code;
    this.created_by = payload.created_by;
    this.created_at = payload.created_at;
    this.updated_by = payload.updated_by;
    this.updated_at = payload.updated_at;
    this.description = payload.description;
    this.active = payload.active;
    this.bkbase_url = payload.bkbase_url;
    this.custom_collector_ch_name = payload.custom_collector_ch_name;
    this.custom_collector_en_name = payload.custom_collector_en_name;
  }
}
