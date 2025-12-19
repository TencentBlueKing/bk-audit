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

export default class resultData {
  original_sql: string;
  name: string;
  json_path: string;
  isChecked: boolean;
  isChild: boolean;
  children: Array<Record<string, any>>;
  list: Array<Record<string, any>>;
  type: string;
  config: null | Record<string, any>;
  listName: string;
  listDescription: string;
  constructor(payload = {} as resultData) {
    this.original_sql = payload.original_sql;
    this.name = payload.name;
    this.json_path = payload.json_path;
    this.isChecked = payload.isChecked;
    this.isChild = payload.isChild;
    this.children = payload.children;
    this.list = payload.list;
    this.type = payload.type;
    this.config = payload.config;
    this.listName = payload.listName;
    this.listDescription = payload.listDescription;
  }
}
