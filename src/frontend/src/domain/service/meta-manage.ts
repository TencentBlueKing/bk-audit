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
import AppInfoModel from '@model/meta/app-info';
import RetrieveUserModel from '@model/meta/retrieve-user';
import SystemModel from '@model/meta/system';
import SystemActionModel from '@model/meta/system-action';
import SystemResourceTypeModel from '@model/meta/system-resource-type';
import UserModel from '@model/meta/user';

import MetaManageSource from '../source/meta-manage';

export default {
  /**
   * @desc 获取全局配置
   */
  fetchGlobals() {
    return MetaManageSource.getGlobals({}, {
      cache: true,
    })
      .then(({ data }) => data);
  },
  /**
   * @desc 获取全局字典
   */
  fetchGlobalChoices() {
    return MetaManageSource.getGlobalChoices({}, {
      cache: true,
    })
      .then(({ data }) => data);
  },
  /**
   * @desc 根据特性id获取特性开关
   * @param { String } feature_id
   */
  fetchFeature(params: {feature_id: string}) {
    return MetaManageSource.getFeature(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取 Namespace 列表
   */
  fetchNamespaceList() {
    return MetaManageSource.getAllNamespace()
      .then(({ data }) => data);
  },
  /**
   * @desc 获取系统列表
   * @param { Object } params
   */
  fetchSystemList(params:
    {
      page:number,
      page_size: number,
      keyword?: string
    }) {
    return MetaManageSource.getAllSysetem(params, {
      permission: 'page',
    }).then(({ data }) => ({
      ...data,
      results: data.results.map(result => new SystemModel(result)),
    }));
  },
  /**
   * @desc 获取系统列表(All)
   * @param { String } action_ids
   */
  fetchSystemWithAction(params: { action_ids?: string }) {
    return MetaManageSource.getAllSysetemByActionId(params, {
      permission: 'page',
    })
      .then(({ data }) => data);
  },
  /**
   * @desc 获取系统详情
   * @param { String } id
   */
  fetchSystemDetail(params: Record<'id', string>) {
    return MetaManageSource.getSysetemById(params, {
      permission: 'page',
    })
      .then(({ data }) => new SystemModel(data));
  },
  /**
   * @desc 操作列表
   * @param { String } id
   */
  fetchSystemActionList(params: Record<'id', string>) {
    return MetaManageSource.getAllActionBySysetemId(params, {
      permission: 'page',
    })
      .then(({ data }) => data.map(item => new SystemActionModel(item)));
  },
  /**
   * @desc 操作列表(搜索)
   * @param { String } system_ids
   */
  fetchBatchSystemActionList(params: Record<'system_ids', string>) {
    return MetaManageSource.getBatchActionBySystemIds(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 资源类型列表
   * @param { String } id
   */
  fetchSysetemResourceTypeList(params: Record<'id', string>) {
    return MetaManageSource.getAllResourceTypeBySysetemId(params, {
      permission: 'page',
    })
      .then(({ data }) => data.map(item => new SystemResourceTypeModel(item)));
  },
  /**
   * @desc 资源类型列表(搜索)
   * @param { String } system_ids
   */
  fetchBatchSystemResourceTypeList(params: Record<'system_ids', string>) {
    return MetaManageSource.getBatchResourceTypeBySysetemIds(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取用户列表
   * @param { Object } params
   */
  fetchUserList(params = {}) {
    return MetaManageSource.getAllUser(params)
      .then(({ data }) => ({
        count: data.count,
        results: data.results.map(item => new UserModel(item)),
      }));
  },
  /**
   * @desc 获取通知组变量列表
   * @param { Object } params
   */
  fetchVariableList() {
    return MetaManageSource.getVariableList()
      .then(({ data }) => data.member_variable);
  },
  /**
   * @desc 获取标准字段
   * @param { Boolean } is_etl
   */
  fetchStandardField(params?: Record<'is_etl', boolean>) {
    return MetaManageSource.getStandardField(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取敏感信息对象列表
   */
  fetchSensitiveList(params: {
    system_id: string;
    resource_type: string;
    resource_id: string;
  }) {
    return MetaManageSource.getSensitiveList(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取用户字段
   * @param { String } route_path
   */
  fetchCustomFields(params: Record<'route_path', string>) {
    return MetaManageSource.getCustomFields(params)
      .then(({ data }) => data || []);
  },
  /**
   * @desc 更新用户字段
   * @param { Object } params
   */
  fetchUpdateCustomFields(params: {route_path: string, fields: []}) {
    return MetaManageSource.updateCustomField(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取单个用户信息
   * @param { Object } params
   */
  fetchRetrieveUser(params: {
    id: string,
    lookup_field?: string,
    fields?:string
  }) {
    return MetaManageSource.getRetrieveUser(params)
      .then(({ data }) => new RetrieveUserModel(data));
  },
  /**
   * @desc 获取资源类型结构
   * @param { Object } params
   */
  fetchResourceTypeSchema(params:
    {
      system_id: string,
      resource_type_id: string,
      id: string
    }) {
    return MetaManageSource.getResourceTypeSchema(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取多平台应用信息
   * @param { String } app_code
   */
  fetchAppInfo(params: Record<'app_code', string>) {
    return MetaManageSource.getAppInfo(params)
      .then(({ data }) => new AppInfoModel(data));
  },
  /**
   * @desc 获取系统详情
   * @param { String } id
   */
  fetchSystemInfo(params: Record<'id', string>) {
    return MetaManageSource.getSystemInfo(params)
      .then(({ data }) => new SystemModel(data));
  },
  /**
   * @desc 获取资源类型结构
   * @param { Object } params
   */
  /**
   * @desc 获取资源类型结构
   * @param { Object } params
   */
  fetchResourceTypeSchemaSearch(params:
    {
      system_id: string,
      resource_type_id: string,
      id: string
    }) {
    return MetaManageSource.getResourceTypeSchemaSearch(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取集群列表
   * @param { Number } bk_biz_id
   */
  fetchListBcsClusters(params: Record<'bk_biz_id', number>) {
    return MetaManageSource.getListBcsClusters(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取标签（策略和联表合并标签）
   */
  fetchTags() {
    return MetaManageSource.getTags()
      .then(({ data }) => data);
  },
  /**
   * @desc 收藏的查询条件列表
   * @param { Object } params
   */
  fetchFavouriteQueryList(params: Record<string, any>) {
    return MetaManageSource.getFavouriteQueryList(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 收藏查询条件
   * @param { Object } params
   */
  favouriteQueryCreate(params: Record<string, any>) {
    return MetaManageSource.favouriteQueryCreate(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 更新收藏查询条件
   * @param { Object } params
   */
  favouriteQueryUpdate(params: Record<string, any>) {
    return MetaManageSource.favouriteQueryUpdate(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 删除收藏查询条件
   * @param { Object } params
   */
  favouriteQueryDelete(params: {
    id: number
  }) {
    return MetaManageSource.favouriteQueryDelete(params)
      .then(({ data }) => data);
  },
};
