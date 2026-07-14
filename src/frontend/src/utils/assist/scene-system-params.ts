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

type SceneSystemParams = {
  scope_id: string;
  scope_type: string;
};

/**
 * 从 URL query 解析场景/系统参数
 * 优先级：scene_id > scope_id + scope_type
 */
const getParamsFromUrl = (): SceneSystemParams | null => {
  try {
    const urlParams = new URLSearchParams(window.location.search);
    const urlSceneId = urlParams.get('scene_id');
    const urlScopeId = urlParams.get('scope_id');
    const urlScopeType = urlParams.get('scope_type') || '';

    // scene_id 优先级最高（深链 / 产生风险单等入口的临时切换）
    if (urlSceneId) {
      if (urlSceneId === 'allSecen') {
        return { scope_id: '', scope_type: 'cross_scene' };
      }
      if (urlSceneId === 'allSystem') {
        return { scope_id: '', scope_type: 'cross_system' };
      }
      return {
        scope_id: urlSceneId,
        scope_type: urlScopeType || 'scene',
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
  } catch {
    // URL 解析失败，忽略
  }
  return null;
};

/**
 * 从 localStorage 解析场景/系统参数
 */
const getParamsFromStorage = (): SceneSystemParams | null => {
  try {
    const scopeInfo = JSON.parse(localStorage.getItem('scene-system-selector:selected') || '{}');
    if (!scopeInfo?.id) {
      return null;
    }
    if (scopeInfo.id === 'allSecen') {
      return {
        scope_id: '',
        scope_type: 'cross_scene',
      };
    }
    if (scopeInfo.id === 'allSystem') {
      return {
        scope_id: '',
        scope_type: 'cross_system',
      };
    }
    return {
      scope_id: scopeInfo.id,
      scope_type: scopeInfo.type === 'scene' ? 'scene' : 'system',
    };
  } catch {
    return null;
  }
};

/**
 * @desc 获取场景系统参数
 * 优先级：URL参数(scene_id/scope_id) > localStorage > 默认空值
 * 深链进入时须以 URL 为准，才能正确临时切换场景（同时由选择器回写 localStorage）
 */
export const getSceneSystemParams = (): SceneSystemParams => {
  const fromUrl = getParamsFromUrl();
  if (fromUrl) {
    return fromUrl;
  }

  const fromStorage = getParamsFromStorage();
  if (fromStorage) {
    return fromStorage;
  }

  return {
    scope_id: '',
    scope_type: '',
  };
};
