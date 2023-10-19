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
export default class RetrieveUser {
  display_name: string;
  id: number;
  username: string;
  status: string;
  staff_status: string;
  departments: Array<{
    order:number;
    id: number;
    full_name: string;
    name: string;
  }>;
  leader: Array<{
    username: string;
    display_name:string;
    id:number;
  }>;
  extras: {
    virtualapi: number;
    postname: string;
    gender: string;
  };

  constructor(payload = {} as RetrieveUser) {
    this.display_name = payload.display_name;
    this.id = payload.id;
    this.username = payload.username;
    this.status = payload.status;
    this.staff_status = payload.staff_status;
    this.departments = payload.departments || [];
    this.leader = payload.leader || [];
    this.extras = payload.extras || [];
  }
  get departmentText() {
    const  { departments } = this;
    if (departments && departments.length) {
      return departments[0].full_name;
    }
  }

  get gender() {
    if (this.extras) {
      return this.extras.gender;
    }
  }

  get postname() {
    if (this.extras) {
      return this.extras.postname;
    }
  }
  get leaders() {
    const { leader } = this;
    if (leader && leader.length) {
      return `${leader[0].username}(${leader[0].display_name})`;
    }
  }

  get name() {
    return `${this.username}(${this.display_name})`;
  }
}
