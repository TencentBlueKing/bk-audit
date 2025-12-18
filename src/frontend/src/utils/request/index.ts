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
import type {
  CancelTokenSource,
} from 'axios';
import _ from 'lodash';

import {
  buildURLParams,
  downloadUrl,
} from '@utils/assist';

import Request, {
  type Config,
  type Method,
} from './lib/request';

export type IRequestPayload = Config['payload']

type IRequestConfig = Pick<Config, 'params' | 'payload'> & {
  responseType?: string;
}
interface IRequestResponseResult<T>{
  readonly 'result': boolean,
  readonly 'code': number,
  readonly 'message': string,
  readonly 'request_id':string
  readonly 'data': T
}

export type IRequestResponseData<T> = T
export interface IRequestResponsePaginationData<T>{
  results: Array<T>,
  page: number,
  num_pages: number,
  total: number
}

const methodList:Array<Method> = ['get', 'delete', 'post', 'put', 'download'];

let cancelTokenSource: CancelTokenSource;

export const setCancelTokenSource = (source: CancelTokenSource) => {
  cancelTokenSource = source;
};

export const getCancelTokenSource = () => cancelTokenSource;

const handler = {} as {
  [n in Method]: <T = any>(url: string, config?: IRequestConfig)=>
  Promise<IRequestResponseResult<T>>
};

methodList.forEach((method) => {
  Object.defineProperty(handler, method, {
    get() {
      return function (url: string, config?: IRequestConfig) {
        if (method === 'download') {
          downloadUrl(`${window.PROJECT_CONFIG.AJAX_URL_PREFIX}/${_.trim(url, '/')}?${buildURLParams(config?.params)}`);
          return Promise.resolve();
        }
        const handler = new Request({
          url,
          method,
          ...config,
        });
        return handler.run();
      };
    },
  });
});

export default handler;
