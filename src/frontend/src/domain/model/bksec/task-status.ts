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

export type BksecTaskState = 'RUNNING' | 'FINISHED' | 'FAILED' | string;

export const isTerminalTaskState = (state: string) => state === 'FINISHED' || state === 'FAILED';

export type TaskPollDecision = 'continue' | 'success' | 'failed' | 'stopped';

/** 代次变化表示抽屉已关或已发起新任务，旧轮询必须停止。 */
export const decideTaskPoll = (
  generation: number,
  currentGeneration: number,
  state: string,
): TaskPollDecision => {
  if (generation !== currentGeneration) return 'stopped';
  if (state === 'FINISHED') return 'success';
  if (state === 'FAILED') return 'failed';
  return 'continue';
};

export default class BksecTestTaskStatus {
  /** 接口是否明确返回了 state。空响应不能当成进行中。 */
  hasState: boolean;
  state: BksecTaskState;
  failureHint: string;
  constructor(payload: { state?: string; failure_hint?: string } = {}) {
    this.hasState = !!payload.state;
    this.state = payload.state || 'RUNNING';
    this.failureHint = payload.failure_hint || '';
  }
}
