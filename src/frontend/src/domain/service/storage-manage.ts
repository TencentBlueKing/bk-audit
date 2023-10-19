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
import NodeAttrModel from '@model/storage/node-attr';
import StorageModel from '@model/storage/storage';

import StorageManageSources from '../source/storage-manage';

export default  {
  /**
   * @desc 集群列表
   * @param { String } keyword
   */
  fetchList(params: { keyword?: string }) {
    return StorageManageSources.getAll(params, {
      permission: 'page',
    })
      .then(({ data }) => {
        const results = data.map(item => new StorageModel(item));
        return results;
      });
  },
  /**
   * @desc 创建集群
   * @param { Object } params
   */
  create(params: Record<string, any>) {
    return StorageManageSources.create(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 更新集群
   * @param { Object } params
   */
  update(params: Record<string, any> & {id: string}) {
    return StorageManageSources.updateById(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 删除集群
   * @param { Number } id
   */
  remove(params: {id: number}) {
    return StorageManageSources.deleteById(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 设置默认集群
   * @param { Number } id
   */
  setActivate(params: {id: number}) {
    return StorageManageSources.activateById(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 连通性测试
   * @param { Object } params
   */
  connectivityDetect(params: Record<string, any>) {
    return StorageManageSources.connectivityDetect(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 批量连通性测试
   * @param { String } cluster_ids
   */
  batchConnectivityDetect(params = {} as {cluster_ids: string}) {
    return StorageManageSources.batchConnectivityDetect(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 集群节点属性
   * @param { Object } params
   */
  fetchNodeAttrList(params: Record<string, any>) {
    return StorageManageSources.getNodeAttrs(params)
      .then(({ data }) => data.map(item => new NodeAttrModel(item)));
  },
};
