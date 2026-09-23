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

export type ExecutionStatus = 'success' | 'failed' | 'running';
export type ExecutionTrigger = 'manual' | 'auto' | 'retry';

export default class ExecutionRecord {
  task_id: string;
  task_name: string;
  application_id: string;
  application_name: string;
  risk_id: string;
  trigger_type: ExecutionTrigger;
  started_at: string;
  duration: string;
  status: ExecutionStatus;
  error: string;
  executor: string;
  scene_id: string;
  constructor(payload: Partial<ExecutionRecord> = {}) {
    this.task_id = payload.task_id || '';
    this.task_name = payload.task_name || '';
    this.application_id = payload.application_id || '';
    this.application_name = payload.application_name || '';
    this.risk_id = payload.risk_id || '';
    this.trigger_type = payload.trigger_type || 'auto';
    this.started_at = payload.started_at || '';
    this.duration = payload.duration || '';
    this.status = payload.status || 'running';
    this.error = payload.error || '';
    this.executor = payload.executor || '';
    this.scene_id = payload.scene_id || '';
  }
}
