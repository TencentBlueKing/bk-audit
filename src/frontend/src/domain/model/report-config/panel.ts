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
export default class PanelModel {
  id: string;
  name: string;
  description: string;
  vision_id: string;
  is_enabled: boolean;
  priority_index: number;
  group_id: number;
  group_name: string;
  group_priority_index: number;
  updated_by: string;
  updated_at: string;

  constructor(payload: PanelModel) {
    this.id = payload.id;
    this.name = payload.name;
    this.description = payload.description;
    this.vision_id = payload.vision_id;
    this.is_enabled = payload.is_enabled;
    this.priority_index = payload.priority_index;
    this.group_id = payload.group_id;
    this.group_name = payload.group_name;
    this.group_priority_index = payload.group_priority_index;
    this.updated_by = payload.updated_by;
    this.updated_at = payload.updated_at;
  }
}
