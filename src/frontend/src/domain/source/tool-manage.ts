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
import type ParseSqlModel from '@model/tool/parse-sql';
import type ToolDetailModel from '@model/tool/tool-detail';
import type ToolInfoModel from '@model/tool/tool-info';

import Request from '@utils/request';
import { processedParams } from '@utils/request/lib/utils';

import ModuleBase from './module-base';

import type { IRequestResponsePaginationData } from '@/utils/request';


class ToolManage extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1';
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
    return Request.get<IRequestResponsePaginationData<ToolInfoModel>>(`${this.path}/tool/?${processedParams(params).toString()}`);
  }
  // 获取工具tag列表
  getToolTags() {
    return Request.get<Array<{
      tag_id: string;
      tag_name: string;
      tool_count: number,
    }>>(`${this.path}/tool/tags/`);
  }
  // 新建工具
  createTool(params: Record<string, any>) {
    return Request.post(`${this.path}/tool/`, {
      params,
    });
  }
  // 解析sql
  parseSql(params: Record<string, any>) {
    return Request.post<ParseSqlModel>(`${this.path}/tool/sql_analyse/`, {
      params,
    });
  }
  // 编辑模式解析sql
  editModelParseSql(params: Record<string, any>) {
    return Request.post<ParseSqlModel>(`${this.path}/tool/${params.uid}/sql_analyse_with_tool/`, {
      params,
    });
  }
  // 获取工具详情
  getToolsDetail(params: {
    uid: string,
  }) {
    return Request.get<ToolDetailModel>(`${this.path}/tool/${params.uid}/`);
  }
  // 编辑工具
  updateTool(params: Record<string, any>) {
    return Request.put(`${this.path}/tool/${params.uid}/`, {
      params,
    });
  }
  // 获取全部工具
  getAllTools() {
    return Request.get<Array<ToolDetailModel>>(`${this.path}/tool/all/`);
  }
  // 工具执行
  getToolsExecute(params: {
    uid: string,
    params: Record<string, any>,
  }) {
    return Request.post(`${this.path}/tool/${params.uid}/execute/`, { params });
  }
  // 工具调试
  getToolsDebug(params: {
    tool_type: string,
    config: Record<string, any>,
    params: Record<string, any>,
  }) {
    return Request.post(`${this.path}/tool/tool_execute_debug/`, { params });
  }
  // 工具删除
  deleteTool(params: {
    uid: string,
  }) {
    return Request.delete(`${this.path}/tool/${params.uid}/`, { params });
  }
  // 收藏/取消收藏工具
  toggleFavorite(params: {
    uid: string,
    favorite: boolean,
  }) {
    return Request.put(`${this.path}/tool/${params.uid}/favorite/`, {
      params: {
        favorite: params.favorite,
      },
    });
  }
  // 获取图表列表
  getChartLists() {
    return Request.get<Array<{
      uid: string;
      name: string;
      share: Array<{
        uid: string;
        name: string;
      }>,
    }>>(`bkvision${this.module}/share/share_list/`);
  }
  // 获取报表列表
  getReportLists(params: {
    share_uid: string,
  }) {
    return Request.get(`bkvision${this.module}/share/share_detail/?share_uid=${params.share_uid}`);
  }
}

export default new ToolManage();
