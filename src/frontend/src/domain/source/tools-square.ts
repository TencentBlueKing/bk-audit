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


import type  ToolDetail from '@model/tool/tool-detail';
import type toolInfo from '@model/tools-square/tools-square';

import Request from '@utils/request';
import { processedParams } from '@utils/request/lib/utils';

import ModuleBase from './module-base';

import type { IRequestResponsePaginationData } from '@/utils/request';

class ToolsSquare extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1/namespace/default';
  }
  // 获取工具标签列表
  getToolsTagsList() {
    return Request.get<Array<{
      tag_id: string,
      tag_name: string,
      tool_count: number,
    }>>(`${this.path}/tool/tags/`);
  }
  // 获取工具列表
  getToolsList(params: {
  offset?: number
  limit?: number
  keyword?: string,
  page: number,
  page_size: number
  tags?: string[],
}) {
    return Request.get<IRequestResponsePaginationData<toolInfo>>(`${this.path}/tool/?${processedParams(params).toString()}`);
  }
  // 获取工具详情
  getToolsDetail(params: {
    uid: string,
  }) {
    return Request.get<ToolDetail>(`${this.path}/tool/${params.uid}/`);
  }
  // 工具执行
  getToolsExecute(params: {
    uid: string,
    params: Record<string, any>,
  }) {
    return Request.post(`${this.path}/tool/${params.uid}/execute/`, { params });
  }

  // 工具删除
  deleteTool(params: {
    uid: string,
  }) {
    return Request.delete(`${this.path}/tool/${params.uid}/`, { params });
  }
}

export default new ToolsSquare();
