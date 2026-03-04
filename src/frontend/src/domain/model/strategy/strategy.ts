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

import DatabaseTableFieldModel from '@model/strategy/database-table-field';

import StrategyFieldEvent from '../strategy/strategy-field-event';

export default class Strategy {
  strategy_id: number;
  strategy_name: string;
  tags: string[];
  created_at: string;
  created_by: string;
  updated_at: string;
  updated_by: string;
  is_deleted: boolean;
  namespace: string;
  control_id: string;// 控件id
  control_version: number;// 版本
  report_status: string;
  configs: {
    config_type?: string;
    data_source?: {
      source_type: string;
      result_table_id?: string;
      rt_id: string;
      link_table: {
        uid: string,
        version: number,
      },
      system_ids: Array<string>,
      filter_config: Array<{
        connector: string;
        key: string;
        method: string;
        value: string[];
      }>;
      fields: {
        [key: string]: Array<{
          field_name: string,
          source_field: Array<{
            action_id: string;
            source_field: string;
            mapping_type: string
          }>
        }> | Array<{
          field_name: string;
          source_field: string;
        }>
      }
    };
    select: Array<DatabaseTableFieldModel>,
    where: {
      connector: 'and' | 'or' ;
      conditions: Array<{
        connector: 'and' | 'or';
        index: number;
        conditions: Array<{
          condition: {
            field: DatabaseTableFieldModel | '';
            filter: string;
            filters: string[];
            operator: '',
          }
        }>
      }>;
    },
    schedule_config: {
      count_freq: string,
      schedule_period: string,
    },
    [key: string]: any
  };
  status: string;
  status_msg: string;
  permission: Record<string, boolean>;
  notice_groups: Array<number>;
  description: string;
  risk_level: string;
  risk_hazard: string;
  risk_guidance: string;
  risk_title: string;
  risk_count: number;
  strategy_type: string;
  event_data_field_configs: StrategyFieldEvent['event_data_field_configs'];
  event_basic_field_configs: StrategyFieldEvent['event_basic_field_configs'];
  event_evidence_field_configs: StrategyFieldEvent['event_evidence_field_configs'];
  risk_meta_field_config: StrategyFieldEvent['risk_meta_field_config'];
  processor_groups: Array<number>;
  link_table_uid: string;
  link_table_version: number;
  report_enabled: boolean;
  report_config: any;
  report_auto_render: boolean;
  constructor(payload = {} as Strategy) {
    this.strategy_id = payload.strategy_id;
    this.strategy_name = payload.strategy_name;
    this.tags = payload.tags;
    this.created_at = payload.created_at;
    this.created_by = payload.created_by;
    this.updated_at = payload.updated_at;
    this.updated_by = payload.updated_by;
    this.is_deleted = payload.is_deleted;
    this.namespace = payload.namespace;
    this.control_id = payload.control_id;
    this.control_version = payload.control_version;
    this.configs = payload.configs;
    this.status = payload.status;
    this.status_msg = payload.status_msg;
    this.permission = payload.permission;
    this.notice_groups = payload.notice_groups;
    this.description = payload.description;
    this.risk_level = payload.risk_level;
    this.risk_hazard = payload.risk_hazard;
    this.risk_guidance = payload.risk_guidance;
    this.risk_title = payload.risk_title;
    this.risk_count = payload.risk_count; // 风险数量
    this.strategy_type = payload.strategy_type;
    this.event_data_field_configs = payload.event_data_field_configs;
    this.event_basic_field_configs = payload.event_basic_field_configs;
    this.event_evidence_field_configs = payload.event_evidence_field_configs;
    this.risk_meta_field_config = payload.risk_meta_field_config;
    this.processor_groups = payload.processor_groups;
    this.link_table_uid = payload.link_table_uid;
    this.link_table_version = payload.link_table_version;
    this.report_enabled = payload.report_enabled;
    this.report_config = payload.report_config;
    this.report_auto_render = payload.report_auto_render;
    this.report_status = payload.report_status;
  }
  get isFailed() {
    const failedStatusMap: Record<string, string> = {
      failed: 'failed',
      start_failed: 'start_failed',
      update_failed: 'update_failed',
      stop_failed: 'stop_failed',
      delete_failed: 'delete_failed',
    };
    return failedStatusMap[this.status];
  }
  get isPending() {
    const pendingStatusMap: Record<string, string> = {
      pending: 'pending',
      starting: 'starting',
      updating: 'updating',
      stop_failed: 'stop_failed',
      stopping: 'stopping',
    };
    return pendingStatusMap[this.status];
  }

  get statusTag() {
    const statusTagMap: Record<string, string> = {
      disabled: 'unknown',
      running: 'normal',
      // 处理中
      pending: 'warning',
      starting: 'warning',
      updating: 'warning',
      stopping: 'warning',
      // 失败
      failed: 'abnormal',
      start_failed: 'abnormal',
      update_failed: 'abnormal',
      stop_failed: 'abnormal',
      delete_failed: 'abnormal',
    };
    return statusTagMap[this.status];
  }
}
