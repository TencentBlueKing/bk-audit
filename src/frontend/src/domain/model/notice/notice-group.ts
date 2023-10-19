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
export default class NoticeGroup {
  group_id: number;
  group_name: string;
  created_at: string;
  created_by: string;
  updated_at: string;
  updated_by: string;
  is_deleted: boolean;
  group_member: Array<string>;
  notice_config: Array<{
    msg_type:string
  }>;
  description: string;
  permission:Record<string, boolean>;

  constructor(payload = {} as NoticeGroup) {
    this.group_id = payload.group_id;
    this.created_at = payload.created_at;
    this.created_by = payload.created_by;
    this.updated_at = payload.updated_at;
    this.updated_by = payload.updated_by;
    this.is_deleted = payload.is_deleted;
    this.group_name = payload.group_name;
    this.group_member = payload.group_member;
    this.notice_config = payload.notice_config;
    this.description = payload.description;
    this.permission = payload.permission;
  }
}
