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
interface IIPdata {
  ip: string;
  bk_cloud_id: number
}
export default class Topo {
  bk_biz_id: string;
  bk_inst_id: number;
  bk_inst_name: string;
  bk_obj_id: string;
  bk_obj_name: string;
  default: number;
  children: Array<Topo>;
  id: string;
  name: string;
  // 根节点是主机时会有下面的字段
  ip_list: Array<IIPdata>;

  constructor(payload = {} as Topo | Topo & { bk_obj_id: 'module', children: Array<IIPdata> }) {
    this.bk_biz_id = payload.bk_biz_id;
    this.bk_inst_id = payload.bk_inst_id;
    this.bk_inst_name = payload.bk_inst_name;
    this.bk_obj_id = payload.bk_obj_id;
    this.bk_obj_name = payload.bk_obj_name;
    this.children = payload.children || [];
    this.default = payload.default;
    this.id = payload.id;
    this.name = payload.name;

    this.ip_list = [];
    if (payload.bk_obj_id === 'module') {
      this.children = [];
      this.ip_list = this.initIPList(payload.children as Array<IIPdata>);
    }
    this.children = this.initChildren(this.children);
  }

  initChildren(children: Array<Topo>) {
    return children.map(child => new Topo(child));
  }
  initIPList(children = [] as Array<IIPdata>) {
    if (this.bk_obj_id === 'module') {
      return children.map(data => ({
        ip: data.ip,
        bk_cloud_id: data.bk_cloud_id,
      }));
    }
    return [];
  }
}
