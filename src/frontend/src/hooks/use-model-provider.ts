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
import {
  type ComponentInternalInstance,
  getCurrentInstance,
} from 'vue';

const findProvider = (componentInstance: ComponentInternalInstance | null): ComponentInternalInstance | null => {
  let target = null;
  const search = (childrenList: any[] | string) => {
    if (!Array.isArray(childrenList) || !childrenList) {
      return;
    }
    childrenList.forEach((child) => {
      if (child.isMounted
        && typeof child.exposed?.submit === 'function') {
        target = child;
        return;
      }
      if (typeof child.type !== 'object'
        && typeof child.type !== 'function') {
        return search(child.children);
      }
      if (child.isMounted && child.subTree) {
        search([child.subTree]);
      } else if (child.component) {
        search([child.component]);
      } else {
        search(child.children);
      }
    });
  };
  search([componentInstance]);
  return target;
};

export default function () {
  const currentInstance = getCurrentInstance();
  return () => {
    const provider = findProvider(currentInstance);
    if (!provider) {
      return {
        submit: () => Promise.resolve(),
        cancel: () => Promise.resolve(),
      };
    }

    const {
      submit = () => Promise.resolve(),
      cancel = () => Promise.resolve(),
    } = provider.exposed as Record<'submit'|'cancel', () => Promise<any>>;

    return {
      submit,
      cancel,
    };
  };
}
