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
import SceneModel from '@model/scene/scene';

import SceneManageSource from '../source/scene-manage';

export default {
  /**
   * @desc 获取场景列表
   * @param { Object } params
   */
  fetchSceneList(params: {
    keyword?: string;
    page?: number;
    page_size?: number;
    status?: 'enabled' | 'disabled';
  } = {}) {
    return SceneManageSource.getSceneList(params)
      .then(({ data }) => ({
        ...data,
        results: data.results.map((item: SceneModel) => new SceneModel(item)),
      }));
  },

  /**
   * @desc 创建场景
   * @param { Object } params
   */
  createScene(params: {
    name: string;
    description?: string;
    managers: string[];
    users?: string[];
    systems?: Record<string, any>[];
    tables?: Record<string, any>[];
  }) {
    return SceneManageSource.createScene(params)
      .then(({ data }) => new SceneModel(data));
  },

  /**
   * @desc 编辑场景
   * @param { String } id - 场景 ID
   * @param { Object } params
   */
  updateScene(params: {
    id: string | number;
    scene_id?: number;
    name?: string;
    description?: string;
    managers?: string[];
    users?: string[];
    systems?: Record<string, any>[];
    tables?: Record<string, any>[];
  }) {
    return SceneManageSource.updateScene(params)
      .then(({ data }) => new SceneModel(data));
  },

  /**
   * @desc 编辑场景基础信息（场景管理员）
   * @param { Object } params
   */
  updateSceneInfo(params: {
    sceneId: string | number;
    name?: string;
    description?: string;
    managers?: string[];
    users?: string[];
  }) {
    return SceneManageSource.updateSceneInfo(params)
      .then(({ data }) => new SceneModel(data));
  },

  /**
   * @desc 获取场景详情
   * @param { String|Number } id - 场景 ID
   */
  fetchSceneDetail(id: string | number) {
    return SceneManageSource.getSceneDetail(id)
      .then(({ data }) => new SceneModel(data));
  },

  /**
   * @desc 获取场景信息（场景管理员可查看）
   * @param { String|Number } id - 场景 ID
   */
  fetchSceneInfo(id: string | number) {
    return SceneManageSource.getSceneInfo(id)
      .then(({ data }) => new SceneModel(data));
  },

  /**
   * @desc 启用场景
   * @param { String|Number } id - 场景 ID
   */
  enableScene(id: string | number) {
    return SceneManageSource.enableScene(id)
      .then(({ data }) => new SceneModel(data));
  },

  /**
   * @desc 停用场景
   * @param { String|Number } id - 场景 ID
   */
  disableScene(id: string | number) {
    return SceneManageSource.disableScene(id)
      .then(({ data }) => new SceneModel(data));
  },

  /**
   * @desc 删除场景
   * @param { String|Number } id - 场景 ID
   */
  deleteScene(id: string | number) {
    return SceneManageSource.deleteScene(id);
  },

  /**
   * @desc 场景精简列表
   * @param { Object } params
   */
  fetchSceneAll(params: { status?: 'enabled' | 'disabled' } = {}) {
    return SceneManageSource.getSceneAll(params)
      .then(({ data }) => data);
  },
};
