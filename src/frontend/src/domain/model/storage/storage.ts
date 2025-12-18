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
export default class Storage {
  auth_info: {
    password: string,
    username: string
  };
  bk_biz_id: number;
  cluster_config: {
    cluster_id: number,
    cluster_name: string,
    create_time: string,
    creator: string,
    custom_option: {
      bkbase_cluster_id: string,
      description: string,
      allocation_min_days: number,
      hot_warm_config: {
        hot_attr_name: string,
        hot_attr_value: string,
        is_enabled: boolean,
        warm_attr_name: string,
        warm_attr_value: string
      },
      setup_config: {
        number_of_replicas_default: number,
        number_of_replicas_max: number,
        retention_days_default: number,
        retention_days_max: number,
      },
      source_type: string,
      option: {
        is_default: boolean,
        update_at: string,
        updater: string,
        create_at: string,
        creator: string
      },
      [key: string]: any
    },
    domain_name: string,
    enable_hot_warm: boolean,
    last_modify_time: string,
    last_modify_user: string,
    port: number,
    schema: string,
  };
  permission: {
    // 删除权限
    delete_storage: boolean,
    // 编辑权限
    edit_storage: boolean,
  };
  // 异步获取状态
  status: boolean;
  isStatusLoading: boolean;

  constructor(payload: Storage) {
    this.bk_biz_id = payload.bk_biz_id;
    this.permission = payload.permission;

    this.cluster_config = this.initClusterConfig(payload.cluster_config);
    this.auth_info = this.initAuthInfo(payload.auth_info);

    this.isStatusLoading = true;
    this.status = false;
  }

  // 是否为默认
  get isDefault(): boolean {
    return this.cluster_config.custom_option.option.is_default;
  }

  initAuthInfo(authInfo = {} as Storage['auth_info']) {
    const {
      password,
      username,
    } = authInfo;

    return {
      username,
      // 编辑模式密码为 ******
      password: this.cluster_config.cluster_id ? '******' : password,
    };
  }
  initClusterConfig(clusterConfig: Storage['cluster_config']) {
    const {
      cluster_id,
      cluster_name,
      create_time,
      creator,
      custom_option: customOption,
      domain_name,
      enable_hot_warm,
      last_modify_time,
      last_modify_user,
      port,
      schema,
    } = clusterConfig;

    if (!customOption.option) {
      customOption.option = {
        is_default: false,
        update_at: '',
        updater: '',
        create_at: '',
        creator: '',
      };
    }
    if (!customOption.option.is_default) {
      customOption.option.is_default = false;
    }
    if (!customOption.option.creator) {
      customOption.option.creator = '--';
    }
    if (!customOption.option.create_at) {
      customOption.option.create_at = '--';
    }

    return {
      cluster_id,
      cluster_name,
      create_time,
      creator,
      custom_option: customOption,
      domain_name,
      enable_hot_warm,
      last_modify_time,
      last_modify_user,
      port,
      schema,
    };
  }
}
