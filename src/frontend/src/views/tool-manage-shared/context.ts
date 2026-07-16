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
import { inject, type InjectionKey, provide } from 'vue';

import MetaManageService from '@service/meta-manage';
import ToolManageService from '@service/tool-manage';

import { getSceneSystemParams, getToolListScopeParams } from '@/utils/assist/scene-system-params';

export type ToolManageScope = 'platform' | 'scene';

export interface ToolManageContext {
  scope: ToolManageScope;
  /** 工具列表页路由名 */
  listRouteName: string;
  /** 新建工具路由名 */
  createRouteName: string;
  /** 编辑工具路由名 */
  editRouteName: string;
  /** 获取可用于下钻的工具列表 */
  fetchTools: (params?: Record<string, any>) => Promise<any>;
  /** 工具列表默认请求参数 */
  getToolsDefaultParams: () => Record<string, any>;
  /** 获取标签列表 */
  fetchTags: (params?: Record<string, any>) => Promise<any>;
  /** 标签请求成功后是否需要刷新工具列表（场景侧需要） */
  refreshToolsAfterTags: boolean;
  /** 删除工具 */
  deleteTool: (uid: string) => Promise<any>;
  /** 启停/上下架 */
  toggleToolStatus: (params: {
    uid: string;
    enable: boolean;
  }) => Promise<any>;
  /** 启停文案：上架/下架 vs 启用/停用 */
  statusActionLabels: {
    enableTitle: string;
    disableTitle: string;
    enableSubTitle: string;
    disableSubTitle: string;
    enableConfirm: string;
    disableConfirm: string;
    enableSuccess: string;
    disableSuccess: string;
  };
}

export const TOOL_MANAGE_CONTEXT_KEY: InjectionKey<ToolManageContext> = Symbol('toolManageContext');

const platformStatusLabels: ToolManageContext['statusActionLabels'] = {
  enableTitle: '确认上架该工具？',
  disableTitle: '确认下架该工具？',
  enableSubTitle: '上架后，该工具将在「工具广场」中展示',
  disableSubTitle: '下架后，该工具将从「工具广场」中隐藏',
  enableConfirm: '上架',
  disableConfirm: '下架',
  enableSuccess: '上架成功',
  disableSuccess: '下架成功',
};

const sceneStatusLabels: ToolManageContext['statusActionLabels'] = {
  enableTitle: '确认启用该工具？',
  disableTitle: '确认停用该工具？',
  enableSubTitle: '启用后，该工具将在「工具广场」中展示',
  disableSubTitle: '停用后，该工具将从「工具广场」中隐藏',
  enableConfirm: '启用',
  disableConfirm: '停用',
  enableSuccess: '启用成功',
  disableSuccess: '停用成功',
};

export function createPlatformToolManageContext(): ToolManageContext {
  return {
    scope: 'platform',
    listRouteName: 'platformToolConfig',
    createRouteName: 'platformToolCreate',
    editRouteName: 'platformToolEdit',
    fetchTools: params => ToolManageService.fetchToolsList(params as any),
    getToolsDefaultParams: () => ({ status: ['published'] }),
    fetchTags: () => MetaManageService.fetchTags(),
    refreshToolsAfterTags: false,
    deleteTool: uid => ToolManageService.deletePlatformTool(uid),
    toggleToolStatus: ({ uid, enable }) => ToolManageService.publishPlatformToolStatus({
      id: uid,
      status: enable ? 'published' : 'unpublished',
    }),
    statusActionLabels: platformStatusLabels,
  };
}

export function createSceneToolManageContext(): ToolManageContext {
  return {
    scope: 'scene',
    listRouteName: 'sceneToolManege',
    createRouteName: 'sceneToolCreate',
    editRouteName: 'sceneToolEdit',
    fetchTools: params => ToolManageService.fetchAllTools(params as any),
    getToolsDefaultParams: () => getToolListScopeParams({ status: 'published' }),
    fetchTags: params => ToolManageService.fetchToolTags(params as any),
    refreshToolsAfterTags: true,
    deleteTool: (uid) => {
      const scopeParams = getSceneSystemParams();
      return ToolManageService.fetchDeleteSceneTool({
        uid,
        scene_id: Number(scopeParams.scope_id) || 0,
      });
    },
    toggleToolStatus: ({ uid }) => {
      const scopeParams = getSceneSystemParams();
      return ToolManageService.publishPlatformTool({
        uid,
        scene_id: Number(scopeParams.scope_id) || 0,
      });
    },
    statusActionLabels: sceneStatusLabels,
  };
}

export function provideToolManageContext(ctx: ToolManageContext) {
  provide(TOOL_MANAGE_CONTEXT_KEY, ctx);
}

export function useToolManageContext(): ToolManageContext {
  const ctx = inject(TOOL_MANAGE_CONTEXT_KEY);
  if (!ctx) {
    // 兜底：未 provide 时按平台行为，避免局部复用崩溃
    return createPlatformToolManageContext();
  }
  return ctx;
}
