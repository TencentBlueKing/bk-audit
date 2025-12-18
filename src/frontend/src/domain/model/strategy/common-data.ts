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

type ItemType = {
  label: string,
  value: string
  config?: any;
}

export default class CommonData {
  offset_unit: Array<ItemType>;
  table_type: Array<ItemType>;
  mapping_type: Array<ItemType>;
  strategy_operator: Array<ItemType>;
  filter_operator: Array<ItemType>;
  algorithm_operator: Array<ItemType>;
  strategy_status: Array<ItemType>;
  risk_level: Array<ItemType>;
  strategy_type: Array<ItemType>;
  rule_audit_config_type: Array<ItemType>;
  aggregate: Array<ItemType>;
  link_table_join_type: Array<ItemType>;
  link_table_table_type: Array<ItemType>;
  rule_audit_aggregate_type: Array<ItemType>;
  rule_audit_condition_operator: Array<ItemType>;

  constructor(payload = {} as CommonData) {
    this.offset_unit = payload.offset_unit || [];
    this.table_type = payload.table_type || [];
    this.mapping_type = payload.mapping_type || [];
    this.strategy_operator = payload.strategy_operator || [];
    this.filter_operator = payload.filter_operator || [];
    this.algorithm_operator = payload.algorithm_operator || [];
    this.strategy_status = payload.strategy_status || [];
    this.risk_level = payload.risk_level || [];
    this.strategy_type = payload.strategy_type || [];
    this.rule_audit_config_type = payload.rule_audit_config_type || [];
    this.aggregate = payload.aggregate || [];
    this.link_table_join_type = payload.link_table_join_type || [];
    this.link_table_table_type = payload.link_table_table_type || [];
    this.rule_audit_aggregate_type = payload.rule_audit_aggregate_type || [];
    this.rule_audit_condition_operator = payload.rule_audit_condition_operator || [];
  }
}

