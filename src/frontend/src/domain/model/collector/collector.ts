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
export default class Collector {
  bk_biz_id: number;
  bk_data_id: number;
  bkbase_table_id: string;
  collector_config_id: number;
  collector_config_name: string;
  collector_config_name_en: string;
  collector_plugin_id:number;
  custom_type: string;
  description: string;
  has_storage: boolean;
  processing_id: string;
  system_id: string;
  source_platform: string;
  permission: {
    manage_collection_v2_bk_log: boolean;
    view_collection_v2_bk_log: boolean;
  };
  tail_log_time: string;  // 最后一条数据时间

  constructor(payload = {} as Collector) {
    this.bk_biz_id = payload.bk_biz_id;
    this.source_platform = payload.source_platform;
    this.bk_data_id = payload.bk_data_id;
    this.bkbase_table_id = payload.bkbase_table_id;
    this.collector_plugin_id = payload.collector_plugin_id;
    this.collector_config_id = payload.collector_config_id;
    this.collector_config_name = payload.collector_config_name;
    this.collector_config_name_en = payload.collector_config_name_en;
    this.custom_type = payload.custom_type;
    this.description = payload.description;
    this.has_storage = Boolean(payload.has_storage);
    this.processing_id = payload.processing_id;
    this.system_id = payload.system_id;
    this.permission = payload.permission;
    this.tail_log_time = payload.tail_log_time;
  }
}
