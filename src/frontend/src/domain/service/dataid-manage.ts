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
import type CollectorEtlField from '@model/collector/collector-etl-field';

import DataIdManageSource from '../source/dataid-manage';

export default {
  /**
   * 创建或更新DataID清洗入库
   * @param params
  */
  createDataIdEtl(params: {
    bk_data_id: number,
    fields: CollectorEtlField,
    etl_params: {
      delimiter: string,
      retain_original_text: boolean
    },
  }) {
    return DataIdManageSource.createDataIdEtl(params)
      .then(({ data }) => data);
  },
  /**
   * DataID清洗预览
   * @param params
  */
  fetchDataIdEtlPreview(params: {
    data: string;
  }) {
    return DataIdManageSource.dataIdEtlPreview(params)
      .then(({ data }) => data);
  },
  /**
   * dataid清洗字段历史
   * @param params
  */
  fetchFieldHistory(params: {
    id: number
  }) {
    return DataIdManageSource.fieldHistory(params)
      .then(({ data }) => data);
  },
  /**
  * 获取系统下的dataid列表
  * @param params
 */
  fetchSystemDataIdList(params: {
    system_id: string
  }) {
    return DataIdManageSource.getSystemDataIdList(params)
      .then(({ data }) => data);
  },
  /**
   * 获取dataID列表
   */
  fetchDataIDList(params: {
    bk_biz_id: number
  }) {
    return DataIdManageSource.getAllDataIdList(params)
      .then(({ data }) => data);
  },
  /**
   * 获取dataid详情
   * @param params
   */
  fecthDetail(params: {
    bk_data_id: number,
  }) {
    return DataIdManageSource.getDetail(params)
      .then(({ data }) => data);
  },
  /**
   * 删除DataId接入
   * @param params
   */
  deleteDataId(params: {
    bk_data_id: number,
  }) {
    return DataIdManageSource.deleteDataId(params)
      .then(({ data }) => data);
  },
  /**
   * 接入dataid数据源
   * @param params
   */
  applyDataIdSource(params: {
    bk_data_id: number,
    system_id: string
  }) {
    return DataIdManageSource.applyDataIdSource(params)
      .then(({ data }) => data);
  },
  /**
   * 获取最近源数据
   * @param params
   */
  fetchTail(params: {
    bk_data_id: number
  }) {
    return DataIdManageSource.getTail(params)
      .then(({ data }) => data);
  },
};
