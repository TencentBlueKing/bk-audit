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

export const buildTree = (obj: any, parentId = '', path: string[] = [], isChild = false, type = 'object', nameCountMap = new Map<string, number>())  => {
  const result: any[] = [];

  // 如果是对象，我们递归它的每个键值对
  if (typeof obj === 'object' && obj !== null) {
    const keys = Object.keys(obj);
    keys.forEach((key) => {
      const currentPath = [...path, key];
      const currentId = parentId
        ? `${parentId}.${key}`
        : `${key}`;

      // 检测节点名称是否重复
      const currentCount = nameCountMap.get(key) || 0;
      nameCountMap.set(key, currentCount + 1);

      // 根据重复情况设置显示名称
      const displayName = `${key} (${currentId})`;

      const node = {
        name: displayName,
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
        // 如果值是对象且不是数组，递归（传递相同的名称计数映射）
        node.children = buildTree(obj[key], currentId, currentPath, true, 'kv', nameCountMap);
      } else if (Array.isArray(obj[key])) { // 如果值是数组
        if (obj[key].length > 0 && typeof obj[key][0] === 'object' && obj[key][0] !== null) {
          // 如果数组中的每一项都是对象，将其视为表格
          node.type = 'table';
          const childNodes = buildTree(obj[key][0], currentId, currentPath, true, 'list', nameCountMap);
          node.list = childNodes;
        } else {
          // 如果数组中的项不是对象（比如字符串、数字等），将其视为普通数组字段
          node.children = [];
          node.type = 'kv'; // 可以添加一个专门的类型标识
        }
      } else {
        // 其他类型（字符串、数字、布尔值等）不需要子节点
        node.children = [];
        node.type = 'kv'; // 可以添加类型标识
      }

      result.push(node);
    });
  }
  return result;
};
