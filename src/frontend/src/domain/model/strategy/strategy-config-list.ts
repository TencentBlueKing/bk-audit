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
export default class StrategyConfigList {
  id: number;
  version: string;
  bk_biz_id: string;
  name: string;
  source: string;
  scenario: string;
  items: Array<
    {
      id: number,
      name: string,
      no_data_config: {
        level: number,
        continuous: number,
        is_enabled: boolean,
        agg_dimension: []
      },
      target: [[]],
      expression: string,
      functions: [],
      origin_sql: string,
      query_configs: Array<
        {
          data_source_label: string,
          data_type_label: string,
          alias: string,
          metric_id: string,
          id: number,
          functions: [],
          query_string: string,
          result_table_id:  string
          index_set_id: number|string,
          agg_interval: number|string,
          agg_dimension: string[],
          agg_condition: [
            {
              key: string,
              value: string[],
              method: string,
              condition: string
            }
          ],
          time_field: string,
          name: string
        }
      >,
      algorithms: Array<
        {
          id: number,
          type: string,
          level: number,
          config: Array<
            [
              {
                method: string,
                threshold: number
              }
            ]
          >,
          unit_prefix: string
        }
      >
    }
  >;
  detects: Array<{
    [key: string]: any
  }>;
  actions: [];
  permission:Record<string, boolean>;
  notice: {
    id: number,
    config_id: number,
    user_groups: number[],
    signal: string[],
    options: {
      end_time: string,
      start_time: string,
      converge_config: {[key: string]: any},
      exclude_notice_ways: {[key: string]: any},
      noise_reduce_config: {[key: string]: any}
    },
    relate_type: string,
    config: {[key: string]: any}
  };
  is_enabled: boolean;
  is_invalid: boolean;
  invalid_type: string;
  update_time: string;
  update_user: string;
  create_time: string;
  create_user: string;
  labels: string[];
  app: string;
  alert_count: number;
  shield_alert_count: number;
  shield_info: {
    'is_shielded': false,
    'shield_ids': []
  };
  add_allowed: boolean;
  data_source_type: string;
  strategy_type: string;


  constructor(payload = {} as StrategyConfigList) {
    this.id = payload.id;
    this.version = payload.version;
    this.bk_biz_id = payload.bk_biz_id;
    this.name = payload.name;
    this.source = payload.source;
    this.scenario = payload.scenario;
    this.items = payload.items;
    this.detects = payload.detects;
    this.actions = payload.actions;
    this.notice = payload.notice;
    this.permission = payload.permission;
    this.is_enabled = payload.is_enabled;
    this.is_invalid = payload.is_invalid;
    this.invalid_type = payload.invalid_type;
    this.update_time = payload.update_time;
    this.update_user = payload.update_user;
    this.create_time = payload.create_time;
    this.create_user = payload.create_user;
    this.labels = payload.labels;
    this.app = payload.app;
    this.alert_count = payload.alert_count;
    this.shield_alert_count = payload.shield_alert_count;
    this.shield_info = payload.shield_info;
    this.add_allowed = payload.add_allowed;
    this.data_source_type = payload.data_source_type;
    this.strategy_type = payload.strategy_type;
  }
}

