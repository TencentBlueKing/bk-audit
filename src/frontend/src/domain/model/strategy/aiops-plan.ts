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
export default class AiopsPlan {
  plan_id: number;
  scene_id: number;
  plan_name:string;
  plan_alias: string;
  plan_description: string;
  version_id: number;
  version_no: string;
  latest_plan_version_id: number;
  plan_document: {
    content: string;
    imgList: Array<string>;
  };
  developer: Array<string>;
  input_fields: {
    [key: string]: Array<{
      data_field_name: string,
      input_field_name: string | any[],
      role: string[],
      [key: string]: any
    }>
  };
  variable_config: Array<any>;
  output_fields: [];

  // 检测 input field 是否隐藏显示
  // static checkHideInputField(inputField: ValueOf<AiopsPlan['input_fields']>[0]) {
  //   return !(
  //     inputField.roles.includes('system')
  //     || inputField.roles.includes('timestamp')
  //     || inputField.field_name === 'attr_group');
  // }
  static checkHideInputField(inputField: ValueOf<AiopsPlan['input_fields']>[0]) {
    if (inputField.field_container_type === 'group'
      || inputField.roles.includes('system')
      || inputField.roles.includes('timestamp')
      || ['strategy_id', 'origin_data'].includes(inputField.field_name)) {
      return false;
    }
    return true;
  }

  constructor(payload = {} as AiopsPlan) {
    this.plan_id = payload.plan_id;
    this.scene_id = payload.scene_id;
    this.plan_name = payload.plan_name;
    this.plan_alias = payload.plan_alias;
    this.plan_description = payload.plan_description;
    this.version_id = payload.version_id;
    this.version_no = payload.version_no;
    this.latest_plan_version_id = payload.latest_plan_version_id;
    this.plan_document = payload.plan_document || {};
    this.developer = payload.developer || [];
    this.input_fields = payload.input_fields || {};
    this.variable_config = payload.variable_config || [];
    this.output_fields = payload.output_fields || [];
  }
}
