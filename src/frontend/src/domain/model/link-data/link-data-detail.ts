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
export default class AiopsDetail {
  table_name: number|string;
  tag: string;
  status: string;
  created_by: string;
  created_at: string;
  updated_by: string;
  updated_at: string;
  has_refresh: boolean;
  links: Array<{
		left_dataset_uid: string,
    left_dataset_name: string,
		right_dataset_uid: string,
		right_dataset_name: string,
		join_type: string,
		link_fields: Array<{
			left_field: string,
			right_field: string
		}>
	}>;

  // {
  //   left_dataset_uid: 'aYuCYsCZbXrYmEcx4fgpKW',
  //   left_dataset_name: 'a操作日志表',
  //   right_dataset_uid: '3uewK9ytd2nqVS6qMfgsru',
  //   right_dataset_name: 'a资产表',
  //   join_type: 'left_join',
  //   link_fields: [{
  //     left_field: '35NShkXqzsUpScA3qomU4a',
  //     right_field: '3kaFQmGGaY4DVYeUfqKDiV',
  //   }],
  // },
  constructor(payload = {} as AiopsDetail) {
    this.table_name = payload.table_name;
    this.tag = payload.tag;
    this.status = payload.status;
    this.created_by = payload.created_by;
    this.created_at = payload.created_at;
    this.updated_by = payload.updated_by;
    this.updated_at = payload.updated_at;
    this.has_refresh = payload.has_refresh;
    this.links = payload.links;
  }
}
