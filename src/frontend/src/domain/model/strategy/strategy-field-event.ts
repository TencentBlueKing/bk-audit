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
type EventItem = {
  field_name: string,
  description: string
  display_name: string;
  is_show: boolean;
  is_priority: boolean;
  duplicate_field: boolean;
  map_config?: {
    target_value: string | undefined,
    source_field: string | undefined,
  };
  enum_mappings?: {
    collection_id: string;
    mappings: Array<{
      key: string;
      name: string;
    }>
  }
  drill_config?: Array<{
    tool: {
      uid: string;
      version: number;
    };
    drill_name: string;
    config: Array<{
      source_field: string;
      target_value_type: string;
      target_value: string;
      target_field_type: string;
    }>
  }>;
  prefix: string;
  example?: string
}

export default class StrategyFieldEvent {
  event_basic_field_configs: Array<EventItem>;
  event_data_field_configs: Array<EventItem>;
  event_evidence_field_configs: Array<EventItem>;
  risk_meta_field_config: Array<EventItem>;

  constructor(payload = {} as StrategyFieldEvent) {
    this.event_basic_field_configs = StrategyFieldEvent.processingData(payload.event_basic_field_configs, '');
    this.event_data_field_configs = StrategyFieldEvent.processingData(payload.event_data_field_configs, 'event_data');
    this.event_evidence_field_configs = StrategyFieldEvent.processingData(payload.event_evidence_field_configs, 'event_evidence');
    this.risk_meta_field_config = StrategyFieldEvent.processingData(payload.risk_meta_field_config, 'event_evidence');
  }

  static processingData(data: Array<EventItem>, prefix = '') {
    return (data && data.map(item => ({
      field_name: item.field_name,
      display_name: item.display_name,
      is_show: item.is_show ?? true,
      is_priority: !prefix ? true : item.is_priority || false, // 如果不是基本信息，则默认不重点展示
      duplicate_field: item.duplicate_field || false,
      map_config: {
        target_value: item.map_config?.target_value,
        source_field: item.map_config?.source_field,
      },
      enum_mappings: {
        collection_id: item.enum_mappings?.collection_id || '',
        mappings: item.enum_mappings?.mappings || [],
      },
      drill_config: item.drill_config || [],
      description: item.description,
      example: item.example,
      prefix,
    }))) || [];
  }
}
