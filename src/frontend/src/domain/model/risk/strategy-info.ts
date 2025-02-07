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

import StrategyFieldEvent from '../strategy/strategy-field-event';

export default class StrategyInfo {
  risk_title: string;
  risk_level: string;
  risk_guidance: string;
  risk_hazard: string;
  event_data_field_configs: StrategyFieldEvent['event_data_field_configs'];
  event_basic_field_configs: StrategyFieldEvent['event_basic_field_configs'];

  constructor(payload = {} as StrategyInfo) {
    this.risk_title = payload.risk_title;
    this.risk_level = payload.risk_level;
    this.risk_guidance = payload.risk_guidance;
    this.risk_hazard = payload.risk_hazard;
    this.event_data_field_configs = payload.event_data_field_configs;
    this.event_basic_field_configs = payload.event_basic_field_configs;
  }
}
