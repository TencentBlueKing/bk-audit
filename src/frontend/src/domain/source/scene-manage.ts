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
import type SceneModel from '@model/scene/scene';

import Request, {
  type IRequestPayload,
  type IRequestResponsePaginationData,
} from '@utils/request';

import ModuleBase from './module-base';

class SceneManage extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1/scene';
  }

  // 场景列表
  getSceneList(params: {
    keyword?: string;
    page?: number;
    page_size?: number;
    status?: 'enabled' | 'disabled' | '';
  } = {}, payload = {} as IRequestPayload) {
    // 过滤空值参数
    const filteredParams: Record<string, any> = {};
    Object.keys(params).forEach((key) => {
      const value = params[key as keyof typeof params];
      if (value !== undefined && value !== null && value !== '') {
        filteredParams[key] = value;
      }
    });
    return Request.get<IRequestResponsePaginationData<SceneModel>>(`${this.module}/`, {
      params: filteredParams,
      payload,
    });
  }

  // 创建场景
  createScene(params: {
    name: string;
    description?: string;
    managers: string[];
    users?: string[];
    systems?: Record<string, any>[];
    tables?: Record<string, any>[];
  }, payload = {} as IRequestPayload) {
    return Request.post<SceneModel>(`${this.module}/`, {
      params,
      payload,
    });
  }

  // 编辑场景
  updateScene(params: {
    id: string | number,
    scene_id?: number;
    name?: string;
    description?: string;
    managers?: string[];
    users?: string[];
    systems?: Record<string, any>[];
    tables?: Record<string, any>[];
  }, payload = {} as IRequestPayload) {
    return Request.put<SceneModel>(`${this.module}/${params.id}/`, {
      params,
      payload,
    });
  }

  // 场景详情
  getSceneDetail(id: string | number, payload = {} as IRequestPayload) {
    return Request.get<SceneModel>(`${this.module}/${id}/`, { payload });
  }

  // 启用场景
  enableScene(id: string | number, payload = {} as IRequestPayload) {
    return Request.post<SceneModel>(`${this.module}/${id}/enable/`, { payload });
  }

  // 停用场景
  disableScene(id: string | number, payload = {} as IRequestPayload) {
    return Request.post<SceneModel>(`${this.module}/${id}/disable/`, { payload });
  }

  // 删除场景
  deleteScene(id: string | number, payload = {} as IRequestPayload) {
    return Request.delete(`${this.module}/${id}/`, { payload });
  }
}

export default new SceneManage();
