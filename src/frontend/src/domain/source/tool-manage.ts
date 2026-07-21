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
import type ParseSqlModel from '@model/tool/parse-sql';
import type ToolDetailModel from '@model/tool/tool-detail';
import type ToolInfoModel from '@model/tool/tool-info';
import type {
  CreatePlatformToolPayload,
  EditModelParseSqlParams,
  ParseSqlParams,
  SceneToolWritePayload,
  ToolDebugPayload,
  ToolExecutePayload,
  UpdatePlatformToolPayload,
  UpdateSceneToolPayload,
} from '@model/tool/tool-manage-types';

import Request from '@utils/request';
import { processedParams } from '@utils/request/lib/utils';

import ModuleBase from './module-base';

import { getSceneSystemParams } from '@/utils/assist/scene-system-params';


class ToolManage extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1';
  }
  // 获取工具列表（不再分页，直接返回数组）
  getToolsList(params: {
    keyword?: string,
    scope_type?: string,
    scope_id?: string,
    binding_type?: string,
    status?: string[],
    sort?: string[],
    my_created?: boolean,
    recent_used?: boolean,
  }) {
    return Request.get<Array<ToolInfoModel>>(`${this.path}/tool/?${processedParams(params).toString()}`);
  }
  // 获取工具tag列表
  getToolTags(params?: {
    scope_type?: string,
    scope_id?: string,
    status?: string[],
  }) {
    const sceneParams = getSceneSystemParams();
    const mergedParams = {
      scope_type: sceneParams.scope_type,
      scope_id: sceneParams.scope_id,
      ...params,
    };
    const query = `?${processedParams(mergedParams).toString()}`;
    return Request.get<Array<{
      tag_id: string;
      tag_name: string;
      tool_count: number,
    }>>(`${this.path}/tool/tags/${query}`);
  }
  // 创建场景级工具
  createSceneTool(params: SceneToolWritePayload) {
    const sceneId = getSceneSystemParams().scope_id;
    return Request.post(`${this.path}/tool/scene/?scene_id=${sceneId}`, {
      params: {
        ...params,
        scene_id: sceneId,
      },
    });
  }
  // 解析sql
  parseSql(params: ParseSqlParams) {
    return Request.post<ParseSqlModel>(`${this.path}/tool/sql_analyse/`, {
      params,
    });
  }
  // 编辑模式解析sql
  editModelParseSql(params: EditModelParseSqlParams) {
    return Request.post<ParseSqlModel>(`${this.path}/tool/${params.uid}/sql_analyse_with_tool/`, {
      params,
    });
  }
  // 获取工具详情
  getToolsDetail(params: {
    uid: string,
    scene_id?: number,
    system_id?: string,
  }) {
    const { uid, ...queryParams } = params;
    const query = Object.keys(queryParams).length > 0
      ? `?${processedParams(queryParams).toString()}`
      : '';
    return Request.get<ToolDetailModel>(`${this.path}/tool/${uid}/${query}`);
  }
  // 编辑工具
  updateSceneTool(params: UpdateSceneToolPayload) {
    const sceneId = getSceneSystemParams().scope_id;
    return Request.put(`${this.path}/tool/scene/${params.uid}/?scene_id=${sceneId}`, {
      params: {
        ...params,
        scene_id: sceneId,
      },
    });
  }
  // 获取全部工具
  getAllTools(params?: {
    scope_type?: string,
    scope_id?: string,
    status?: string[],
    namespace?: string,
  }) {
    // scope_type 为后端必填；无参/空参调用时回退当前场景/系统，避免 /tool/all/? 空查询 500
    const sceneParams = getSceneSystemParams();
    const { scope_type: paramScopeType, scope_id: paramScopeId, ...rest } = params || {};
    const scopeType = paramScopeType || sceneParams.scope_type || 'cross_scene';
    const scopeId = paramScopeId || sceneParams.scope_id;
    const mergedParams = {
      ...rest,
      scope_type: scopeType,
      ...(scopeId ? { scope_id: scopeId } : {}),
    };
    const query = `?${processedParams(mergedParams).toString()}`;
    return Request.get<Array<ToolDetailModel>>(`${this.path}/tool/all/${query}`);
  }
  // 工具执行
  getToolsExecute(params: ToolExecutePayload) {
    return Request.post(`${this.path}/tool/${params.uid}/execute/`, { params });
  }
  // 工具调试
  getToolsDebug(params: ToolDebugPayload) {
    return Request.post(`${this.path}/tool/tool_execute_debug/`, { params });
  }
  // 删除场景级工具
  deleteSceneTool(params: {
    uid: string,
    scene_id: number,
  }) {
    return Request.delete(`${this.path}/tool/scene/${params.uid}/`, { params });
  }
  // 上架/下架场景级工具
  publishPlatformTool(params: {
    uid: string,
    scene_id: number,
  }) {
    return Request.post(`${this.path}/tool/scene/${params.uid}/publish/`, {
      params: {
        uid: params.uid,
        scene_id: params.scene_id,
      },
    });
  }
  // 编辑平台级工具
  updatePlatformTool(params: UpdatePlatformToolPayload) {
    return Request.put(`${this.path}/tool/platform/${params.uid}/`, {
      params: {
        ...params,
      },
    });
  }
  // 创建平台级工具
  createPlatformTool(params: CreatePlatformToolPayload) {
    return Request.post(`${this.path}/tool/platform/`, {
      params,
    });
  }
  // 删除平台级工具
  deletePlatformTool(params: { uid: string }) {
    return Request.delete(`${this.path}/tool/platform/${params.uid}/`);
  }
  // 上架/下架平台级工具
  publishPlatformToolStatus(params: { id: string, status: 'published' | 'unpublished' }) {
    return Request.post(`${this.path}/tool/platform/${params.id}/publish/`, {
      params: {
        id: params.id,
        status: params.status,
      },
    });
  }
  // 收藏/取消收藏工具
  toggleFavorite(params: {
    uid: string,
    favorite: boolean,
  }) {
    return Request.put(`${this.path}/tool/${params.uid}/favorite/`, {
      params: {
        favorite: params.favorite,
      },
    });
  }
  // 获取图表列表
  getChartLists() {
    return Request.get<Array<{
      uid: string;
      name: string;
      share: Array<{
        uid: string;
        name: string;
      }>,
    }>>(`bkvision${this.module}/share/share_list/`);
  }
  // 获取报表列表
  getReportLists(params: {
    share_uid: string,
  }) {
    return Request.get(`bkvision${this.module}/share/share_detail/?share_uid=${params.share_uid}`);
  }
}

export default new ToolManage();
