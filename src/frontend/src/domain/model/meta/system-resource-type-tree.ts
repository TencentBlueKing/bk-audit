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
export default class SystemResourceTypeTree {
  system_id: string;
  resource_type_id: string;
  unique_id: string;
  name: string;
  name_en: string;
  description: string;
  children: Array<SystemResourceTypeTree>;

  constructor(payload: SystemResourceTypeTree) {
    this.system_id = payload.system_id;
    this.resource_type_id = payload.resource_type_id;
    this.unique_id = `${payload.system_id}-${payload.resource_type_id}`;
    this.name = payload.name;
    this.name_en = payload.name_en;
    this.description = payload.description;
    this.children = payload.children;
  }
}
