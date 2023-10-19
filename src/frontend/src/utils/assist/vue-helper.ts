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
import _ from 'lodash';

const isListener = (key: string) => /^on[A-Z]/.test(key);
const isCSS = (key: string) => /^(class|style)$/.test(key);

export const attrsWithoutListener = (attrs: Record<string, any>) => Object.keys(attrs).reduce((result, key) => {
  if (!(isListener(key) && _.isFunction(attrs[key]))) {
    return {
      ...result,
      [key]: attrs[key],
    };
  }
  return result;
}, {});

export const attrsOnlyProp = (attrs: Record<string, any>) => Object.keys(attrs).reduce((result, key) => {
  if (!isCSS(key)
    && !(isListener(key) && _.isFunction(attrs[key]))) {
    return {
      ...result,
      [key]: attrs[key],
    };
  }
  return result;
}, {});
