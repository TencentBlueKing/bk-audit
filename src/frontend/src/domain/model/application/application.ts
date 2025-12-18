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
export default class Application {
  id: string;
  created_at: string;
  created_by: string;
  updated_at: string;
  updated_by: string;
  is_deleted: boolean;
  name: string;
  sops_template_id: number;
  rule_count: number;
  need_approve: boolean | string;
  approve_service_id: number;// 审批服务id

  approve_config: Record<string, any>;
  description: string;
  is_enabled: boolean;
  constructor(payload = {} as Application) {
    this.id = payload.id;

    this.created_at = payload.created_at;
    this.created_by = payload.created_by;
    this.updated_at = payload.updated_at;
    this.updated_by = payload.updated_by;
    this.is_deleted = payload.is_deleted;
    this.name = payload.name;
    this.sops_template_id = payload.sops_template_id;
    this.rule_count = payload.rule_count;
    this.need_approve = payload.need_approve;
    this.approve_service_id = payload.approve_service_id;
    this.approve_config = payload.approve_config;
    this.description = payload.description;
    this.is_enabled = payload.is_enabled;
  }
}
