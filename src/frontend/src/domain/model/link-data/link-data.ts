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
export default class LinkData {
  id: number;
  uid: string;
  name: number|string;
  tags: Array<string>;
  strategy_count: number;
  updated_by: string;
  updated_at: string;
  created_by: string;
  created_at: string;
  permission: {
    delete_link_table: boolean
    edit_link_table: boolean
    view_link_table: boolean
  };
  version: number;
  need_update_strategy: boolean;

  constructor(payload = {} as LinkData) {
    this.id = payload.id;
    this.uid = payload.uid;
    this.name = payload.name;
    this.tags = payload.tags;
    this.strategy_count = payload.strategy_count;
    this.updated_by = payload.updated_by;
    this.updated_at = payload.updated_at;
    this.created_by = payload.created_by;
    this.created_at = payload.created_at;
    this.permission = payload.permission;
    this.version = payload.version;
    this.need_update_strategy = payload.need_update_strategy;
  }
}
