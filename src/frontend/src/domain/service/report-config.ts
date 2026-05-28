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
import PanelModel from '@model/report-config/panel';

import PanelModelSource from '../source/report-config';

export default  {
  /**
   * @desc 分组列表
   */
  fetchGroups(params: {
    scope_id: number | string,
    scope_type : string,
  }) {
    return PanelModelSource.fetchGroups(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取场景报表列表
   */
  fetchPanels(params:{
    page: number,
    page_size: number,
    status?: 'published' | 'unpublished',
    keyword?: string,
    scene_id: string,
    name?: string,
    description?: string,
  }) {
    return PanelModelSource.fetchPanels(params)
      .then(({ data }) => data.map((item: PanelModel) => new PanelModel(item)));
  },
  /**
   * @desc 创建场景级报表
   */
  createPanel(params: {
    scene_id: string | number,
    vision_id: string,
    group_id: string,
    id: string,
    name: string,
    category: string,
    status?: 'published' | 'unpublished',
    description?: string,
  }) {
    return PanelModelSource.createPanel(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 更新场景报表
   */
  updatePanel(params: {
    id: string,
    scene_id: number | string,
    group_id: number,
    panel_id: string,
    name: string,
    status?: 'published' | 'unpublished',
    category?: string,
    description?: string,
  }) {
    return PanelModelSource.updatePanel(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 删除Panel
   */
  deletePanel(params: { id: string, scene_id: number | string}) {
    return PanelModelSource.deletePanel(params);
  },
  /**
   * @desc 更新场景报表分组内排序
   */
  orderPanels(params: {
    scene_id: number | string,
    items: Array<{
      panel_id: string,
      group_id: number,
      priority_index: number,
    }>,
  }) {
    return PanelModelSource.orderPanels(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 更新场景报表分组排序
   */
  orderGroups(params: {
    scene_id: number | string,
    groups: Array<{
      group_id: number,
      priority_index: number,
    }>,
  }) {
    return PanelModelSource.orderGroups(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 收藏/取消收藏Panel
   */
  updateFavorite(params: {
    panel_id: string,
    is_favorite: boolean,
  }) {
    return PanelModelSource.updateFavorite(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取Panel用户偏好
   */
  fetchPanelPreference() {
    return PanelModelSource.fetchPanelPreference()
      .then(({ data }) => data);
  },
  /**
   * @desc 更新Panel用户偏好
   */
  updatePanelPreference(params: {
    config: string,
  }) {
    return PanelModelSource.updatePanelPreference(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 创建场景级报表分组
   */
  createGroup(params: {
    scene_id: string | number,
    name: string,
    priority_index?: number,
  }) {
    return PanelModelSource.createGroup(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 更新场景级报表分组（重命名）
   */
  updateGroup(params: {
    scene_id: number | string,
    group_id: number,
    name: string,
    priority_index?: number,
  }) {
    return PanelModelSource.updateGroup(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 删除场景级报表分组
   */
  deleteGroup(params: { id: number | string, scene_id: number | string}) {
    return PanelModelSource.deleteGroup(params);
  },
};
