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
import type SearchModel from '@model/es-query/search';
import type AiopsDetailModel from '@model/strategy/aiops-detail';
import type AiopsPlanModel from '@model/strategy/aiops-plan';
import type CommonDataModel from '@model/strategy/common-data';
import type RtMetaModel from '@model/strategy/rt-meta';
import type StrategyModel from '@model/strategy/strategy';
import type StrategyFieldEvent from '@model/strategy/strategy-field-event';
// import type StrategyFieldModel from '@model/strategy/strategy-field';
// import type StrategyConfigListModel from '@model/strategy/strategy-config-list';
import type StrategyTag from '@model/strategy/strategy-tag';

import Request, {
  type IRequestPayload,
  type IRequestResponsePaginationData,
} from '@utils/request';

import ModuleBase from './module-base';


class Strategy extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1/';
  }
  // 策略列表
  getStrategyList(params: {
    label?: string,
    name?: string,
    page: number,
    page_size: number
  }, payload = {} as IRequestPayload) {
    return Request.get<IRequestResponsePaginationData<StrategyModel>>(`${this.path}/strategy/`, {
      params,
      payload,
    });
  }
  // 新建策略
  saveStrategy(params: Record<string, any>) {
    return Request.post(`${this.path}/strategy/`, {
      params,
    });
  }
  // 获取所有策略下拉列表
  getAllStrategyList() {
    return Request.get<Array<{
      label: string,
      value: number
    }>>(`${this.path}/strategy/all/`);
  }
  // 获取权限下所有策略下拉列表
  getScopedStrategyList(params: Record<string, any>) {
    return Request.get<Array<{
      label: string,
      value: number
    }>>(`${this.module}risks/strategies/`, { params });
  }
  // 获取告警常量
  getStrategyCommon(payload = {} as IRequestPayload) {
    return Request.get<CommonDataModel>(`${this.path}/strategy/common/`, {
      payload,
    });
  }

  // 重试策略
  retryStrategy(params: {
    strategy_id: number
  }) {
    return Request.put(`${this.path}/strategy/${params.strategy_id}/retry/`, {
      params,
    });
  }

  // 获取处理中的策略状态
  getStrategyStatus(params: {
    strategy_ids: string,
  }) {
    return Request.get<Record<string, {
      status: string,
      status_msg: string,
    }>>(`${this.path}/strategy/status/`, {
      params,
    });
  }

  // 更新策略
  updateStrategy(params: StrategyModel) {
    return Request.put(`${this.path}/strategy/${params.strategy_id}/`, {
      params,
    });
  }
  // 删除策略
  deleteStrategy(params: {
    id: number
  }) {
    return Request.delete(`${this.path}/strategy/${params.id}/`, {});
  }

  // 启停
  switchStrategy(params: {
    strategy_id: number
    toggle: boolean,
  }) {
    return Request.post(`${this.path}/strategy/${params.strategy_id}/toggle/`, {
      params,
    });
  }
  // 获取策略字段
  getStrategyFields(params: {
    system_id: string;
    action_id: string
  }) {
    return Request.get<Array<{
      description: string;
      field_name: string;
      field_type: string;
      is_dimension: boolean;
    }>>(`${this.path}/strategy_fields/`, {
      params,
    });
  }

  // 获取变量值
  getStrategyFieldValue(params: {
    field_name: string
  }) {
    return Request.get<Array<{
      label: string,
      value: string,
      children?: Array<{
        label: string,
        value: string,
      }>
    }>>(`${this.path}/strategy_fields/value/`, {
      params,
    });
  }
  // 获取表格id
  getTable(params: {
    table_type: string;
  }) {
    return Request.get<Array<{
      label: string;
      value: string;
      children: Array<{
        label: string;
        value: string;
      }>
    }>>(`${this.path}/strategy_table/`, {
      params,
    });
  }
  // 获取表格的信息
  getTableRtMeta(params: {
    table_id: string
  }) {
    return Request.get<RtMetaModel>(`${this.path}/strategy_table/rt_meta/`, {
      params,
    });
  }
  // 获取表格最后一条数据
  getTableRtLastData(params: {
    table_id: string
  }) {
    return Request.get<{
      last_data: Array<Record<string, any>>;
    }>(`${this.path}/strategy_table/rt_last_data/`, {
      params,
    });
  }
  // 批量获取表格的字段列表
  getBatchTableRtFields(params: {
    table_ids: string
  }) {
    return Request.get<Array<{
      fields: Array<{
        field_type: string;
        label: string;
        value: string;
        spec_field_type: string;
      }>,
      table_id: string,
    }>>(`${this.path}/strategy_table/bulk_rt_fields/`, {
      params,
    });
  }
  // 获取表格的字段列表
  getTableRtFields(params: {
    table_id: string
  }) {
    return Request.get<Array<{
      field_type: string;
      label: string;
      value: string;
      spec_field_type: string;
    }>>(`${this.path}/strategy_table/rt_fields/`, {
      params,
    });
  }
  // 获取不同数据源可用调度方式
  getSourceType(params: Record<string, any>) {
    return Request.post <{
      support_source_types: Array<'batch_join_source' | 'stream_source'>,
    }>(`${this.path}/strategy/rule_audit_source_type_check/`, {
      params,
    });
  }


  // 获取策略标签
  getStrategyTags() {
    return Request.get<Array<StrategyTag>>(`${this.path}/strategy_tags/`);
  }

  // 获取方案列表
  getControlList() {
    return Request.get<Array<{
      control_type_id: string;
      control_id: string;
      control_name: string;
      versions: Array<{
        control_id: string;
        control_version: number
      }>
    }>>('/api/v1/controls/');
  }


  // event

  // 查询图表数据
  getGraph(params: {
    start_time: string
    end_time: string,
    strategy_id: number,
    interval: number,
    conditions: Array<Record<string, string>>
  }) {
    return Request.post<Record<string, Array<number>>>(`${this.path}/unify_query/graph/`, {
      params,
    });
  }
  // 获取操作事件列表
  getRecentLog(params: {
    start_time: string
    end_time: string,
    strategy_id: number,
    interval: number,
    conditions: Array<Record<string, string>>,
    page: number,
    page_size: number
  }, payload = {} as IRequestPayload) {
    return Request.post<IRequestResponsePaginationData<SearchModel>>(`${this.path}/unify_query/recent_log/`, {
      params,
      payload,
    });
  }
  // 获取算法下拉
  getAiopsPlan() {
    return Request.get<Record<string, any>>(`${this.path}/aiops_plan/`);
  }
  // 获取算法详情
  getAiopsPlanById(params: { id: string }) {
    return Request.get<AiopsPlanModel>(`${this.path}/aiops_plan/${params.id}/`);
  }
  // 获取结果表字段
  getRtfields(params: { system_id: string }) {
    return Request.get<Record<string, Record<string, string>>>(`${this.path}/aiops_meta/rt_fields/`, { params });
  }
  // 获取aiops策略详情
  getAiopsById(params: { id: string }) {
    return Request.get<AiopsDetailModel>(`${this.path}/strategies/${params.id}/aiops_detail/`, { params });
  }
  // 获取aiops策略详情
  getStrategyEvent(params: { id: string }) {
    return Request.get<StrategyFieldEvent>(`${this.path}/strategy_fields/fields_config/`, { params });
  }
  // 获取风险单风险等级
  getRiskLevel(params: {
    strategy_ids: string,
  }) {
    return Request.get<{
      [key: string]: {
        risk_level: string
      }
    }>(`${this.path}/strategy/display_info/`, {
      params,
    });
  }
  // 获取风险单运行记录
  getRisksRunning(params: {
    limit: number,
    offset: number,
    strategy_id: string,
  }) {
    return Request.get<{
      strategy_running_status: Array<{
        schedule_time: string,
        status: string,
        status_str: string,
        risk_count: number,
      }>
    }>(`${this.path}/strategy/${params.strategy_id}/strategy_running_status_list/`, {
      params,
    });
  }

  // 获取风险简要列表
  getRisksBrief(params: {
    page: number,
    page_size: number,
    strategy_id: string
    end_time: string,
    start_time: string,
  }) {
    return Request.get(`${this.module}risks/brief/`, {
      params,
    });
  }

  // 获取聚合函数列表
  getAggregationFunctions() {
    return Request.get(`${this.path}/report/aggregation_functions/`);
  }
}
export default new Strategy();
