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

export const buildTree = (obj: any, parentId = '', path: string[] = [], isChild = false, type = 'object')  => {
  const result: any[] = [];

  // 如果是对象，我们递归它的每个键值对
  if (typeof obj === 'object' && obj !== null) {
    const keys = Object.keys(obj);
    keys.forEach((key) => {
      const currentPath = [...path, key];
      const currentId = parentId
        ? `${parentId}.${key}`
        : `${key}`;

      const node = {
        name: key,
        json_path: currentId,
        isChecked: false,
        isChild,
        children: [] as any[],
        list: [] as any[],
        type,
        config: null,
        listName: '',
        listDescription: '',
      };
      if (typeof obj[key] === 'object' && obj[key] !== null && !Array.isArray(obj[key])) {
        // 如果值是对象且不是数组，递归
        node.children = buildTree(obj[key], currentId, currentPath, true, 'kv');
      } else if (Array.isArray(obj[key]) && obj[key].length > 0) { // 如果值是数组 代表list
        // 递归它的第一个元素
        node.type = 'table';
        const childNodes = buildTree(obj[key][0], currentId, currentPath, true, 'list');
        node.list = childNodes;
      }

      result.push(node);
    });
  }
  return result;
};
