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
import type HostInstanceStatusModel from '@model/biz/host-instance-status';
import type TopoModel from '@model/biz/topo';

export interface TTopoTreeData {
  id: string;
  name: string;
  children: Array<TTopoTreeData>;
  payload: TopoModel
}

export const transformTopoToTree = (topoData: Array<TopoModel>): Array<TTopoTreeData> => {
  if (!topoData || topoData.length < 1) {
    return [];
  }
  return topoData.map(data => ({
    id: `#${data.bk_obj_id}#${data.bk_inst_id}`,
    name: data.bk_inst_name,
    children: transformTopoToTree(data.children),
    payload: data,
  }));
};

export const getTopoNodeIPList = (topoTreeData: Array<TopoModel>, BkInstId: number) => {
  const result: TopoModel['ip_list'] = [];
  const search = (nodeList: Array<TopoModel>, destiny = false) => {
    if (!nodeList || nodeList.length < 1) {
      return;
    }
    for (let i = 0; i < nodeList.length; i++) {
      const nodeChild = nodeList[i];
      if (nodeChild.bk_inst_id === BkInstId) {
        result.push(...nodeChild.ip_list);
        search(nodeChild.children, true);
        break;
      }
      if (destiny) {
        result.push(...nodeChild.ip_list);
      }
      search(nodeChild.children, destiny);
    }
  };
  search(topoTreeData, false);
  return result;
};

export const getTopoNodeByBkInstId = (topoTreeData: Array<TopoModel>, BkInstId: number) => {
  const search = (nodeList: Array<TopoModel>): TopoModel|null => {
    if (!nodeList || nodeList.length < 1) {
      return null;
    }
    for (let i = 0; i < nodeList.length; i++) {
      const nodeChild = nodeList[i];
      if (nodeChild.bk_inst_id === BkInstId) {
        return nodeChild;
      }
      const res = search(nodeChild.children);
      if (res) {
        return res;
      }
    }
    return null;
  };
  return search(topoTreeData);
};

export const getChildNodeList =  (topoTreeData: Array<TopoModel>, BkInstId: number) => {
  const result: TopoModel[] = [];
  // debugger;
  const search = (nodeList: Array<TopoModel>) => {
    if (!nodeList || nodeList.length < 1) {
      return;
    }
    for (let i = 0; i < nodeList.length; i++) {
      const nodeChild = nodeList[i];
      if (nodeChild.bk_inst_id === BkInstId) {
        result.push(...nodeChild.children);
        break;
      }
      search(nodeChild.children);
    }
  };
  search(topoTreeData);
  return result;
};

export const getHostKey = <T extends { ip: string; bk_cloud_id: number } >(data:T) => `#${data.bk_cloud_id}#${data.ip}`;

export const mergeCustomInputHost = (
  hostList: Array<HostInstanceStatusModel>,
  customInputHostList: Array<HostInstanceStatusModel>,
) => {
  const result = [...hostList];
  const hostMap = hostList.reduce((result, item) => ({
    ...result,
    [getHostKey(item)]: true,
  }), {} as Record<string, boolean>);
  customInputHostList.forEach((item) => {
    if (!hostMap[getHostKey(item)]) {
      result.push(item);
    }
  });

  return result;
};
