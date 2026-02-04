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

export default class Config {
  aegis_id: string;
  app_code: string;
  feature_toggle: Record<string, any>;
  login_url: string;
  remote_static_url: string;
  site_url: string;
  static_url: string;
  static_version: string;
  super_manager: boolean;
  system_manager: boolean;
  username: string;
  title: string;
  footer: Array<{
    type: string;
    type_description: string;
    text: string;
    url: string;
  }>;
  language: {
    domain: string;
    name: string;
    available: Array<{
      id: string,
      name: string
    }>
  };
  copyright: string;
  version: string;
  site_title: string;
  help_info:{
    schema: string;
    query_string: string;
    ai_practices: {
      ai_summary: string;
    };
  };
  bk_biz_id: number;
  shared_res_url: string;
  system_diagnosis: {
    iam_web_url: string;
    ieg_std_op_doc_url: string;
  };
  third_party_system: {
    bkbase_web_url: string;
    bkvision_web_url: string;
  };
  third_doc_url: {
    search_rule_iwiki_url: string;
  };
  metric: {
    metric_report_trace_url: string;
  };
  tool: {
    vision_share_permission_url: string;
  };

  constructor(payload = {} as Config) {
    this.aegis_id = payload.aegis_id;
    this.app_code = payload.app_code;
    this.feature_toggle = payload.feature_toggle;
    this.login_url = payload.login_url;
    this.remote_static_url = payload.remote_static_url;
    this.site_url = payload.site_url;
    this.static_url = payload.static_url;
    this.static_version = payload.static_version;
    this.super_manager = payload.super_manager;
    this.system_manager = payload.system_manager;
    this.username = payload.username;
    this.footer = payload.footer || [];
    this.title = payload.title;
    this.copyright = payload.copyright;
    this.version = payload.version;
    this.site_title = payload.site_title;
    this.help_info = payload.help_info;
    this.language = payload.language;
    this.bk_biz_id = payload.bk_biz_id;
    this.shared_res_url = payload.shared_res_url;
    this.system_diagnosis = payload.system_diagnosis;
    this.third_party_system = payload.third_party_system;
    this.third_doc_url = payload.third_doc_url;
    this.metric = payload.metric;
    this.help_info = this.initHelpInfo(payload.help_info);
    this.tool = payload.tool;
  }

  initHelpInfo(params: Config['help_info']) {
    if (!_.isObject(params)) {
      return {
        schema: '',
        query_string: '',
        ai_practices: {
          ai_summary: '',
        },
      };
    }
    return params;
  }
}
