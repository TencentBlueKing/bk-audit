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
import ToolManageSources from '../source/tool-manage';

export default  {
  /**
   * @desc 版本列表
   */
  fetchToolTags() {
    return ToolManageSources.getToolTags()
      .then(({ data }) => data);
  },
  /**
   * @desc 新建工具
   * @param { Object } params
   */
  createTool(params: Record<string, any>) {
    return ToolManageSources.createTool(params)
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
     * @desc 工具详情
     * @param { Object } params
     */
  fetchToolsDetail(params: {
      uid: string,
    }) {
    return ToolManageSources.getToolsDetail(params).then(({ data }) =>  data);
  },
  /**
   * @desc 编辑工具
   * @param { Object } params
   */
  updateTool(params: Record<string, any>) {
    return ToolManageSources.updateTool(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取全部工具
   */
  fetchAllTools() {
    return ToolManageSources.getAllTools()
      .then(({ data }) => data);
  },
};
