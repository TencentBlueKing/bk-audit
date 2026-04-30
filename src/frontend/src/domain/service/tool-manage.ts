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
import ToolInfo from '../model/tool/tool-info';
import ToolManageSources from '../source/tool-manage';

export default  {
  /**
   * @desc 工具列表
   * @param { Object } params
   */
  fetchToolsList(params: {
      offset?: number
      limit?: number
      keyword?: string,
      page: number,
      page_size: number
      tags?: string[],
      scope_type?: string,
      scope_id?: string,
      binding_type?: string,
      status?: string,
    }) {
    return ToolManageSources.getToolsList(params).then(({ data }) =>  ({
      ...data,
      results: data.results.map((item: any) => new ToolInfo(item)),
    }));
  },
  /**
   * @desc tag列表
   * @param { Object } params
   */
  fetchToolTags(params?: {
      scope_type?: string,
      scope_id?: string,
    }) {
    return ToolManageSources.getToolTags(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 创建场景级工具
   * @param { Object } params
   */
  createSceneTool(params: Record<string, any>) {
    return ToolManageSources.createSceneTool(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 解析sql
   * @param { Object } params
   */
  parseSql(params: Record<string, any>) {
    return ToolManageSources.parseSql(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 编辑模式解析sql
   * @param { Object } params
   */
  editModelParseSql(params: Record<string, any>) {
    return ToolManageSources.editModelParseSql(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 工具详情
   * @param { Object } params
   */
  fetchToolsDetail(params: {
      uid: string,
    }) {
    return ToolManageSources.getToolsDetail(params).then(({ data }) =>  data);
  },
  /**
   * @desc 编辑场景级工具
   * @param { Object } params
   */
  updateSceneTool(params: Record<string, any>) {
    return ToolManageSources.updateSceneTool(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取全部工具
   */
  fetchAllTools(params?: {
    scope_type?: string,
    scope_id?: string,
  }) {
    return ToolManageSources.getAllTools(params)
      .then(({ data }) => data);
  },
  /**
     * @desc 工具执行
     * @param { Object } params
     */
  fetchToolsExecute(params: {
      uid: string,
      params: Record<string, any>,
    }) {
    return ToolManageSources.getToolsExecute(params).then(({ data }) =>  ({
      ...data,
    }));
  },
  /**
     * @desc 工具调试
     * @param { Object } params
     */
  fetchToolsDebug(params: {
      tool_type: string,
      config: Record<string, any>,
      params: Record<string, any>,
    }) {
    return ToolManageSources.getToolsDebug(params).then(({ data }) =>  ({
      ...data,
    }));
  },
  /**
     * @desc 删除场景级工具
     * @param { Object } params
     */
  fetchDeleteSceneTool(params: {
      uid: string,
      scene_id: number,
    }) {
    return ToolManageSources.deleteSceneTool(params).then(({ data }) =>  ({
      ...data,
    }));
  },
  /**
     * @desc 上架/下架平台级场景工具
     * @param { Object } params
     */
  publishPlatformTool(params: {
      uid: string,
      scene_id: number,
    }) {
    return ToolManageSources.publishPlatformTool(params).then(({ data }) => data);
  },
  /**
     * @desc 收藏/取消收藏工具
     * @param { Object } params
     */
  toggleFavorite(params: {
      uid: string,
      favorite: boolean,
    }) {
    return ToolManageSources.toggleFavorite(params).then(({ data }) =>  data);
  },
  /**
     * @desc 获取图表列表
     * @param { Object }
     */
  fetchChartLists() {
    return ToolManageSources.getChartLists().then(({ data }) => data)
      .catch(() => 'error');
  },
  /**
     * @desc 获取报表列表
     * @param { Object } params
     */
  fetchReportLists(params: {
      share_uid: string,
    }) {
    return ToolManageSources.getReportLists(params).then(({ data }) => data);
  },

};
