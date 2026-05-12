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
    description?: string;
    keyword?: string;
    manager?: string;
    name?: string;
    page?: number;
    page_size?: number;
    scene_id?: string | number;
    sort?: string[];
    status?: 'enabled' | 'disabled' | '';
    updated_by?: string;
    user?: string;
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

  // 编辑场景基础信息（场景管理员）
  updateSceneInfo(params: {
    sceneId: string | number;
    name?: string;
    description?: string;
    managers?: string[];
    users?: string[];
  }, payload = {} as IRequestPayload) {
    const { sceneId, ...rest } = params;
    return Request.patch<SceneModel>(`${this.module}/${sceneId}/update_scene_info/`, {
      params: rest,
      payload,
    });
  }

  // 场景详情
  getSceneDetail(id: string | number, payload = {} as IRequestPayload) {
    return Request.get<SceneModel>(`${this.module}/${id}/`, { payload });
  }

  // 获取场景信息（场景管理员可查看）
  getSceneInfo(id: string | number, payload = {} as IRequestPayload) {
    return Request.get<SceneModel>(`${this.module}/${id}/get_scene_info/`, { payload });
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

  // 获取场景下有权限的系统列表
  getScenePermissionSystems(sceneId: string | number, payload = {} as IRequestPayload) {
    return Request.get<Array<{ system_id: string; system_name: string }>>(
      `${this.module}/${sceneId}/scene_permission_systems/`,
      { params: { scene_id: sceneId }, payload },
    );
  }

  // 获取场景下有权限的数据表列表
  getScenePermissionTables(sceneId: string | number, payload = {} as IRequestPayload) {
    return Request.get<Array<{ table_id: string }>>(
      `${this.module}/${sceneId}/scene_permission_tables/`,
      { params: { scene_id: sceneId }, payload },
    );
  }

  // 场景精简列表
  getSceneAll(params: { status?: 'enabled' | 'disabled' } = {}, payload = {} as IRequestPayload) {
    return Request.get<Array<{
      scene_id: number;
      name: string;
      status: 'enabled' | 'disabled';
      permission: Record<string, boolean>;
      description?: string;
      managers?: string[];
    }>>(`${this.module}/all/`, { params, payload });
  }

  // 获取场景下用户组成员列表
  getSceneMembers(params: {
    scene_id: string | number;
  }) {
    return Request.get(`${this.module}/${params.scene_id}/scene_members/`, {
      params,
    });
  }
}

export default new SceneManage();
