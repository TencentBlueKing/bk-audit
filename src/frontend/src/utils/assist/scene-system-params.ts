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

/**
 * @desc 获取场景系统参数
 * 优先级：localStorage > URL参数(scene_id/scope_id) > 默认空值
 */
export const getSceneSystemParams = ()  => {
  const scopeInfo = JSON.parse(localStorage.getItem('scene-system-selector:selected') || '{}');

  // 如果 localStorage 没有有效值，尝试从 URL 参数获取（防止初始化竞态）
  if (!scopeInfo?.id) {
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const urlSceneId = urlParams.get('scene_id');
      const urlScopeId = urlParams.get('scope_id');
      const urlScopeType = urlParams.get('scope_type') || '';
      // ⚠️ scene_id 优先级最高（直接从链接进入的场景ID），但要结合 scope_type 判断类型
      if (urlSceneId) {
        if (urlSceneId === 'allSecen') {
          return { scope_id: '', scope_type: 'cross_scene' };
        }
        if (urlSceneId === 'allSystem') {
          return { scope_id: '', scope_type: 'cross_system' };
        }
        // 有明确的 scope_type 时用它，否则默认为 scene
        const finalType = urlScopeType || 'scene';
        return {
          scope_id: urlSceneId,
          scope_type: finalType,
        };
      }
      if (urlScopeId && urlScopeType === 'scene') {
        return {
          scope_id: urlScopeId,
          scope_type: 'scene',
        };
      }
      if (urlScopeId && urlScopeType === 'system') {
        return {
          scope_id: urlScopeId,
          scope_type: 'system',
        };
      }
      // cross_scene / cross_system（无具体 scope_id）
      if (!urlScopeId && urlScopeType === 'cross_scene') {
        return {
          scope_id: '',
          scope_type: 'cross_scene',
        };
      }
      if (!urlScopeId && urlScopeType === 'cross_system') {
        return {
          scope_id: '',
          scope_type: 'cross_system',
        };
      }
    } catch (e) {
      // URL 解析失败，忽略
    }
    // 空值 返回空
    return {
      scope_id: '',
      scope_type: '',
    };
  }
  if (scopeInfo.id === 'allSecen') { // 所有场景
    return {
      scope_id: '',
      scope_type: 'cross_scene',
    };
  } if (scopeInfo.id === 'allSystem') { // 所有系统
    return {
      scope_id: '',
      scope_type: 'cross_system',
    };
  } // 指定场景 指定系统

  return {
    scope_id: scopeInfo.id,
    scope_type: scopeInfo.type === 'scene' ? 'scene' : 'system',
  };
};

export interface SceneSystemScopeParams {
  scope_type?: string;
  scope_id?: string;
}

export interface ToolDetailScopeQuery {
  scene_id?: number;
  system_id?: string;
}

/** 跨场景/跨系统时工具级的默认值覆盖上下文 */
export type ToolDetailOverrideContext = ToolDetailScopeQuery;

/**
 * @desc 从工具 visibility 推断覆盖上下文（仅单场景/单系统时兜底）
 */
export const resolveToolOverrideContextFromTool = (
  tool: { visibility?: { scene_ids?: number[]; system_ids?: Array<string | number> } },
  scopeType?: string,
): ToolDetailOverrideContext => {
  if (scopeType === 'cross_scene') {
    const sceneIds = (tool.visibility?.scene_ids || []).filter(id => id > 0);
    if (sceneIds.length === 1) {
      return { scene_id: sceneIds[0] };
    }
  }
  if (scopeType === 'cross_system') {
    const systemIds = tool.visibility?.system_ids || [];
    if (systemIds.length === 1) {
      return { system_id: String(systemIds[0]) };
    }
  }
  return {};
};

/**
 * @desc 根据可见范围参数组装工具详情请求的 scene_id / system_id
 * 用于后端按场景/系统覆盖平台工具的可见范围默认值
 */
export const getToolDetailScopeQuery = (
  scopeParams?: SceneSystemScopeParams,
  overrideContext?: ToolDetailOverrideContext,
): ToolDetailScopeQuery => {
  const params = resolveToolDetailScopeParams(scopeParams);
  if (params.scope_type === 'scene' && params.scope_id) {
    const sceneId = Number(params.scope_id);
    if (!Number.isNaN(sceneId)) {
      return { scene_id: sceneId };
    }
  }
  if (params.scope_type === 'system' && params.scope_id) {
    return { system_id: String(params.scope_id) };
  }
  if (overrideContext?.scene_id !== undefined) {
    return { scene_id: overrideContext.scene_id };
  }
  if (overrideContext?.system_id) {
    return { system_id: overrideContext.system_id };
  }
  return {};
};

/**
 * @desc 解析工具详情请求用的可见范围（props 未就绪时回退 URL/localStorage）
 */
export const resolveToolDetailScopeParams = (scopeParams?: SceneSystemScopeParams): SceneSystemScopeParams => {
  const propsScope = scopeParams ?? {};
  if (
    (propsScope.scope_type === 'scene' || propsScope.scope_type === 'system')
    && propsScope.scope_id
  ) {
    return propsScope;
  }
  const globalScope = getSceneSystemParams();
  if (
    globalScope.scope_id
    && (globalScope.scope_type === 'scene' || globalScope.scope_type === 'system')
  ) {
    return globalScope;
  }
  if (propsScope.scope_type) {
    return propsScope;
  }
  return globalScope;
};

/** 工具列表/标签接口所需的可见范围参数（scope_type 为后端必填） */
export const getToolListScopeParams = (extra?: {
  status?: string | string[];
}) => {
  const { scope_type: scopeType, scope_id: scopeId } = getSceneSystemParams();
  return {
    scope_type: scopeType || 'cross_scene',
    ...(scopeId ? { scope_id: scopeId } : {}),
    ...extra,
  };
};

/** 场景/系统维度需等 scope_id 就绪后再请求工具详情，避免先发无参请求 */
export const isToolDetailScopeReady = (scopeParams?: SceneSystemScopeParams): boolean => {
  const scope = resolveToolDetailScopeParams(scopeParams);
  if (!scope.scope_type) return false;
  if (scope.scope_type === 'scene' || scope.scope_type === 'system') {
    return !!scope.scope_id;
  }
  return true;
};
