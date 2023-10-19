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

import type CollectorModel from '@model/collector/collector';
import type CollectorEtlField from '@model/collector/collector-etl-field';

import Request from '@utils/request';

import ModuleBase from './module-base';

import type DataIdDetailModel from '@/domain/model/dataid/dataid-detail';
import type DataIdTopicLogModel from '@/domain/model/dataid/dataid-tail';

class DataIDManage extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1/databus';
  }
  // 创建或更新DataID清洗入库
  createDataIdEtl(params: {
    bk_data_id: number,
    fields: CollectorEtlField,
    etl_params: {
      delimiter: string,
      retain_original_text: boolean
    },
  }) {
    return Request.post(`${this.path}/data_id_etl/`, {
      params,
    });
  }
  // DataID清洗预览
  dataIdEtlPreview(params: {
    data: string;
  }) {
    return Request.post(`${this.path}/data_id_etl/preview/`, {
      params,
    });
  }
  // dataid清洗字段历史
  fieldHistory(params: {
    id: number
  }) {
    return Request.get<Record<string, string>>(`${this.path}/data_id_etl/${params.id}/field_history/`);
  }
  // 获取系统下的dataid列表
  getSystemDataIdList(params: {
    system_id: string
  }) {
    return Request.get<Array<CollectorModel>>(`${this.path}/data_ids/`, {
      params,
    });
  }
  // dataid列表
  getAllDataIdList(params: {
    bk_biz_id: number
  }) {
    return Request.get<Array<{
      bk_biz_id: number,
      bk_data_id: number,
      custom_type: string,
      raw_data_alias: string,
      raw_data_name: string,
      is_applied:boolean
    }>>(`${this.path}/data_ids/mine/`, {
      params,
    });
  }
  // 获取dataid详情
  getDetail(params: {
    bk_data_id: number,
  }) {
    return Request.get<DataIdDetailModel>(`${this.path}/data_ids/${params.bk_data_id}/`, {
      params,
    });
  }
  // 删除DataId接入
  deleteDataId(params: {
    bk_data_id: number,
  }) {
    return Request.delete(`${this.path}/data_ids/${params.bk_data_id}/`, {
      params,
    });
  }
  // 接入dataid数据源
  applyDataIdSource(params: {
    bk_data_id: number,
    system_id: string
  }) {
    return Request.post(`${this.path}/data_ids/apply_source/`, {
      params,
    });
  }
  // 获取最近源数据
  getTail(params: {
    bk_data_id: number
  }) {
    return Request.get<Array<DataIdTopicLogModel>>(`${this.path}/data_ids/${params.bk_data_id}/tail/`, {
      params,
    });
  }
}
export default new DataIDManage();
