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
const STATUS_CLOSED = 'closed';
const STATUS_RUNNING = 'running';
const STATUS_FAILED = 'failed';
const STATUS_PREPARING = 'preparing';
export default class JoinData {
  resource_type_id: string;
  status: string;
  system_id:string;

  static componentMap: Record<string, string> = {
    [STATUS_CLOSED]: 'taskSwitch',
    [STATUS_RUNNING]: 'taskSwitch',
    [STATUS_FAILED]: 'taskFailed',
    [STATUS_PREPARING]: 'taskPreparing',
  };


  constructor(payload = {} as JoinData) {
    this.resource_type_id = payload.resource_type_id;
    this.status = payload.status;
    this.system_id = payload.system_id;
  }

  get taskComponent() {
    return JoinData.componentMap[this.status];
  }
}
