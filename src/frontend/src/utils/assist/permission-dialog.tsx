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
  type App,
  createApp,
} from 'vue';

import type ApplyDataModel from '@model/iam/apply-data';

import PermissionDialog, {
  type CheckParams,
} from '@components/apply-permission/dialog.vue';

import I18n from '@language/index.js';

let activeApp: App<Element> | null = null;
let activeContainer: HTMLElement | null = null;

const destroyActivePermissionDialog = () => {
  if (activeApp) {
    activeApp.unmount();
    activeApp = null;
  }
  if (activeContainer?.parentNode) {
    activeContainer.parentNode.removeChild(activeContainer);
  }
  activeContainer = null;
};

export const permissionDialog = (applyData?: ApplyDataModel, checkParams?: CheckParams) => {
  // 同一时期只保留一个权限弹窗
  destroyActivePermissionDialog();

  const container = document.createElement('div');
  activeContainer = container;

  const handleCancel = () => {
    if (activeContainer === container) {
      destroyActivePermissionDialog();
    }
  };

  const app = createApp({
    setup() {
      return () => (
        <PermissionDialog
          applyData={applyData}
          checkParams={checkParams}
          onCancel={handleCancel} />
      );
    },
  });
  activeApp = app;
  app.use(I18n).mount(container);
  document.body.appendChild(container);
};
