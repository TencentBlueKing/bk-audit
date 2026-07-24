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
export type PanelVisibilityType = 'all_visible' | 'all_scenes' | 'all_systems'
  | 'specific_scenes' | 'specific_systems' | 'scenes_and_systems';

export interface PanelVisibilityPayload {
  visibility_type: PanelVisibilityType;
  scene_ids: number[];
  system_ids: string[];
}

/** 平台报表默认值覆盖（创建/编辑提交 & 管理列表回显） */
export interface PanelDefaultValueOverrides {
  scenes?: Record<string, Record<string, any>>;
  systems?: Record<string, Record<string, any>>;
}

/** 用户侧报表详情（按当前 scope 返回单份映射） */
export interface PanelDetail {
  id: string;
  vision_id: string;
  name: string;
  status: string;
  category: string;
  description: string;
  updated_by?: string;
  updated_at?: string;
  default_value_override?: Record<string, any>;
}

export default class PanelModel {
  id: string;
  name: string;
  description: string;
  binding_type: string;
  vision_id: string;
  priority_index: number;
  group_id: number;
  group_name: string;
  group_type: string;
  group_priority_index: number;
  updated_by: string;
  updated_at: string;
  category: string;
  status: 'published' | 'unpublished';
  is_enabled?: boolean;
  visibility_type?: PanelVisibilityType;
  scene_ids?: number[];
  system_ids?: string[];
  default_value_overrides?: PanelDefaultValueOverrides;

  constructor(payload: PanelModel) {
    this.id = payload.id;
    this.name = payload.name;
    this.description = payload.description;
    this.binding_type = payload.binding_type;
    this.vision_id = payload.vision_id;
    this.priority_index = payload.priority_index;
    this.group_id = payload.group_id;
    this.group_name = payload.group_name;
    this.group_type = payload.group_type;
    this.group_priority_index = payload.group_priority_index;
    this.updated_by = payload.updated_by;
    this.updated_at = payload.updated_at;
    this.category = payload.category;
    this.status = payload.status;
    this.is_enabled = payload.is_enabled;
    this.visibility_type = payload.visibility_type;
    this.scene_ids = payload.scene_ids;
    this.system_ids = payload.system_ids;
    this.default_value_overrides = payload.default_value_overrides;
  }
}
