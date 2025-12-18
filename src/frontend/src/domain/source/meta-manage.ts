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
import type EventSourceAppModel from '@model/meta/event-source-app';
import type GlobalsModel from '@model/meta/globals';
import type NamespaceModel from '@model/meta/namespace';
import type ResourceTypeSchemaModel from '@model/meta/resource-type-schema';
import type RetrieveUserModel from '@model/meta/retrieve-user';
import type StandardFieldModel from '@model/meta/standard-field';
import type SystemModel from '@model/meta/system';
import type SystemActionModel from '@model/meta/system-action';
import type SystemResourceTypeModel from '@model/meta/system-resource-type';
import type SystemResourceTypeTree from '@model/meta/system-resource-type-tree';
import type UserModel from '@model/meta/user';

import Request, {
  type IRequestPayload,
  type IRequestResponsePaginationData,
} from '@utils/request';

import ModuleBase from './module-base';

class MetaManage extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1/meta';
  }

  // 获取全局配置
  getGlobals(params: Record<string, any>, payload = {} as IRequestPayload) {
    return Request.get<GlobalsModel>(`${this.module}/globals/`, {
      params,
      payload,
    });
  }
  // 获取全局字典
  getGlobalChoices(params: Record<string, any>, payload = {} as IRequestPayload) {
    return Request.get<Record<string, Array<{
      id: string,
      name: string
    }>>>(`${this.module}/globals/global_choices/`, {
      params,
      payload,
    });
  }
  // 根据特性id获取特性开关，用于判断是否显示按钮、菜单等
  getFeature(params: {feature_id: string}) {
    return Request.get<Record<'enabled', boolean>>(`/api/v1/feature/${params.feature_id}/`);
  }
  // 获取 Namespace 列表
  getAllNamespace() {
    return Request.get<NamespaceModel>(`${this.module}/namespaces/`);
  }
  // 创建系统
  createdSysetem(params: Record<string, any>) {
    return Request.post(`${this.path}/systems/`, {
      params,
    });
  }
  // 更新系统
  updateSysetem(params: Record<string, any>) {
    return Request.put(`${this.path}/systems/${params.system_id}/`, {
      params,
    });
  }
  // 获取系统列表
  getAllSysetem(
    params: {
      page:number,
      page_size: number,
      audit_status: 'accessed'
      keyword?: string,
    },
    payload = {} as IRequestPayload,
  ) {
    return Request.get<IRequestResponsePaginationData<SystemModel>>(`${this.path}/systems/`, {
      params: {
        ...params,
        audit_status: params.audit_status || 'accessed',
      },
      payload,
    });
  }
  // 获取系统列表(All)
  getAllSysetemByActionId(params: { action_ids?: string }, payload = {} as IRequestPayload) {
    return Request.get<Array<EventSourceAppModel>>(`${this.path}/systems/all/`, {
      params,
      payload,
    });
  }
  // 获取系统详情
  getSysetemById(params: Record<'id', string>, payload = {} as IRequestPayload) {
    return Request.get<SystemModel>(`${this.path}/systems/${params.id}/`, {
      payload,
    });
  }
  // 操作列表
  getAllActionBySysetemId(params: Record<'id', string>, payload = {} as IRequestPayload) {
    return Request.get<Array<SystemActionModel>>(`${this.path}/systems/${params.id}/actions/`, {
      params,
      payload,
    });
  }
  // 操作列表(搜索)
  getBatchActionBySystemIds(params: Record<'system_ids', string>) {
    return Request.get<Array<Record<'id'|'name', string>>>(`${this.path}/systems/action_search/`, {
      params,
    });
  }
  // 删除操作
  deleteAction(params: Record<'unique_id', string>) {
    return Request.delete(`${this.path}/actions/${params.unique_id}/`);
  }
  // 获取操作
  getActionByUniqueId(params: Record<'unique_id', string>) {
    return Request.get<SystemActionModel>(`${this.path}/actions/${params.unique_id}/`);
  }
  // 新建操作
  createAction(params: Record<string, any>) {
    return Request.post(`${this.path}/actions/`, {
      params,
    });
  }
  // 批量新建操作
  batchCreateAction(params: Record<string, any>) {
    return Request.post(`${this.path}/actions/bulk/`, {
      params,
    });
  }
  // 更新操作
  updateAction(params: Record<string, any>) {
    return Request.put(`${this.path}/actions/${params.unique_id}/`, {
      params,
    });
  }
  // 资源类型列表
  getAllResourceTypeBySysetemId(params: Record<'id', string>, payload = {} as IRequestPayload) {
    return Request.get<Array<SystemResourceTypeModel>>(`${this.path}/systems/${params.id}/resource_types/`, {
      params,
      payload,
    });
  }
  // 资源类型列表(搜索)
  getBatchResourceTypeBySysetemIds(params: Record<'system_ids', string>) {
    return Request.get<Array<Record<'id'|'name', string>>>(`${this.path}/systems/resource_type_search/`, {
      params,
    });
  }
  // 删除资源类型
  deleteResourceType(params: Record<'unique_id', string>) {
    return Request.delete(`${this.path}/resource_types/${params.unique_id}/`);
  }
  // 获取资源类型
  getResourceTypeByUniqueId(params: Record<'unique_id', string>) {
    return Request.get<SystemResourceTypeModel>(`${this.path}/resource_types/${params.unique_id}/`);
  }
  // 获取父级资源
  getParentResourceType(params: Record<'system_id', string>) {
    return Request.get<Array<SystemResourceTypeTree>>(`${this.path}/resource_types/tree/`, {
      params,
    });
  }
  // 新建资源
  createResourceType(params: Record<string, any>) {
    return Request.post(`${this.path}/resource_types/`, {
      params,
    });
  }
  // 批量创建资源
  batchCreateResourceType(params: Record<string, any>) {
    return Request.post(`${this.path}/resource_types/bulk_create/`, {
      params,
    });
  }
  // 更新资源
  updateResourceType(params: Record<string, any>) {
    return Request.put(`${this.path}/resource_types/${params.unique_id}/`, {
      params,
    });
  }
  // 获取用户列表
  getAllUser(params: Record<string, any>) {
    return Request.get<{results: Array<UserModel>, count: number}>(`${this.path}/user_manage/list_users/`, {
      params,
    });
  }
  // 获取通知组变量列表
  getVariableList() {
    return Request.get<{member_variable: Array<{
      label: string,
      value: string
    }>}>('/api/v1/notice/common/');
  }
  // 获取标准字段
  getStandardField(params?: Record<'is_etl', boolean>) {
    return Request.get<Array<StandardFieldModel>>(`${this.module}/fields/`, {
      params,
    });
  }
  // 获取敏感信息对象列表
  getSensitiveList(params: {
    system_id: string;
    resource_type: string;
    resource_id: string;
  }) {
    return Request.get<{
      id: string;
      name: string;
    }>(`${this.module}/sensitive_object/`, {
      params,
    });
  }

  // 获取用户字段
  getCustomFields(params: Record<'route_path', string>) {
    return Request.get<Array<StandardFieldModel>>(`${this.module}/custom_fields/`, {
      params,
    });
  }
  // 更新用户字段
  updateCustomField(params: Record<string, any>) {
    return Request.post(`${this.module}/custom_fields/`, {
      params,
    });
  }
  // 获取单个用户信息
  getRetrieveUser(params: {
    id: string,
    lookup_field?: string,
    fields?:string
  }) {
    return Request.get<RetrieveUserModel>(`${this.path}/user_manage/retrieve_user/`, {
      params,
    });
  }
  // 获取资源类型结构
  getResourceTypeSchema(params: {
    system_id: string,
    resource_type_id: string,
    id: string
  }) {
    return Request.get<Array<ResourceTypeSchemaModel>>(`${this.path}/systems/${params.system_id}/resource_type_schema/`, {
      params,
    });
  }
  // 获取多平台应用信息
  getAppInfo(params: Record<'app_code', string>) {
    return Request.get(`${this.path}/paas/app_info/`, {
      params,
    });
  }
  // 获取系统详情
  getSystemInfo(params: Record<'id', string>, payload = {} as IRequestPayload) {
    return Request.get<SystemModel>(`${this.path}/systems/${params.id}/search/`, {
      payload,
    });
  }
  // 获取检索资源类型结构
  getResourceTypeSchemaSearch(params: {
    system_id: string,
    resource_type_id: string,
    id: string
  }) {
    return Request.get<Array<ResourceTypeSchemaModel>>(`${this.path}/systems/${params.system_id}/resource_type_schema_search/`, {
      params,
    });
  }
  // 获取集群列表
  getListBcsClusters(params: { bk_biz_id: number}) {
    return Request.get<Array<Record<'id'|'name', string>>>(`${this.module}/bizs/list_bcs_clusters/`, {
      params,
    });
  }
  // 获取标签
  getTags() {
    return Request.get<Array<{
      link_table_count: number,
      tag_id: string,
      tag_name: string
    }>>(`${this.path}/tag/`);
  }
  // 获取收藏的查询条件列表
  getFavouriteQueryList(params: Record<string, any>) {
    return Request.get<Array<{
      config_name: string,
      id: number,
      config_content: Record<string, any>
    }>>(`${this.path}/general_config/`, {
      params,
    });
  }
  // 收藏查询条件
  favouriteQueryCreate(params: Record<string, any>) {
    return Request.post(`${this.path}/general_config/`, {
      params,
    });
  }
  // 更新查询条件
  favouriteQueryUpdate(params: Record<string, any>) {
    const { id, ...rest } = params;
    return Request.put(`${this.path}/general_config/${id}/`, {
      params: rest,
    });
  }
  // 删除查询条件
  favouriteQueryDelete(params: {
    id: number
  }) {
    return Request.delete(`${this.path}/general_config/${params.id}/`, {
      params,
    });
  }

  // 更新系统审计状态
  updateSystemAuditStatus(params: Record<string, any>) {
    return Request.put(`${this.path}/systems/${params.system_id}/audit_status/`, {
      params,
    });
  }
  // 更新系统收藏
  updateSystemAuditFavorite(params: Record<string, any>) {
    return Request.put(`${this.path}/systems/${params.system_id}/favorite/`, {
      params,
    });
  }
}

export default new MetaManage();

