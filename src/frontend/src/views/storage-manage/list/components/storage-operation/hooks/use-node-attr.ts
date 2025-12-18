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
import { computed } from 'vue';

import StorageManageService from '@service/storage-manage';

import type NodeAttrModel from '@model/storage/node-attr';

import useRequest from '@hooks/use-request';

export const genNodeAttrKey = (node: Record<'attr'|'value', string>): string => {
  if (!node || !node.attr || !node.value) {
    return '';
  }
  return `#${node.attr}#${node.value}`;
};
export const parseNodeAttrKey = (key: string): {name: string, value: string} => {
  if (!key) {
    return {
      name: '',
      value: '',
    };
  }
  const match = key.match(/#([^#]+)#(.*)$/) as [string, string, string];
  return {
    name: match[1],
    value: match[2],
  };
};

export default function () {
  const nodeAttrList = computed(() => {
    const countMap: {[key: string]: Array<NodeAttrModel>} = {};
    originalNodeAttrList.value.forEach((nodeAttr) => {
      const key = genNodeAttrKey(nodeAttr);
      if (countMap[key]) {
        countMap[key].push(nodeAttr);
      } else {
        countMap[key] = [nodeAttr];
      }
    });
    return Object.keys(countMap).reduce((result, key) => {
      const list = countMap[key];
      result.push({
        ...list[0],
        key: genNodeAttrKey(list[0]),
        num: list.length,
        list,
      });
      return result;
    }, [] as Array<NodeAttrModel & {key: string, num: number, list: NodeAttrModel[]}>);
  });

  const {
    loading,
    data: originalNodeAttrList,
    run: fetchNodeAttrList,
  } = useRequest(StorageManageService.fetchNodeAttrList, {
    defaultValue: [],
  });

  return {
    loading,
    nodeAttrList,
    fetchNodeAttrList,
  };
}
