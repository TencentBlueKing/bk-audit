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
export default class Scene {
  uid: string;
  scene_id: number;
  name: string;
  description: string;
  data_source: string;
  status: 'enabled' | 'disabled';
  managers: string[];
  users: string[];
  strategy_count: number;
  risk_count: number;
  created_by: string;
  updated_by: string;
  updated_at: string | null;
  systems: Record<string, any>[];
  iam_manager_group_id: string | null;
  iam_viewer_group_id: string | null;
  tables: Record<string, any>[];
  strategy_ids: number[];
  system_count: number;
  table_count: number;


  constructor(payload = {} as Scene) {
    this.uid = payload.uid;
    this.scene_id = payload.scene_id;
    this.name = payload.name;
    this.description = payload.description;
    this.data_source = payload.data_source;
    this.status = payload.status;
    this.managers = payload.managers || [];
    this.users = payload.users || [];
    this.strategy_count = payload.strategy_count || 0;
    this.risk_count = payload.risk_count || 0;
    this.created_by = payload.created_by;
    this.updated_by = payload.updated_by;
    this.updated_at = payload.updated_at;
    this.systems = payload.systems || [];
    this.iam_manager_group_id = payload.iam_manager_group_id;
    this.iam_viewer_group_id = payload.iam_viewer_group_id;
    this.strategy_ids = payload.strategy_ids || [];
    this.system_count = payload.system_count || 0;
    this.table_count = payload.table_count || 0;
    this.tables = payload.tables || [];
  }

  get isEnabled() {
    return this.status === 'enabled';
  }

  get statusText() {
    return this.status === 'enabled' ? '启用' : '停用';
  }
}
