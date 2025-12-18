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
const STATUS_ABNORMAL = 'ABNORMAL'; // 未恢复
const STATUS_CLOSED = 'CLOSED'; // 已关闭
const STATUS_RECOVERED = 'RECOVERED'; // 已恢复
const STATUS_UNKNOWN = 'UNKNOWN'; // 未知

export default class Event {
  static statusMap: Record<string, string> = {
    [STATUS_ABNORMAL]: 'abnormal',
    [STATUS_CLOSED]: 'close',
    [STATUS_RECOVERED]: 'recovered',
    [STATUS_UNKNOWN]: 'unknown',
  };

  id: string;
  alert_name: string;
  status: string;
  labels: Array<string>;
  description: string;
  severity: number;
  metric: Array<string>;
  bk_biz_id: number;
  ip: string;
  bk_cloud_id: string;
  bk_service_instance_id: string;
  bk_topo_node: string;
  assignee: Array<string>;
  appointee: string;
  is_ack: string;
  is_shielded: boolean;
  shield_left_time: string;
  shield_id: string;
  is_handled: boolean;
  strategy_id: number;
  create_time: string;
  update_time: string;
  begin_time: string;
  end_time: string;
  latest_time: string;
  first_anomaly_time: string;
  target_type: string;
  target: string;
  category: string;
  tags: Array<
    {
      key: string;
      value: string;
    }
  >;
  category_display: string;
  duration: string;
  ack_duration: string;
  data_type: string;
  converge_id: string;
  event_id: string;
  plugin_id: string;
  stage_display: string;
  dimensions: Array<{
    display_value: string;
    display_key: string;
    value: string;
    key: string;
  }>;
  seq_id: number;
  dedupe_md5: string;
  dedupe_keys: [string];
  dimension_message: string;
  metric_display: Array<
    {
      id: string;
      name: string
    }
  >;
  target_key: string;
  ack_operator: string;
  shield_operator: Array<string>;
  strategy_name: string;
  bk_biz_name: string;
  status_name: string;


  constructor(payload = {} as Event) {
    this.id = payload.id;
    this.alert_name = payload.alert_name;
    this.status = payload.status;
    this.labels = payload.labels || [];
    this.description = payload.description;
    this.severity = payload.severity;
    this.metric = payload.metric;
    this.bk_biz_id = payload.bk_biz_id;
    this.ip = payload.ip;
    this.bk_cloud_id = payload.bk_cloud_id;
    this.bk_service_instance_id = payload.bk_service_instance_id;
    this.bk_topo_node = payload.bk_topo_node;
    this.assignee = payload.assignee;
    this.appointee = payload.appointee;
    this.is_ack = payload.is_ack;
    this.is_shielded = payload.is_shielded;
    this.shield_left_time = payload.shield_left_time;
    this.shield_id = payload.shield_id;
    this.is_handled = payload.is_handled;
    this.strategy_id = payload.strategy_id;
    this.create_time = payload.create_time;
    this.update_time = payload.update_time;
    this.begin_time = payload.begin_time;
    this.end_time = payload.end_time;
    this.latest_time = payload.latest_time;
    this.first_anomaly_time = payload.first_anomaly_time;
    this.target_type = payload.target_type;
    this.target = payload.target;
    this.category = payload.category;
    this.tags = payload.tags;
    this.category_display = payload.category_display;
    this.duration = payload.duration;
    this.ack_duration = payload.ack_duration;
    this.data_type = payload.data_type;
    this.converge_id = payload.converge_id;
    this.event_id = payload.event_id;
    this.plugin_id = payload.plugin_id;
    this.stage_display = payload.stage_display;
    this.dimensions = payload.dimensions;
    this.seq_id = payload.seq_id;
    this.dedupe_md5 = payload.dedupe_md5;
    this.dedupe_keys = payload.dedupe_keys;
    this.dimension_message = payload.dimension_message;
    this.metric_display = payload.metric_display || [];
    this.target_key = payload.target_key;
    this.ack_operator = payload.ack_operator;
    this.shield_operator = payload.shield_operator;
    this.strategy_name = payload.strategy_name;
    this.bk_biz_name = payload.bk_biz_name;
    this.status_name = payload.status_name;
  }

  get statusClass() {
    return Event.statusMap[this.status];
  }

  get assigneeLabels() {
    return this.assignee ? this.assignee.join(',') : '--';
  }

  get chartTitle() {
    return this.metric_display[0];
  }
}

