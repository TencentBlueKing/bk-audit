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
const STATUS_SUCCESS = 'SUCCESS'; // 成功
const STATUS_RUNNING = 'RUNNING'; // 部署中
const STATUS_FAILED = 'FAILED'; // 失败
const STATUS_PARTFAILED = 'PARTFAILED'; // 部分失败
const STATUS_PREPARE = 'PREPARE'; // 准备中
const STATUS_UNKNOWN = 'UNKNOWN'; // 未知
const STATUS_TERMINATED = 'TERMINATED'; // 已停用
const STATUS_WARNING = 'WARNING'; // 已完成下发无配置

export default class BatchSubscriptionStatus {
  collector_id: number;
  subscription_id: number;
  status:string;
  status_name: string;
  total: number;
  success: number;
  failed: number;
  pending: number;

  static iconMap: Record<string, string> = {
    [STATUS_SUCCESS]: 'completed',
    [STATUS_RUNNING]: 'loading',
    [STATUS_FAILED]: 'cuo',
    [STATUS_PARTFAILED]: 'cuo',
    [STATUS_PREPARE]: 'loading',
    [STATUS_UNKNOWN]: 'cuo',
    [STATUS_TERMINATED]: 'cuo',
    [STATUS_WARNING]: 'weiwancheng',
  };

  static operationMap:  Record<string, string> = {
    [STATUS_SUCCESS]: 'operation',
    [STATUS_RUNNING]: 'detail',
    [STATUS_FAILED]: 'operation',
    [STATUS_PARTFAILED]: 'operation',
    [STATUS_PREPARE]: 'detail',
    [STATUS_UNKNOWN]: 'operation',
    [STATUS_TERMINATED]: 'operation',
    [STATUS_WARNING]: 'config',
  };

  constructor(payload = {} as BatchSubscriptionStatus) {
    this.collector_id = payload.collector_id;
    this.subscription_id = payload.subscription_id;
    this.status = payload.status;
    this.status_name = payload.status_name;
    this.total = payload.total;
    this.success = payload.success;
    this.failed = payload.failed;
    this.pending = payload.pending;
  }

  get icon() {
    return BatchSubscriptionStatus.iconMap[this.status];
  }

  get operation() {
    return BatchSubscriptionStatus.operationMap[this.status];
  }

  get isRunning() {
    return [
      STATUS_RUNNING,
      STATUS_PREPARE,
    ].includes(this.status);
  }
}
