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
import ScenePermissionApplicationModel from '@model/scene/scene-permission-application';

import ScenePermissionApplicationSource from '../source/scene-permission-application';

export default {
  /**
   * @desc 我的场景权限申请列表
   */
  fetchMineList(params: {
    page?: number;
    page_size?: number;
    scene_id?: number | string;
    status?: string;
  } = {}) {
    return ScenePermissionApplicationSource.getMineList(params)
      .then(({ data }) => ({
        ...data,
        results: data.results.map(item => new ScenePermissionApplicationModel(item)),
      }));
  },

  /**
   * @desc 提交场景权限申请
   */
  apply(params: {
    scene_id: number;
    role: string;
    reason: string;
  }) {
    return ScenePermissionApplicationSource.apply(params)
      .then(({ data }) => data);
  },
};
