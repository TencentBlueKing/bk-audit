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
import MetaManageService from '@service/meta-manage';

export interface IFieldConfig {
  label: string,
  type: string,
  required: boolean,
  validator?: (value: any)=> boolean,
  message?: string,
  service?: (params?: Record<string, any>) => Promise<Array<any>>
  labelName?: string,
  valName?: string,
  operator?: string,
  help?: boolean,
  canClose?: boolean,
  customField?: boolean,
  isFavourite?: boolean,
}
// eslint-disable-next-line no-useless-escape
// const specialReg = /[`~!@#$%^&*()_\+=<>?:"{}|,.\/;'\\[\]·~！@#￥%……&*（）——\+={}|《》？：“”【】、；‘'，。、]/im;
export default {
  system_id: {
    label: '系统名称(ID)',
    type: 'system-id',
    required: false,
    operator: 'include',
    service: () => MetaManageService.fetchSystemWithAction({
      action_ids: 'search_regular_event',
    }),
  },
  action_id: {
    label: '操作事件名',
    type: 'action-id',
    required: false,
    operator: 'include',
    service: MetaManageService.fetchBatchSystemActionList,
  },
  resource_type_id: {
    label: '资源类型',
    type: 'resource-type-id',
    required: false,
    operator: 'include',
    service: MetaManageService.fetchBatchSystemResourceTypeList,
  },
  instance_name: {
    label: '资源实例名',
    type: 'string',
    operator: 'like',
    required: false,
    help: true,
    // validator(str: string) {
    //   if (str === '') return true;
    //   return !specialReg.test(str);
    // },
    // message: '不允许出现特殊字符',
  },
  username: {
    label: '操作人',
    type: 'user-selector-tenant', // 多租户人员选择器
    required: false,
    operator: 'include',
  },
  event_id: {
    label: '事件 ID',
    type: 'string',
    required: false,
    operator: 'include',
    // validator(str: string) {
    //   if (str === '') return true;
    //   return !specialReg.test(str);
    // },
    // message: '不允许出现特殊字符',
  },
  datetime: {
    label: '操作时间',
    type: 'datetimerange',
    required: true,
  },
  request_id: {
    label: '请求 ID',
    type: 'string',
    required: false,
    operator: 'include',
    canClose: true,
    // validator(str: string) {
    //   if (str === '') return true;
    //   return !specialReg.test(str);
    // },
    // message: '不允许出现特殊字符',
  },
  event_content: {
    label: '事件描述',
    type: 'string',
    required: false,
    operator: 'like',
    help: true,
    canClose: true,
    // validator(str: string) {
    //   if (str === '') return true;
    //   return !specialReg.test(str);
    // },
    // message: '不允许出现特殊字符',
  },
  user_identify_type: {
    label: '操作人账号类型',
    type: 'select',
    required: false,
    operator: 'include',
    canClose: true,
  },
  // user_identify_tenant_id: {
  //   label: '操作人租户 ID',
  //   type: 'string',
  //   required: false,
  // },
  access_type: {
    label: '操作途径',
    type: 'select',
    required: false,
    operator: 'include',
    canClose: true,
  },
  access_source_ip: {
    label: '来源 IP',
    type: 'string',
    required: false,
    operator: 'include',
    message: 'IP地址格式不正确',
    canClose: true,
    validator: (value: string) => {
      const ipv4 = /^((\d|[1-9]\d|1\d\d|2([0-4]\d|5[0-5]))\.){4}$/;
      const ipv6 = /^(([\da-fA-F]{1,4}):){8}$/;
      if (value) {
        if (!ipv4.test(`${value}.`) && !ipv6.test(`${value}:`)) {
          return false;
        }
      }
      return true;
    },
  },
  access_user_agent: {
    label: '客户端类型',
    type: 'string',
    required: false,
    operator: 'like',
    canClose: true,
    // validator(str: string) {
    //   if (str === '') return true;
    //   return !specialReg.test(str);
    // },
    // message: '不允许出现特殊字符',
  },
  // resource_sensitive_lvl: {
  //   label: '资源敏感等级',
  //   type: 'sensitive',
  //   required: false,
  // },
  instance_id: {
    label: '资源实例 ID',
    type: 'string',
    required: false,
    operator: 'include',
    canClose: true,
    // validator(str: string) {
    //   if (str === '') return true;
    //   return !specialReg.test(str);
    // },
    // message: '不允许出现特殊字符',
  },
  result_code: {
    label: '操作结果',
    type: 'select',
    required: false,
    operator: 'include',
    help: true,
    canClose: true,
  },
  result_content: {
    label: '操作结果描述',
    type: 'string',
    required: false,
    operator: 'include',
    canClose: true,
    // validator(str: string) {
    //   if (str === '') return true;
    //   return !specialReg.test(str);
    // },
    // message: '不允许出现特殊字符',
  },
  log: {
    label: '原始日志',
    type: 'string',
    required: false,
    operator: 'match_any',
    help: true,
    canClose: true,
  },
  query_string: {
    label: '查询语句',
    type: 'expr',
    required: false,
  },
} as Record<string, IFieldConfig>;
