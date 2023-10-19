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
export default class AppInfo {
  app_code: string;
  app_name: string;
  developers: Array<string>;
  status: string;
  status_msg: string;
  system_url: string;

  constructor(payload = {} as AppInfo) {
    this.app_code = payload.app_code;
    this.app_name = payload.app_name;
    this.developers = payload.developers || [];
    this.status = payload.status;
    this.status_msg = payload.status_msg;
    this.system_url = payload.system_url;
  }

  get developerText() {
    return this.developers.join(',');
  }
}
