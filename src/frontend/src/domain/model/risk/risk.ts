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

export default class Event {
  risk_id: number;
  event_content: string;
  raw_event_id: string;
  strategy_id: number;
  event_evidence: string;
  event_type: string[];
  event_data: Record<string, any>;
  event_time: string;
  last_operate_time: string;
  event_source: string;
  operator: string[];
  status: string;
  rule_id: string;
  rule_version: number;
  origin_operator: string[];
  current_operator: string[];
  updated_at: string;
  updated_by: string;
  unsynced_events?: Array<Record<string, any>>;
  event_end_time: string;
  ticket_history: Array<{
    action: string,
    id: string,
    current_operator: string[],
    operator: string,
    process_result: {
      rule_id: string,
      rule_version: string,
      status?: {
        sn: string,
        current_status: string, // 单据状态
        update_at: string,
        ticket_url: string,
        updated_by: string,
        approve_result: boolean,

        state: string, // 任务状态
        name: string, // 任务名称
        finish_time: string,
        start_time: string,
      },
      ticket: {
        sn: string,
        id: number, // 单据名称
        ticket_url: string, // 单据链接
      },
      task: {
        task_id: number,
        task_url: string,
      }
    },
    time: string,
    timestamp: number,


    new_operators: string[],
    description: string, // 误报说明

    custom_action: string, // CustomProcess
    pa_id: string, // 套餐id
    pa_params: Record<string, any>// 套餐参数

    [key: string]: any,
  }>;
  notice_users: string[];
  tags: string[];
  risk_label: string;
  report_enabled: boolean;
  report_auto_render: boolean;
  report_generating: boolean;
  has_report: boolean;
  report: {
    content: string;
    status: string;
    auto_generate: boolean;
    create_at: string;
    update_at: string;
    updated_by: string;
    updated_at: string;
  } | null;
  permission: Record<string, boolean>;
  experiences: number;// 风险总结
  title: string;
  notice_groups:  number[];
  processor_groups:  number[];
  event_basic_field_configs: Array<Record<string, any>>;

  constructor(payload = {} as Event) {
    this.risk_id = payload.risk_id;
    this.updated_at = payload.updated_at;
    this.updated_by = payload.updated_by;
    this.event_content = payload.event_content;
    this.raw_event_id = payload.raw_event_id;
    this.strategy_id = payload.strategy_id;
    this.event_evidence = payload.event_evidence;
    this.event_data = payload.event_data;
    this.event_time = payload.event_time;
    this.last_operate_time = payload.last_operate_time;
    this.event_source = payload.event_source;
    this.operator = payload.operator;
    this.status = payload.status;
    this.event_type = payload.event_type;
    this.report_enabled = payload.report_enabled;
    this.report_auto_render = payload.report_auto_render;
    this.has_report = payload.has_report;
    this.report = payload.report;
    this.rule_id = payload.rule_id;
    this.rule_version = payload.rule_version;
    this.origin_operator = payload.origin_operator;
    this.current_operator = payload.current_operator;
    this.event_end_time = payload.event_end_time;
    this.ticket_history = payload.ticket_history;
    this.notice_users = payload.notice_users;
    this.tags = payload.tags;
    this.risk_label = payload.risk_label;
    this.permission = payload.permission;
    this.experiences = payload.experiences;
    this.title = payload.title;
    this.unsynced_events = payload.unsynced_events;
    this.notice_groups = payload.notice_groups;
    this.processor_groups = payload.processor_groups;
    this.event_basic_field_configs = payload.event_basic_field_configs;
    this.report_generating = payload.report_generating;
  }
}
