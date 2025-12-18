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
const STATUS_RUNNING = 'RUNNING';
const STATUS_SUCCESS = 'SUCCESS';
const STATUS_FAILED = 'FAILED';
const STATUS_PENDING = '"PENDING"';
const STATUS_PARTFAILED = 'PARTFAILED';
const STATUS_TERMINATED = 'TERMINATED';
const STATUS_UNKNOWN = 'UNKNOWN';
const STATUS_PREPARE = 'PREPARE';

export class BcsContentChild {
  container_collector_config_id: number;
  name: string;
  status: string;
  constructor(payload = {} as BcsContentChild) {
    this.container_collector_config_id = payload.container_collector_config_id;
    this.name = payload.name;
    this.status = payload.status;
  }

  get isSuccessed() {
    return this.status === STATUS_SUCCESS;
  }

  get isFailed() {
    return this.status === STATUS_FAILED;
  }

  get isRunning() {
    return !this.isSuccessed && !this.isFailed;
  }

  get statusIconType() {
    if (this.isSuccessed) {
      return 'success';
    } if (this.isFailed) {
      return 'failed';
    }
    return 'loading';
  }

  get statusText() {
    const statusMap = {
      [STATUS_RUNNING]: '部署中',
      [STATUS_SUCCESS]: '成功',
      [STATUS_FAILED]: '失败',
      [STATUS_PENDING]: '等待中',
      [STATUS_PARTFAILED]: '部分失败',
      [STATUS_TERMINATED]: '已停用',
      [STATUS_UNKNOWN]: '未知',
      [STATUS_PREPARE]: '准备中',
    } as Record<string, string>;
    return statusMap[this.status];
  }
}

export class BcsContent {
  collector_config_id: number;
  collector_config_name: string;
  child: Array<BcsContentChild>;
  constructor(payload = {} as BcsContent) {
    this.collector_config_id = payload.collector_config_id;
    this.collector_config_name = payload.collector_config_name;
    this.child = this.initChild(payload.child);
  }

  get allList() {
    return this.child;
  }
  // task 成功
  get successList() {
    return this.child.reduce((result, item) => {
      if (item.isSuccessed) {
        result.push(item);
      }
      return result;
    }, [] as Array<BcsContentChild>);
  }
  // task 失败
  get failedList() {
    return this.child.reduce((result, item) => {
      if (item.isFailed) {
        result.push(item);
      }
      return result;
    }, [] as Array<BcsContentChild>);
  }
  // task 执行中
  get runningList() {
    return this.child.reduce((result, item) => {
      if (item.isRunning) {
        result.push(item);
      }
      return result;
    }, [] as Array<BcsContentChild>);
  }

  initChild(child: Array<BcsContentChild>) {
    if (!Array.isArray(child)) {
      return [];
    }
    return child.map(item => new BcsContentChild(item));
  }
}

export default class TaskStatus {
  static STATUS_RUNNING = STATUS_RUNNING;
  static STATUS_SUCCESS = STATUS_SUCCESS;
  static STATUS_FAILED = STATUS_FAILED;
  static STATUS_PENDING = STATUS_PENDING;
  static STATUS_PARTFAILED = STATUS_PARTFAILED;
  static STATUS_TERMINATED = STATUS_TERMINATED;
  static STATUS_UNKNOWN = STATUS_UNKNOWN;
  static STATUS_PREPARE = STATUS_PREPARE;

  task_ready: boolean;
  contents: Array<BcsContent>;

  constructor(payload = {} as TaskStatus) {
    this.task_ready = Boolean(payload.task_ready);
    this.contents = this.initContent(payload.contents);
  }

  get allList() {
    const recordMap: Record<string, boolean> = {};
    const result: Array<BcsContentChild> = [];
    this.contents.forEach((content) => {
      content.child.forEach((child) => {
        const key = `#${child.container_collector_config_id}#${child.name}`;
        if (!recordMap[key]) {
          result.push(child);
          recordMap[key] = true;
        }
      });
    });
    return result;
  }
  // task 成功
  get successList() {
    return this.allList.reduce((result, item) => {
      if (item.isSuccessed) {
        result.push(item);
      }
      return result;
    }, [] as Array<BcsContentChild>);
  }
  // task 失败
  get failedList() {
    return this.allList.reduce((result, item) => {
      if (item.isFailed) {
        result.push(item);
      }
      return result;
    }, [] as Array<BcsContentChild>);
  }
  // task 执行中
  get runningList() {
    return this.allList.reduce((result, item) => {
      if (item.isRunning) {
        result.push(item);
      }
      return result;
    }, [] as Array<BcsContentChild>);
  }

  initContent(content: Array<BcsContent>) {
    if (!Array.isArray(content)) {
      return [];
    }
    return content.map(item => new BcsContent(item));
  }
}
