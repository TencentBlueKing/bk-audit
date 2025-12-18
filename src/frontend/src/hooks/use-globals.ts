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

import useRequest from '@hooks/use-request';

export default function () {
  const {
    loading,
    data,
  } = useRequest(MetaManageService.fetchGlobals, {
    defaultValue: {
      app_info: {
        app_code: '',
      },
      data_delimiter: [],
      data_encoding: [],
      es_source_type: [],
      etl_config: [],
      param_conditions_match: [],
      param_conditions_type: [],
      storage_duration_time: [],
      bcs_log_type: [],
    },
    manual: true,
  });

  return {
    loading,
    data,
  };
}
