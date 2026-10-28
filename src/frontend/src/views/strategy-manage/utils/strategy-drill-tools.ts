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
import type { RouteLocationNormalizedLoaded } from 'vue-router';

import ToolManageService from '@service/tool-manage';

import type ToolDetailModel from '@model/tool/tool-detail';

import { getStrategyBindingScope, getStrategySystemScopeParams } from './strategy-routes';

type StrategyRoute = Pick<RouteLocationNormalizedLoaded, 'name' | 'meta'>;

type ToolTagItem = {
  tag_id: string;
  tag_name: string;
  tool_count: number;
};

/**
 * 策略字段下钻可选工具：
 * - 全局策略：全部已启用的全局工具，不受工具可见范围限制
 * - 审计策略：当前场景可见的已启用工具
 */
export const fetchStrategyDrillTools = (route: StrategyRoute): Promise<Array<ToolDetailModel>> => {
  if (getStrategyBindingScope(route).isPlatform) {
    return ToolManageService.fetchToolsList({ status: ['published'] }) as unknown as Promise<Array<ToolDetailModel>>;
  }
  return ToolManageService.fetchAllTools({
    ...getStrategySystemScopeParams(route),
    status: ['published'],
  });
};

/** 全局策略的下钻工具平铺展示，不需要标签分组 */
export const fetchStrategyDrillToolTags = (route: StrategyRoute): Promise<Array<ToolTagItem>> => {
  if (getStrategyBindingScope(route).isPlatform) {
    return Promise.resolve([]);
  }
  return ToolManageService.fetchToolTags({
    ...getStrategySystemScopeParams(route),
    status: ['published'],
  });
};
