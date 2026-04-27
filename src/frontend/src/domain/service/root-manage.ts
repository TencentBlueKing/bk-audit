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
import ConfigModel from '@model/root/config';
import userPermissionConfig from '@model/root/user-permission';

import RootManageSource from '../source/root-manage';


export default {
  /**
   * @desc 获取配置信息
   */
  config() {
    return RootManageSource.config({}, {
      cache: true,
    })
      .then(({ data }) => new ConfigModel(data));
  },
  /**
   *  @desc 获取当前语言
   *  @param { string } id
   */
  language(params: { id: string}) {
    return RootManageSource.language(params, {
      cache: true,
    })
      .then(data => data);
  },
  /**
   *  @desc 获取身份权限
   */
  getUserPermission() {
    return RootManageSource.getUserPermission()
      .then(({ data }) => {
        sessionStorage.setItem('userScenePermission', JSON.stringify(data));

        /**
         * 根据四个权限字段确定5种身份角色
         * 权限优先级（高→低）：manage_platform > manage_scene > edit_system > view_system
         */
        let userRole = [] as string[];
        if (data.manage_platform) {
          userRole = ['saas_admin']; // SaaS管理员：全部权限含平台管理
          sessionStorage.setItem('userRole', JSON.stringify(userRole));
          return data as userPermissionConfig;
        }

        if (!data.manage_platform && !data.manage_scene && !data.edit_system && !data.view_system && !data.view_scene) {
          userRole = ['risk_handler']; // 风险处理者：仅处理风险
          sessionStorage.setItem('userRole', JSON.stringify(userRole));

          return data as userPermissionConfig;
        }
        if (data.manage_scene) {
          userRole.push('scene_admin'); // 场景管理员：可管理场景配置
        }
        if (data.edit_system || data.view_system) {
          userRole.push('system_admin'); // 系统管理员：可编辑/导入系统  系统使用者：可在系统内查看数据
        }
        if (data.view_scene) {
          userRole.push('scene_user'); // 场景使用者：可在场景内查看数据
        }
        sessionStorage.setItem('userRole', JSON.stringify(userRole));

        return data as userPermissionConfig;
      });
  },
};
