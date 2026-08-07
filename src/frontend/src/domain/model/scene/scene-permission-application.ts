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
export default class ScenePermissionApplication {
  id: number | string;
  scene_id: number;
  scene_name: string;
  applicant: string;
  role: string;
  role_display: string;
  reason: string;
  itsm_sn: string;
  itsm_ticket_url: string;
  status: string;
  status_display: string;
  grant_status: string;
  grant_status_display: string;
  approvers: string | string[];
  reject_reason: string;
  created_at: string;

  constructor(payload = {} as ScenePermissionApplication) {
    this.id = payload.id;
    this.scene_id = payload.scene_id;
    this.scene_name = payload.scene_name;
    this.applicant = payload.applicant;
    this.role = payload.role;
    this.role_display = payload.role_display;
    this.reason = payload.reason;
    this.itsm_sn = payload.itsm_sn;
    this.itsm_ticket_url = payload.itsm_ticket_url;
    this.status = payload.status;
    this.status_display = payload.status_display;
    this.grant_status = payload.grant_status;
    this.grant_status_display = payload.grant_status_display;
    this.approvers = payload.approvers;
    this.reject_reason = payload.reject_reason;
    this.created_at = payload.created_at;
  }
}
