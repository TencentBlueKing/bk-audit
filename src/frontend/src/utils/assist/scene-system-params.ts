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
 * 优先级：sessionStorage > URL参数(scene_id/scope_id) > 默认空值
 */
export const getSceneSystemParams = ()  => {
  const scopeInfo = JSON.parse(sessionStorage.getItem('scene-system-selector:selected') || '{}');

  // 如果 sessionStorage 没有有效值，尝试从 URL 参数获取（防止初始化竞态）
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
