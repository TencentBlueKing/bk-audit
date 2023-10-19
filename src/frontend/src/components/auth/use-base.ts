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
import {
  computed,
  onMounted,
} from 'vue';

import IamManageService from '@service/iam-manage';

import useRequest from '@hooks/use-request';

import { permissionDialog } from '@utils/assist';

export interface Props {
  permission?: string | boolean,
  actionId: string,
  resource?: string | number,
}

export default function (props: Props) {
  const {
    data: checkResultMap,
    loading,
    run,
  } = useRequest(IamManageService.check, {
    defaultValue: {},
  });

  const isShowRaw = computed(() => {
    if (props.permission === true) {
      return true;
    }
    return Boolean(checkResultMap.value[props.actionId]);
  });

  // 检测权限
  const checkPermission = () => {
    if (!props.actionId) {
      return;
    }

    run({
      action_ids: props.actionId,
      resources: props.resource,
    });
  };

  // watch(() => props.resource, (resource) => {
  //   if (resource) {
  //     // 资源信息变化需要重新鉴权
  //     checkPermission();
  //   }
  // });


  const handleRequestPermission = (event: Event) => {
    if (loading.value) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    permissionDialog(undefined, {
      action_ids: props.actionId,
      resources: props.resource,
    });
  };


  onMounted(() => {
  // 初始没有权限信息，需要主动鉴权一次
    if (props.permission === 'normal') {
      checkPermission();
    }
  });

  return {
    loading,
    isShowRaw,
    handleRequestPermission,
  };
}
