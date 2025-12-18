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
export default class CollectorCreateResult {
  bk_biz_id: number;
  collector_config_id: number;
  collector_config_name: string;
  collector_plugin_id: number;
  custom_type: string;
  id: string;
  system_id: string;
  task_id_list: Array<string>;

  constructor(payload = {} as CollectorCreateResult) {
    this.bk_biz_id = payload.bk_biz_id;
    this.collector_config_id = payload.collector_config_id;
    this.collector_config_name = payload.collector_config_name;
    this.collector_plugin_id = payload.collector_plugin_id;
    this.custom_type = payload.custom_type;
    this.id = payload.id;
    this.system_id = payload.system_id;
    this.task_id_list = payload.task_id_list;
  }
}
