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
    page: number,
    page_size: number,
  }) {
    return PanelModelSource.fetchGroups(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 分组Panel列表
   */
  fetchPanels(params:{
    page: number,
    page_size: number,
    is_enabled?: boolean,
    keyword?: string,
  }) {
    return PanelModelSource.fetchPanels(params)
      .then(({ data }) => data.map((item: PanelModel) => new PanelModel(item)));
  },
  /**
   * @desc 创建Panel
   */
  createPanel(params: {
    vision_id: string,
    name: string,
    group_name: string,
    description?: string,
    is_enabled?: boolean,
  }) {
    return PanelModelSource.createPanel(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 更新Panel
   */
  updatePanel(params: {
    id: string,
    name?: string,
    description?: string,
    group_name?: string,
    vision_id?: string,
    is_enabled?: boolean,
  }) {
    return PanelModelSource.updatePanel(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 删除Panel
   */
  deletePanel(params: { id: string }) {
    return PanelModelSource.deletePanel(params);
  },

};
