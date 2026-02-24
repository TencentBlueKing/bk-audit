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
import ApplyDataModel from '@model/iam/apply-data';

import IamManageSource from '../source/iam-manage';

export default {
  /**
   * @desc 检查当前用户对该动作是否有权限
   * @param { Object } params
   */
  check(params: { action_ids: string, resources?: string }) {
    return IamManageSource.check(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 检查当前用户是否拥有任意权限策略
   * @param { Object } params
   */
  checkAny(params: { action_ids: string }) {
    return IamManageSource.checkAny(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取权限申请数据
   * @param { Object } params
   */
  getApplyData(params: { action_ids: string, resources?: string }) {
    return IamManageSource.getApplyData(params)
      .then(({ data }) => new ApplyDataModel(data));
  },
};
