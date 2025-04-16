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
export default class DatabaseTableField {
  table: string; // RT ID
  raw_name: string; // bkbase 字段名
  display_name: string; // 展示名称 -- 用于 AS 别名，查询中唯一
  field_type: string; // 字段类型 -- 来自 bkbase
  aggregate: any; // 聚合函数 -- 聚合算法
  remark: string; // 备注
  spec_field_type: string;

  constructor(payload = {} as DatabaseTableField) {
    this.table = payload.table || '';
    this.raw_name = payload.raw_name || '';
    this.display_name = payload.display_name || '';
    this.field_type = payload.field_type || '';
    this.aggregate = payload.aggregate || null;
    this.remark = payload.remark || '';
    this.spec_field_type = payload.spec_field_type || '';
  }
}
