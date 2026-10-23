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

import type { ExecutionStatus, ExecutionTrigger } from './execution-record';

export interface ExecutionAttempt {
  id: string;
  label: string;
  status: ExecutionStatus;
  started_at: string;
  ended_at: string;
  duration: string;
  executor: string;
  error: string;
  nodes: ExecutionNode[];
}

export interface ExecutionNode {
  name: string;
  status: ExecutionStatus;
  started_at: string;
  duration: string;
  error: string;
}

export interface ExecutionParam {
  name: string;
  value: string;
}

export default class ExecutionDetail {
  task_id: string;
  sops_task_id: string;
  sops_task_url: string;
  task_name: string;
  application_id: string;
  application_name: string;
  risk_id: string;
  risk_title: string;
  risk_level: string;
  risk_owner: string;
  risk_type: string;
  risk_evidence: string;
  risk_source: string;
  risk_description: string;
  risk_found_at: string;
  strategy_id: string;
  strategy_name: string;
  raw_event_id: string;
  trigger_type: ExecutionTrigger;
  started_at: string;
  ended_at: string;
  duration: string;
  status: ExecutionStatus;
  error: string;
  executor: string;
  scene_id: string;
  params: ExecutionParam[];
  nodes: ExecutionNode[];
  attempts: ExecutionAttempt[];
  constructor(payload = {} as ExecutionDetail) {
    this.task_id = payload.task_id;
    this.sops_task_id = payload.sops_task_id || '';
    this.sops_task_url = payload.sops_task_url || '';
    this.task_name = payload.task_name;
    this.application_id = payload.application_id;
    this.application_name = payload.application_name;
    this.risk_id = payload.risk_id;
    this.risk_title = payload.risk_title || '';
    this.risk_level = payload.risk_level || '';
    this.risk_owner = payload.risk_owner || '';
    this.risk_type = payload.risk_type || '';
    this.risk_evidence = payload.risk_evidence || '';
    this.risk_source = payload.risk_source || '';
    this.risk_description = payload.risk_description || '';
    this.risk_found_at = payload.risk_found_at || '';
    this.strategy_id = payload.strategy_id || '';
    this.strategy_name = payload.strategy_name || '';
    this.raw_event_id = payload.raw_event_id || '';
    this.trigger_type = payload.trigger_type;
    this.started_at = payload.started_at;
    this.ended_at = payload.ended_at || '';
    this.duration = payload.duration;
    this.status = payload.status;
    this.error = payload.error || '';
    this.executor = payload.executor;
    this.scene_id = payload.scene_id || '';
    this.params = payload.params || [];
    this.nodes = payload.nodes || [];
    this.attempts = payload.attempts || [];
  }
}
