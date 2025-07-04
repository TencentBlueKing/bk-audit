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
import ToolsSquare from '../source/tools-square';

export default {
  /**
   * @desc 工具标签列表
   * @param { Object } params
   */
  fetchToolsTagsList() {
    return ToolsSquare.getToolsTagsList().then(({ data }) => data);
  },
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
  }) {
    return ToolsSquare.getToolsList(params).then(({ data }) =>  ({
      ...data,
      results: data.results,
    }));
  },
  /**
   * @desc 工具详情
   * @param { Object } params
   */
  fetchToolsDetail(params: {
    uid: string,
  }) {
    return ToolsSquare.getToolsDetail(params).then(({ data }) =>  ({
      ...data,
    }));
  },
};
