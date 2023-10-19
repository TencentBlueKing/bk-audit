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
import BizModel from '@model/biz/biz';
import HostInstanceStatusModel from '@model/biz/host-instance-status';
import NodeInstanceStatusModel from '@model/biz/node-instance-status';
import TemplateTopoModel from '@model/biz/template-topo';
import TopoModel from '@model/biz/topo';

import BizSource from '../source/biz-manage';

export default {
  /**
   * @desc 业务列表
   */
  fetchList() {
    return BizSource.getAll()
      .then(({ data }) => data.map(item => new BizModel(item)));
  },
  /**
   * @desc 业务拓扑
   * @param { Object } params
   */
  fetchTopoTree(params: {
    biz_id: string,
    instance_type?: string,
    remove_empty_nodes?: boolean}) {
    return BizSource.getAllTopo(params)
      .then(({ data }) => data.map(item => new TopoModel(item)));
  },
  /**
   * @desc 实例列表
   * @param { Object } params
   */
  fetchNodeBaseInfo(params: {biz_id: string, node_list: NodeInstanceStatusModel}) {
    return BizSource.getNodeBaseInfo(params)
      .then(({ data }) => data.map(item => new NodeInstanceStatusModel(item)));
  },
  /**
   * @desc 获取Agent状态
   * @param { Object } params
   */
  fetchNodeAgentStatus(params: {biz_id: string, node_list: NodeInstanceStatusModel}) {
    return BizSource.getNodeAgentStatus(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 实例列表(ip)
   * @param { Object } params
   */
  fetchHostBaseInfo(params: {biz_id: string, ip_list: HostInstanceStatusModel}) {
    return BizSource.getHostBaseInfo(params)
      .then(({ data }) => data.map(item => new HostInstanceStatusModel(item)));
  },
  /**
   * @desc 服务模板拓扑
   * @param { String } biz_id
   * @param { String } template_type
   */
  fetchAllTemplateTopo(params: {biz_id: string, template_type: string}) {
    return BizSource.getAllTemplateTopo(params)
      .then(({ data }) => data.children.map(item => new TemplateTopoModel(item)));
  },
  /**
   * @desc 节点列表
   * @param { Object } params
   */
  fetchTemplateNodesBaseInfo(params: {
    biz_id: string,
    bk_inst_ids: string,
    template_type: string}) {
    return BizSource.getTemplateNodesBaseInfo(params)
      .then(({ data }) => data.map(item => new NodeInstanceStatusModel(item)));
  },

};
