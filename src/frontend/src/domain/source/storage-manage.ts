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
import type NodeAttrModel from '@model/storage/node-attr';
import type StorageModel from '@model/storage/storage';

import Request from '@utils/request';

import ModuleBase from './module-base';


class StorageManage extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1/databus';
  }
  // 存储集群列表
  getAll(params: { keyword?: string }, payload = {}) {
    return Request.get<Array<StorageModel>>(`${this.path}/storages/`, {
      params,
      payload,
    });
  }
  // 创建集群
  create(params: Record<string, any>) {
    return Request.post(`${this.path}/storages/`, {
      params,
    });
  }
  // 更新集群
  updateById(params: {id: string}) {
    const realParams = Object.assign({}, params) as {id?: string};
    delete realParams.id;
    return Request.put(`${this.path}/storages/${params.id}/`, {
      params: realParams,
    });
  }
  // 删除集群
  deleteById(params: {id: number}) {
    return Request.delete(`${this.path}/storages/${params.id}/`, {});
  }
  // 集群节点属性
  getNodeAttrs(params: Record<string, any>) {
    return Request.post<Array<NodeAttrModel>>(`${this.path}/storages/node_attrs/`, {
      params,
    });
  }
  activateById(params: {id: number}) {
    return Request.put<number>(`${this.path}/storages/${params.id}/activate/`, {});
  }
  // 连通性测试
  connectivityDetect(params: Record<string, any>) {
    return Request.post<boolean>(`${this.path}/storages/connectivity_detect/`, {
      params,
    });
  }
  // 批量连通性测试
  batchConnectivityDetect(params: {cluster_ids: string}) {
    return Request.get<Record<number, boolean>>(`${this.path}/storages/batch_connectivity_detect/`, {
      params,
    });
  }
}

export default new StorageManage();
