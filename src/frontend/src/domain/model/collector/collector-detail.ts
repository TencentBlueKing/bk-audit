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
import _ from 'lodash';

import i18n from '@/language/index.js';

const { t } = i18n.global;

export default class CollectorDetail {
  allocation_min_days: number;
  bcs_cluster_id: string;
  bk_app_code: string;
  bk_biz_id: number;
  bk_data_id: number;
  bk_data_name: string;
  bkbase_table_id: string;
  bkdata_biz_id: number;
  bkdata_data_id: string;
  bkdata_data_id_sync_times: number;
  can_use_independent_es_cluster: boolean;
  category_id: string;
  category_name: string;
  collector_config_id: number;
  collector_config_name: string;
  collector_config_name_en: string;
  collector_config_overlay: string;
  collector_output_format: string;
  collector_package_count: number;
  collector_plugin_id: number;
  collector_scenario_id: string;
  collector_scenario_name: string;
  configs: Array<Record<string, any>>;
  created_at: string;
  created_by: string;
  custom_name: string;
  custom_type: string;
  data_encoding: string;
  data_link_id: number;
  deleted_at: string;
  deleted_by: string;
  description: string;
  environment: string;
  etl_config: string;
  etl_params:{
    es_unique_field_list: Array<string>;
    etl_flat: boolean;
    retain_original_text: boolean;
    separator_fields_remove: string;
    separator_node_action: string;
    separator_node_name: string;
    separator_node_source: string;
    regexp: string;
    regexp_keys?: Array<string>;
    delimiter: string;
  };
  etl_processor: string;
  fields: Array<{
    alias_name: string;
    default_value: string;
    description: string;
    field_name: string;
    field_type: string;
    is_analyzed: boolean;
    is_built_in: boolean;
    is_config_by_user: boolean;
    is_delete: boolean;
    is_dimension: boolean;
    is_time: boolean;
    option:{
      es_type: string;
    };
    tag: string;
    type: string;
    unit: string
  }>;
  iframe_ticket_url: string;
  index_set_id: string;
  index_split_rule: string;
  is_active: boolean;
  is_deleted: boolean;
  is_display: boolean;
  itsm_ticket_sn: string;
  itsm_ticket_status: string;
  itsm_ticket_status_display: string;
  params:{
    paths: Array<string>;
    conditions: {
      match_content: string;
      match_type: string;
      separator: string;
      separator_filters: Array<
      {
        op: string,
        logic_op: string,
        fieldindex: string,
        word: string,
      }>;
      type:string
    };
  };
  processing_id: string;
  retention: number;
  storage_cluster_id: number;
  storage_cluster_name: string;
  storage_replies: number;
  storage_shards_nums: number;
  storage_shards_size: number;
  subscription_id: number;
  system_id: string;
  table_id: string;
  table_id_prefix: string;
  target: Array<{
    [key: string]: any;
  }>;
  target_node_type: string;
  target_nodes:  Array<{
    [key: string]: any;
  }>;
  target_object_type:string;
  target_subscription_diff: {
    [key: string]: any;
  };
  task_id_list: [];
  ticket_url: string;
  updated_at: string;
  updated_by: string;
  yaml_config: string;
  yaml_config_enabled: boolean;
  record_log_type: string;
  select_sdk_type: string;
  constructor(payload = {} as CollectorDetail) {
    this.allocation_min_days = payload.allocation_min_days;
    this.bcs_cluster_id = payload.bcs_cluster_id;
    this.bk_app_code = payload.bk_app_code;
    this.bk_biz_id = payload.bk_biz_id;
    this.bk_data_id = payload.bk_data_id;
    this.bk_data_name = payload.bk_data_name;
    this.bkbase_table_id = payload.bkbase_table_id;
    this.bkdata_biz_id = payload.bkdata_biz_id;
    this.bkdata_data_id = payload.bkdata_data_id;
    this.bkdata_data_id_sync_times = payload.bkdata_data_id_sync_times;
    this.can_use_independent_es_cluster = payload.can_use_independent_es_cluster;
    this.category_id = payload.category_id;
    this.category_name = payload.category_name;
    this.collector_config_id = payload.collector_config_id;
    this.collector_config_name = payload.collector_config_name;
    this.collector_config_name_en = payload.collector_config_name_en;
    this.collector_config_overlay = payload.collector_config_overlay;
    this.collector_output_format = payload.collector_output_format;
    this.collector_package_count = payload.collector_package_count;
    this.collector_plugin_id = payload.collector_plugin_id;
    this.collector_scenario_id = payload.collector_scenario_id;
    this.collector_scenario_name = payload.collector_scenario_name;
    this.configs = payload.configs;
    this.created_at = payload.created_at;
    this.created_by = payload.created_by;
    this.custom_name = payload.custom_name;
    this.custom_type = payload.custom_type;
    this.data_encoding = payload.data_encoding;
    this.data_link_id = payload.data_link_id;
    this.deleted_at = payload.deleted_at;
    this.deleted_by = payload.deleted_by;
    this.description = payload.description;
    this.etl_config = payload.etl_config;
    this.etl_params = payload.etl_params;
    this.etl_processor = payload.etl_processor;
    this.fields = payload.fields;
    this.iframe_ticket_url = payload.iframe_ticket_url;
    this.index_set_id = payload.index_set_id;
    this.index_split_rule = payload.index_split_rule;
    this.is_active = payload.is_active;
    this.is_deleted = payload.is_deleted;
    this.is_display = payload.is_display;
    this.itsm_ticket_sn = payload.itsm_ticket_sn;
    this.itsm_ticket_status = payload.itsm_ticket_status;
    this.itsm_ticket_status_display = payload.itsm_ticket_status_display;
    this.params = payload.params;
    this.processing_id = payload.processing_id;
    this.retention = payload.retention;
    this.storage_cluster_id = payload.storage_cluster_id;
    this.storage_cluster_name = payload.storage_cluster_name;
    this.storage_replies = payload.storage_replies;
    this.storage_shards_nums  = payload.storage_shards_nums;
    this.storage_shards_size = payload.storage_shards_size;
    this.subscription_id = payload.subscription_id;
    this.system_id = payload.system_id;
    this.table_id = payload.table_id;
    this.table_id_prefix = payload.table_id_prefix;
    this.target = payload.target;
    this.target_node_type = payload.target_node_type;
    this.target_nodes = payload.target_nodes;
    this.target_object_type = payload.target_object_type;
    this.target_subscription_diff = payload.target_subscription_diff;
    this.task_id_list = payload.task_id_list || [];
    this.ticket_url = payload.ticket_url;
    this.updated_at = payload.updated_at;
    this.updated_by = payload.updated_by;
    this.yaml_config = payload.yaml_config;
    this.yaml_config_enabled = payload.yaml_config_enabled;
    this.environment = payload.environment;
    this.record_log_type = payload.record_log_type;
    this.select_sdk_type = payload.select_sdk_type;

    this.params = this.initParams(payload.params, payload.configs);
    this.data_encoding = this.initEncoding(payload.configs, payload.data_encoding);
  }
  initParams(params: CollectorDetail['params'], configs: CollectorDetail['configs']) {
    if (!_.isObject(params)) {
      return {
        conditions: {
          match_content: '',
          match_type: '',
          separator: '',
          separator_filters: [
            {
              logic_op: 'AND',
              fieldindex: '',
              word: '',
              op: '',
            },
          ],
          type: '',
        },
        paths: [],
      };
    }
    if (_.isArray(configs)) {
      const result = [] as Array<string>;
      configs.forEach((item) => {
        item.params.paths.forEach((path: string) => {
          result.push(path);
        });
      });
      // eslint-disable-next-line no-param-reassign
      params.paths = result;
      // eslint-disable-next-line no-param-reassign
      params.conditions = configs[0].params.conditions;
      return params;
    }
    return params;
  }

  initEncoding(configs: CollectorDetail['configs'], encoding: CollectorDetail['data_encoding']) {
    if (_.isArray(configs)) {
      const result = [] as Array<string>;
      configs.forEach((item) => {
        result.push(item.data_encoding);
      });
      return result.join(';') || '';
    }
    return encoding;
  }

  get statusText() {
    const statusText: Record<string, string> =  {
      running: t('执行中'),
      failed: t('失败'),
      success: t('成功'),
      unknown: t('未知'),
    };
    return statusText;
  }

  get Icon() {
    const Icon:  Record<string, string> =  {
      running: 'loading',
      failed: 'abnormal',
      success: 'normal',
      unknown: 'unknown',
    };
    return Icon;
  }
}
