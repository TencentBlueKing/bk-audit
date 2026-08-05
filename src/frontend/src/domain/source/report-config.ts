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


import Request, { type IRequestResponsePaginationData } from '@utils/request';

import PanelModel, {
  type PanelDefaultValueOverrides,
  type PanelDetail,
  type PanelVisibilityPayload,
} from './../model/report-config/panel';
import ModuleBase from './module-base';

class PanelManage extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1';
  }
  // 获取报表分组列表
  fetchGroups(params: {
    scope_id: number | string,
    scope_type : string,
  }) {
    return Request.get(`bkvision${this.module}/panels/group/`, {
      params,
    });
  }
  // 获取分组Panel列表
  fetchPanels(params: {
    page: number,
    page_size: number,
    status?: 'published' | 'unpublished',
    keyword?: string,
    scene_id: string,
    name?: string,
    description?: string,
  }) {
    return Request.get<PanelModel[]>(`bkvision${this.module}/panel/scene/`, {
      params,
    });
  }
  // 创建Panel
  createPanel(params: {
    scene_id: string | number,
    group_id: string | number,
    vision_id: string,
    id?: string,
    name: string,
    category?: string,
    status?: 'published' | 'unpublished',
    description?: string,
    input_variable?: Array<Record<string, any>>,
    default_value_overrides?: PanelDefaultValueOverrides,
  }) {
    return Request.post(`bkvision${this.module}/panel/scene/`, {
      params,
    });
  }
  // 更新场景报表
  updatePanel(params: {
    id: string,
    scene_id: number | string,
    group_id: number,
    panel_id: string,
    vision_id?: string,
    name: string,
    status?: 'published' | 'unpublished',
    category?: string,
    description?: string,
    input_variable?: Array<Record<string, any>>,
    default_value_overrides?: PanelDefaultValueOverrides,
  }) {
    const { id, ...rest } = params;
    return Request.put(`bkvision${this.module}/panel/scene/${id}/`, {
      params: rest,
    });
  }
  // 删除Panel
  deletePanel(params: { id: string, scene_id: number | string}) {
    return Request.delete(`bkvision${this.module}/panel/scene/${params.id}/`, {
      params,
    });
  }
  // 更新场景报表分组内排序
  orderPanels(params: {
    scene_id: number | string,
    items: Array<{
      panel_id: string,
      group_id: number,
      priority_index: number,
    }>,
  }) {
    return Request.post(`bkvision${this.module}/panel/scene/group/item/order/`, {
      params,
    });
  }
  // 更新场景报表分组排序
  orderGroups(params: {
    scene_id: number | string,
    groups: Array<{
      group_id: number,
      priority_index: number,
    }>,
  }) {
    return Request.post(`bkvision${this.module}/panel/scene/group/order/`, {
      params,
    });
  }
  // 收藏/取消收藏Panel
  updateFavorite(params: {
    panel_id: string,
    is_favorite: boolean,
  }) {
    return Request.post(`bkvision${this.module}/panels/favorite/`, {
      params,
    });
  }
  // 获取Panel用户偏好
  fetchPanelPreference() {
    return Request.get<{ config: string }>(`bkvision${this.module}/panels/get_panel_preference/`);
  }
  // 更新Panel用户偏好
  updatePanelPreference(params: {
    config: string,
  }) {
    return Request.put(`bkvision${this.module}/panels/update_panel_preference/`, {
      params,
    });
  }
  // 创建场景级报表分组
  createGroup(params: {
    scene_id: string | number,
    name: string,
    priority_index?: number,
  }) {
    return Request.post(`bkvision${this.module}/panel/scene/group/`, {
      params,
    });
  }
  // 更新场景级报表分组（重命名）
  updateGroup(params: {
    scene_id: number | string,
    group_id: number,
    name: string,
    priority_index?: number,
  }) {
    return Request.put(`bkvision${this.module}/panel/scene/group/${params.group_id}/`, {
      params,
    });
  }
  // 删除场景级报表分组
  deleteGroup(params: { id: number | string, scene_id: number | string}) {
    return Request.delete(`bkvision${this.module}/panel/scene/group/${params.id}/`, {
      params,
    });
  }
  // 获取平台级报表列表
  fetchPlatformPanels(params: {
    enable_paginate?: boolean,
    page?: number,
    page_size?: number,
    status?: 'published' | 'unpublished',
    name?: string,
    description?: string,
    updated_by?: string,
    vision_id?: string,
    visibility_type?: string,
    scene_ids?: string | number[],
    system_ids?: string | string[],
    scenario?: string,
  }) {
    return Request.get<IRequestResponsePaginationData<PanelModel>>(
      `bkvision${this.module}/panel/platform/`,
      {
        params: {
          enable_paginate: true,
          ...params,
        },
      },
    );
  }
  // 创建平台级报表
  createPlatformPanel(params: {
    vision_id?: string,
    name: string,
    category?: string,
    description?: string,
    status?: 'published' | 'unpublished',
    visibility?: PanelVisibilityPayload,
    default_value_overrides?: PanelDefaultValueOverrides,
  }) {
    return Request.post(`bkvision${this.module}/panel/platform/`, {
      params,
    });
  }
  // 更新平台级报表
  updatePlatformPanel(params: {
    panel_id: string,
    vision_id?: string,
    name?: string,
    category?: string,
    description?: string,
    status?: 'published' | 'unpublished',
    visibility?: PanelVisibilityPayload,
    default_value_overrides?: PanelDefaultValueOverrides,
  }) {
    const { panel_id: panelId, ...rest } = params;
    return Request.put(`bkvision${this.module}/panel/platform/${panelId}/`, {
      params: {
        panel_id: panelId,
        ...rest,
      },
    });
  }
  // 删除平台级报表
  deletePlatformPanel(params: { panel_id: string }) {
    return Request.delete(`bkvision${this.module}/panel/platform/${params.panel_id}/`, {
      params,
    });
  }
  // 启用/停用平台级报表
  publishPlatformPanel(params: {
    panel_id: string,
    status?: 'published' | 'unpublished',
  }) {
    return Request.post(`bkvision${this.module}/panel/platform/${params.panel_id}/publish/`, {
      params,
    });
  }
  /**
   * 获取报表详情（按当前 scope 返回单份 default_value_override）
   * GET /bkvision/api/v1/panel/{panel_id}/
   * 默认 catchError：调用方自行兜底，避免未实现/无覆盖时弹全局错误
   */
  fetchPanelDetail(params: {
    panel_id: string,
    scope_type: string,
    scope_id?: string,
  }) {
    const { panel_id: panelId, ...query } = params;
    return Request.get<PanelDetail>(`bkvision${this.module}/panel/${panelId}/`, {
      params: {
        panel_id: panelId,
        ...query,
      },
      payload: {
        catchError: true,
      },
    });
  }
}
export default new PanelManage();

