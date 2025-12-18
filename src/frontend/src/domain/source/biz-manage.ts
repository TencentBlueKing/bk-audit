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
import type BizModel from '@model/biz/biz';
import type HostInstanceStatusModel from '@model/biz/host-instance-status';
import type NodeInstanceStatusModel from '@model/biz/node-instance-status';
import type TemplateTopoModel from '@model/biz/template-topo';
import type TopoModel from '@model/biz/topo';

import Request from '@utils/request';

import ModuleBase from './module-base';

class BizManage extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1/meta';
  }

  // 业务列表
  getAll() {
    return Request.get<Array<BizModel>>(`${this.module}/spaces/`);
  }
  // 业务拓扑
  getAllTopo(params: {
    biz_id: string,
    instance_type?: string,
    remove_empty_nodes?: boolean}) {
    const realParams = { ...params } as { biz_id?: string };
    delete realParams.biz_id;
    return Request.get<Array<TopoModel>>(`${this.module}/bizs/${params.biz_id}/biz_topos/`, {
      params: realParams,
    });
  }
  // 节点列表
  getTemplateNodesBaseInfo(params: {
    biz_id: string,
    bk_inst_ids: string,
    template_type: string}) {
    const realParams = { ...params } as { biz_id?: string };
    delete realParams.biz_id;
    return Request.get<Array<NodeInstanceStatusModel>>(`${this.module}/bizs/${params.biz_id}/get_nodes_by_template/`, {
      params: realParams,
    });
  }
  // 实例列表(ip)
  getHostBaseInfo(params: {biz_id: string, ip_list: HostInstanceStatusModel}) {
    const realParams = { ...params } as { biz_id?: string };
    delete realParams.biz_id;
    return Request.post<Array<HostInstanceStatusModel>>(`${this.module}/bizs/${params.biz_id}/host_instance_by_ip/`, {
      params: realParams,
    });
  }
  // 实例列表
  getNodeBaseInfo(params: {biz_id: string, node_list: NodeInstanceStatusModel}) {
    const realParams = { ...params } as { biz_id?: string };
    delete realParams.biz_id;
    return Request.post<Array<NodeInstanceStatusModel>>(`${this.module}/bizs/${params.biz_id}/host_instance_by_node/`, {
      params: realParams,
    });
  }
  // 获取Agent状态
  getNodeAgentStatus(params: {biz_id: string, node_list: NodeInstanceStatusModel}) {
    const realParams = { ...params } as { biz_id?: string };
    delete realParams.biz_id;
    return Request.post<Array<NodeInstanceStatusModel>>(`${this.module}/bizs/${params.biz_id}/list_agent_status/`, {
      params: realParams,
    });
  }
  // 服务模板拓扑
  getAllTemplateTopo(params: {biz_id: string, template_type: string}) {
    const realParams = { ...params } as { biz_id?: string };
    delete realParams.biz_id;
    return Request.get<{children: Array<TemplateTopoModel>}>(`${this.module}/bizs/${params.biz_id}/template_topos/`, {
      params: realParams,
    });
  }
}

export default new BizManage();
