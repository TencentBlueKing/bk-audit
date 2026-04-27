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


export default class userPermissionConfig {
  edit_system: boolean;
  manage_platform: boolean;
  manage_scene: boolean;
  view_scene: boolean;
  view_system: boolean;

  constructor(payload = {} as userPermissionConfig) {
    this.edit_system = payload.edit_system;
    this.manage_platform = payload.manage_platform;
    this.manage_scene = payload.manage_scene;
    this.view_scene = payload.view_scene;
    this.view_system = payload.view_system;
  }
}
