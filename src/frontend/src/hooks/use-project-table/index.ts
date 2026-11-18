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
import axios from 'axios';
import { onBeforeUnmount, reactive } from 'vue';

import StrategyManageService from '@service/strategy-manage';

import { createKeyedTableLoader, type TableLoadState } from '@utils/assist/keyed-table-loader';

export interface ProjectTableNode {
  label: string;
  value: string;
  namespace?: string;
  node_type?: 'project' | 'table';
  table_id?: string;
  leaf?: boolean;
  loaded?: boolean;
  disabled?: boolean;
  children?: ProjectTableNode[];
}

const readConfig = () => {
  try {
    return JSON.parse(sessionStorage.getItem('BK_AUDIT_CONFIG') || '{}');
  } catch {
    return {};
  }
};

/** 只认首页能力开关；缺省与 false 完整保留旧树。 */
export const isProjectTableLazyEnabled = () => readConfig()?.feature_toggle?.bkbase_project_rt_lazy_load === true;

export const isProjectTableType = (tableType: string) => (
  isProjectTableLazyEnabled() && ['BizRt', 'BuildIn'].includes(tableType)
);

/** 项目和 RT 使用不同 UI key，namespace 仅作导航，不会进入提交 RT。 */
export const encodeProjectNamespace = (tableType: string, namespace: string) => `__project__${tableType}__${namespace}`;

/** 每个选择器独立缓存；请求键包含审计空间、场景、类型和真实 namespace。 */
export default () => {
  const states = reactive<Record<string, TableLoadState<ProjectTableNode[]>>>({});
  const loader = createKeyedTableLoader(states, () => axios.CancelToken.source());
  const key = (kind: string, tableType: string, sceneId?: string | number | null, namespace = '') => JSON.stringify([
    'project-rt-v4', readConfig()?.tenant_config?.BK_TENANT_ID, readConfig()?.username,
    window.PROJECT_CONFIG.AJAX_URL_PREFIX, window.PROJECT_CONFIG.NAMESPACE,
    kind, tableType, String(sceneId || ''), namespace,
  ]);
  const loadDirectory = (tableType: string, sceneId?: string | number | null) => loader.load(
    key('directory', tableType, sceneId),
    cancelTokenSource => StrategyManageService.fetchTableProjects({
      table_type: tableType,
      ...(sceneId ? { scene_id: String(sceneId) } : {}),
    }, { silent: true, catchError: true, cancelTokenSource }),
  );
  const loadProject = (tableType: string, namespace: string, sceneId?: string | number | null) => loader.load(
    key('project', tableType, sceneId, namespace),
    cancelTokenSource => StrategyManageService.fetchProjectTables({
      table_type: tableType,
      bkbase_namespace: namespace,
      ...(sceneId ? { scene_id: String(sceneId) } : {}),
    }, { silent: true, catchError: true, cancelTokenSource }),
  );
  const loadMineDirectory = (sceneId?: string | number | null) => loader.load(
    key('directory', 'MineBizRt', sceneId),
    cancelTokenSource => StrategyManageService.fetchTable({
      table_type: 'MineBizRt', ...(sceneId ? { scene_id: String(sceneId) } : {}),
    }, { silent: true, catchError: true, cancelTokenSource }),
  );
  const loadMineTables = (bizId: string, sceneId?: string | number | null) => loader.load(
    key('business', 'MineBizRt', sceneId, bizId),
    cancelTokenSource => StrategyManageService.fetchTable({
      table_type: 'MineBizRt', bk_biz_id: bizId,
      ...(sceneId ? { scene_id: String(sceneId) } : {}),
    }, { silent: true, catchError: true, cancelTokenSource }),
  );
  onBeforeUnmount(loader.cancel);
  return { states, key, loadDirectory, loadProject, loadMineDirectory, loadMineTables, cancel: loader.cancel };
};
