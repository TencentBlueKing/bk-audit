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
import BatchSubscriptionStatusModel from '@model/collector/batch-subscription-status';
import { BcsContent as BcsTaskStatusContent } from '@model/collector/bcs-task-status';
import CollectorDetailModel from '@model/collector/collector-detail';
import CollectorTailLogModel from '@model/collector/collector-tail-log';
import CollectorEtlPreviewModel from '@model/collector/etl-preview';
import JoinDataModel from '@model/collector/join-data';
import CollectorTaskStatusModel, {
  Content as TaskStatusContent,
} from '@model/collector/task-status';

import CollectorSource from '../source/collector-manage';

export default {
  /**
   * @desc 采集列表
   * @param { String } system_id
   */
  fetchList(params:  Record<'system_id', string>) {
    return CollectorSource.getAllCollectors(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 新建采集
   * @param { Object } params
   */
  create(params: Record<any, string>) {
    return CollectorSource.create(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 更新采集
   * @param { Object } params
   */
  update(params: Record<'collector_config_id', number>) {
    return CollectorSource.update(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 应用采集数据上报状态
   */
  fetchSystemCollectStatus() {
    return CollectorSource.getSystemCollectorStatus()
      .then(({ data }) => data);
  },
  /**
   * @desc 批量获取任务下发状态
   * @param { String } collector_id_list
   */
  fetchBatchSubscriptionStatus(params: Record<'collector_id_list', string>) {
    return CollectorSource.getBatchSubscriptionStatus(params)
      .then(({ data }) => data.map(item => new BatchSubscriptionStatusModel(item)));
  },
  /**
   * @desc 批量获取应用采集状态
   * @param { String } system_ids
   */
  fetchBatchSystemCollectorStatusList(params: { system_ids: string }) {
    return CollectorSource.getBatchSystemCollectorStatus(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取最新上报的数据
   * @param { Object } params
   */
  fetchTailLog(params: {id: string, collector_config_id: number}) {
    return CollectorSource.getTailLog(params, {
      permission: 'catch',
    })
      .then(({ data }) => data.map(item => new CollectorTailLogModel(item)));
  },
  /**
   * @desc 获取任务下发状态(Task)
   * @param { Object } params
   */
  fetchTaskStatusList(params: {
    id: string,
    task_id_list: string,
  }) {
    return CollectorSource.getTaskStatus(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 采集详情
   * @param { String } id
   */
  fetchCollectorsById(params: Record<'id', string>) {
    return CollectorSource.getCollectorsById(params, {
      // cache: true,
    })
      .then(({ data }) => new CollectorDetailModel(data));
  },
  /**
   * @desc 获取任务下发状态(Collector)
   * @param { String } collector_config_id
   */
  fetchCollectorSubscriptionStatus(params: Record<'collector_config_id', number>) {
    return CollectorSource.getCollectorSubscriptionStatus(params)
      .then(({ data }) => {
        if (data.contents.length > 0) {
          return new TaskStatusContent(data.contents[0]);
        }
        return new TaskStatusContent();
      });
  },
  /**
   * @desc 获取任务下发状态(Bcs)
   * @param { String } collector_config_id
   */
  fetchBcsTaskStatus(params: {collector_config_id: number, task_id_list: []}) {
    return CollectorSource.getBcsTaskStatus(params)
      .then(({ data }) => {
        if (data.contents.length > 0) {
          return new BcsTaskStatusContent(data.contents[0]);
        }
        return new BcsTaskStatusContent();
      });
  },
  /**
   * @desc 获取任务下发状态(Task)
   * @param { String } collector_config_id
   * @param { String } task_id_list】
   */
  fetchCollectorTaskStatus(params: { collector_config_id: number, task_id_list: string }) {
    return CollectorSource.getCollectorTaskStatus(params)
      .then(({ data }) =>  new CollectorTaskStatusModel(data));
  },
  /**
   * @desc 获取任务下发详情
   * @param { Number } collector_config_id
   * @param { String } instance_id
   */
  fetchCollectorTaskDetail(params: { collector_config_id: number, instance_id: string }) {
    return CollectorSource.getCollectorTaskDetail(params)
      .then(({ data }) =>  data);
  },
  /**
   * @desc 重试订阅任务
   * @param { Object } params
   * @returns { Boolean }
   */
  retryStask(params: { id: number, target_nodes: Array<any>,  instance_id_list?: Array<number> }) {
    return CollectorSource.retryStask(params)
      .then(({ data }) =>  data);
  },
  /**
   * @desc 清洗预览
   * @param { Object } params
   * @returns { Boolean }
   */
  fetchEtlPreview(params: { data: string, etl_config: string, etl_params?: Record<string, any> }) {
    return CollectorSource.getEtlPreview(params)
      .then(({ data }) => data.map(item => new CollectorEtlPreviewModel(item)));
  },
  /**
   * @desc 删除采集
   * @param { Number } collector_config_id
   */
  deleteCollector(params: { collector_config_id: number }) {
    return CollectorSource.deleteCollector(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 采集项清洗规则
   * @param { Object } params
   */
  createCollectorEtl(params:
    {
      collector_config_id: number,
      etl_config: string,
      etl_params: {
        delimiter: string,
        retain_original_text: boolean
      },
      fields: []
    }) {
    return CollectorSource.createCollectorEtl(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 切换数据关联状态
   * @param { Object } params-
   */
  fetchJoinData(params:
    {
      system_id: string,
      resource_type_id: string,
      is_enabled: boolean
    }) {
    return CollectorSource.updateJoinData(params)
      .then(({ data }) => new JoinDataModel(data));
  },
  /**
   * @desc 预检查采集英文名
   * @param { Object } params
   */
  preCheck(params:
  {
    collector_config_name_en: string,
    bk_biz_id?: number
  }) {
    return CollectorSource.preCheck(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 资源快照状态
   * @param { Object } params
   */
  fetchSnapShotStatus(params: {
    system_id: string,
    resource_type_ids: string
  }) {
    return CollectorSource.getSnapShotStatus(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 清洗字段历史
   * @param { String } id
   */
  fetchFieldHistory(params: {id: string}) {
    return CollectorSource.getFieldHistory(params)
      .then(({ data }) => data);
  },

  /**
   * @desc 获取yaml配置模板
   * @param { String } log_config_type
   */
  fetchLogConfigType(params: {log_config_type: string}) {
    return CollectorSource.getLogConfigType(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 校验yaml格式
   * @param { Object } params
   */
  fetchConfigYaml(params: {
    bk_biz_id: number,
    bcs_cluster_id: string,
    yaml_config: string,
  }) {
    return CollectorSource.checkConfigYaml(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 新建采集bcs
   * @param { Object } params
   */
  createBcs(params: Record<any, string>) {
    return CollectorSource.createBcs(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 更新采集bsc
   * @param { Object } params
   */
  updateBcs(params: Record<'collector_config_id', number>) {
    return CollectorSource.updateBcs(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 判断API Push是否启用
   */
  fetchApiPushFeature(params: {system_id: string}) {
    return CollectorSource.getApiPushFeature(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取启用状态&上报host （无需单独鉴权）
   */
  fetchApiPushHost(params: {system_id: string}) {
    return CollectorSource.getApiPushHost(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取上报Token (编辑系统全选)
   */
  fetchApiPush(params: {system_id: string}) {
    return CollectorSource.apiPush(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 编辑系统权限
   */
  fetchApiPushTailLog(params: {system_id: string}) {
    return CollectorSource.getApiPushTailLog(params, {
      permission: 'catch',
    })
      .then(({ data }) => data.map(item => new CollectorTailLogModel(item)));
  },
  /**
   * @desc 生成token
   */
  createApiPush(params: {system_id: string}) {
    return CollectorSource.createApiPush(params)
      .then(({ data }) => data);
  },
};
