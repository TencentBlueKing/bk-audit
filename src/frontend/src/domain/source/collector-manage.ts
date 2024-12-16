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
import type BatchSubscriptionStatusModel from '@model/collector/batch-subscription-status';
import type BcsTaskStatusModel from '@model/collector/bcs-task-status';
import type CollectorModel from '@model/collector/collector';
import type CollectorCreateResultModel from '@model/collector/collector-create-result';
import type CollectorDetailModel from '@model/collector/collector-detail';
import type CollectorTailLogModel from '@model/collector/collector-tail-log';
import type EtlPreviewModel from '@model/collector/etl-preview';
import type JoinDataModel from '@model/collector/join-data';
import type SystemCollectorStatusModel from '@model/collector/system-collector-status';
import type CollectorTaskStatusModel from '@model/collector/task-status';

import Request, {
  type IRequestPayload,
} from '@utils/request';

import ModuleBase from './module-base';

class CollectorManage extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1/databus';
  }

  // 采集列表
  getAllCollectors(params: {system_id:string}) {
    return Request.get<Array<CollectorModel>>(`${this.path}/collectors/`, { params });
  }
  // 新建采集
  create(params: Record<any, string>) {
    return Request.post<CollectorCreateResultModel>(`${this.path}/collectors/`, {
      params,
    });
  }
  // 更新采集
  update(params: { collector_config_id: number }) {
    return Request.put<CollectorCreateResultModel>(`${this.path}/collectors/${params.collector_config_id}/`, {
      params,
    });
  }
  // 应用采集数据上报状态
  getSystemCollectorStatus() {
    return Request.get<SystemCollectorStatusModel>(`${this.path}/collectors/system_collectors_status/`);
  }
  // 批量获取任务下发状态
  getBatchSubscriptionStatus(params: {collector_id_list: string}) {
    return Request.get<Array<BatchSubscriptionStatusModel>>(`${this.path}/collectors/batch_subscription_status/`, { params });
  }
  // 批量获取应用采集状态
  getBatchSystemCollectorStatus(params: { system_ids: string }) {
    return Request.get<{[key: string]: SystemCollectorStatusModel}>(`${this.path}/collectors/bulk_system_collectors_status/`, {
      params,
    });
  }
  // 采集项清洗规则
  createCollectorEtl(params: {collector_config_id: number, [key: string]: any}) {
    const realParams = { ...params } as {collector_config_id?: number};
    delete realParams.collector_config_id;
    return Request.post(`${this.path}/collectors/${params.collector_config_id}/collector_etl/`, {
      params: realParams,
    });
  }
  // 获取最新上报的数据
  getTailLog(params: {collector_config_id: number, id: string}, payload = {}) {
    return Request.get<Array<CollectorTailLogModel>>(`${this.path}/collectors/${params.collector_config_id}/tail_log/`, {
      params,
      payload,
    });
  }
  // 获取任务下发状态(Task)
  getTaskStatus(params: {
    id: string,
    task_id_list: string}) {
    return Request.get<CollectorTaskStatusModel>(`${this.path}/collectors/${params.id}/task_status/`, { params });
  }
  // 采集详情
  getCollectorsById(params: Record<'id', string>, payload = {} as IRequestPayload) {
    return Request.get<CollectorDetailModel>(`${this.path}/collectors/${params.id}/`, { payload });
  }
  // 获取任务下发状态(Collector)
  getCollectorSubscriptionStatus(params: {collector_config_id: number }) {
    return Request.get<{contents: CollectorTaskStatusModel['contents']}>(`${this.path}/collectors/${params.collector_config_id}/subscription_status/`, {
      params,
    });
  }
  // 获取任务下发状态(Bcs)
  getBcsTaskStatus(params: {collector_config_id: number, task_id_list: []}) {
    return Request.get<{contents: BcsTaskStatusModel['contents']}>(`${this.path}/collectors/${params.collector_config_id}/task_status/?task_id_list=${params.task_id_list}`, {
      params,
    });
  }
  // 获取任务下发状态(Task)
  getCollectorTaskStatus(params: { collector_config_id: number, task_id_list: string }) {
    const realParams = { ...params } as {collector_config_id?: number};
    delete realParams.collector_config_id;
    return Request.get<CollectorTaskStatusModel>(`${this.path}/collectors/${params.collector_config_id}/task_status/`, {
      params: realParams,
    });
  }
  // 获取任务下发详情
  getCollectorTaskDetail(params: { collector_config_id: number, instance_id: string }) {
    const realParams = { ...params } as {collector_config_id?: number};
    delete realParams.collector_config_id;
    return Request.get<string>(`${this.path}/collectors/${params.collector_config_id}/task_detail/`, {
      params: realParams,
    });
  }
  // 重试订阅任务
  retryStask(params: { id: number, target_nodes?: Array<any>, instance_id_list?: Array<number> }) {
    const realParams = { ...params } as {id?: number};
    delete realParams.id;
    return Request.post<Array<string>>(`${this.path}/collectors/${params.id}/retry_task/`, {
      params: realParams,
    });
  }
  // 清洗预览
  getEtlPreview(params: { data: string, etl_config: string, etl_params?: Record<string, any> }) {
    return Request.post<Array<EtlPreviewModel>>(`${this.path}/collectors/etl_preview/`, {
      params,
    });
  }
  // 删除采集
  deleteCollector(params: {collector_config_id: number }) {
    return Request.delete(`${this.path}/collectors/${params.collector_config_id}/`);
  }
  // 切换数据关联状态
  updateJoinData(params: {system_id: string, resource_type_id:string, is_enabled: boolean}) {
    return Request.put<JoinDataModel>(`${this.path}/collectors/join_data/`, {
      params,
    });
  }
  // 预检查采集英文名
  preCheck(params: { collector_config_name_en: string }) {
    return Request.get<boolean>(`${this.path}/collectors/pre_check/`, {
      params,
    });
  }
  // 资源快照状态
  getSnapShotStatus(params: {
    system_id: string,
    resource_type_ids: string
  }) {
    return Request.get<Record<string,
    {
      bkbase_url: string,
      system_id: string,
      status:string,
      hdfs_status: 'failed' | 'preparing' | 'running' | 'closed',
      pull_type: 'partial' | 'full',
      status_msg: string,
    }>>(`${this.path}/collectors/snapshot_status/`, {
      params,
    });
  }
  // 判断资源表格操作列是否显示
  getResourceFeature() {
    return Request.get<Record<'enabled', boolean>>('/api/v1/feature/bkbase_aiops/');
  }
  // 清洗字段历史
  getFieldHistory(params: { id: string}) {
    return Request.get<Record<string, string>>(`${this.path}/collectors/${params.id}/etl_field_history/`);
  }
  // 获取yaml模板
  getLogConfigType(params: {log_config_type: string}) {
    return Request.get<Record<'yaml_config', string>>(`${this.path}/collectors/get_bcs_yaml_template/`, {
      params,
    });
  }
  // 校验yaml模板
  checkConfigYaml(params:{
    bk_biz_id: number,
    bcs_cluster_id: string,
    yaml_config: string,
  }) {
    return Request.post(`${this.path}/collectors/validate_container_config_yaml/`, {
      params,
    });
  }
  // 创建采集
  createBcs(params: Record<any, string>) {
    return Request.post(`${this.path}/collectors/bcs_collector/`, {
      params,
    });
  }
  // 更新采集
  updateBcs(params: { collector_config_id: number }) {
    return Request.put<Record<any, string>>(`${this.path}/collectors/${params.collector_config_id}/update_bcs_collector/`, {
      params,
    });
  }
  // 判断API Push是否启用
  getApiPushFeature(params: {feature_id: string}) {
    return Request.get<Record<'enabled', boolean>>(`/api/v1/feature/${params.feature_id}/`);
  }
  // 获取启用状态&上报host （无需单独鉴权）
  getApiPushHost(params: {system_id: string}) {
    return Request.get<Record<string, any>>(`${this.path}/collectors/api_push_host/`, {
      params,
    });
    // return Promise.resolve({
    //   data: {
    //     enabled: true,
    //     hosts: ['云区域0 grpc: http://xxx.xx.xxx.xx:4317 '],
    //   },
    // });
  }
  // 获取上报Token (编辑系统全选)
  apiPush(params: {system_id: string}) {
    return Request.get<Record<string, string>>(`${this.path}/collectors/api_push/`, {
      params,
    });
  }
  // 生成token
  createApiPush(params: {system_id: string}) {
    return Request.post(`${this.path}/collectors/create_api_push/`, {
      params,
    });
  }
  // 编辑系统权限
  getApiPushTailLog(params: {system_id: string}, payload = {}) {
    return Request.get<Array<CollectorTailLogModel>>(`${this.path}/collectors/api_push_tail_log/`, {
      params,
      payload,
    });
  }
  // 判断上报方式，计算平台已有数据源是否显示
  getBkbaseFeature(params: {feature_id: string}) {
    return Request.get<Record<'enabled', boolean>>(`/api/v1/feature/${params.feature_id}/`);
  }
}

export default new CollectorManage();
