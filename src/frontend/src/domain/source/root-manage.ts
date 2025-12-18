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
import type ConfigModel from '@model/root/config';

import Request, {
  type IRequestPayload,
} from '@utils/request';

import ModuleBase from './module-base';

class Root extends ModuleBase {
  constructor() {
    super();
    this.module = '/';
  }

  config(params = {}, payload = {} as IRequestPayload) {
    return Request.get<ConfigModel>(`${this.module}`, {
      params,
      payload,
    });
  }

  language(params: { id: string }, payload = {} as IRequestPayload) {
    return Request.get(`/i18n/${params.id}/`, {
      params,
      payload,
    });
  }
}

export default new Root();
