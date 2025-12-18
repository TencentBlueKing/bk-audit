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
export default class SystemAction {
  action_id: string;
  description: string;
  name: string;
  name_en: string;
  sensitivity: number;
  type: string;
  version: string;
  resource_type_ids: Array<string>;
  unique_id: string;

  constructor(payload = {} as SystemAction) {
    this.action_id = payload.action_id;
    this.description = payload.description;
    this.name = payload.name;
    this.name_en = payload.name_en;
    this.sensitivity = payload.sensitivity;
    this.type = payload.type;
    this.version = payload.version;
    this.resource_type_ids = payload.resource_type_ids;
    this.unique_id = payload.unique_id;
  }

  get isSensitivity() {
    return this.sensitivity !== 0;
  }
}
