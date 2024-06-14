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
import { InfoBox } from 'bkui-vue';

import i18n from '@language/index.js';

export const changeConfirm = (message = '离开将会导致未保存信息丢失'): Promise<boolean> => {
  const { t, te } = i18n.global;
  if (!window.changeConfirm || window.changeConfirm === 'popover') {
    return Promise.resolve(true);
  }
  const msg = te(message) ? t(message) : message;
  return new Promise((resolve, reject) => {
    InfoBox({
      title: t('确认离开当前页？'),
      subTitle: msg,
      cancelText: t('取消'),
      confirmText: t('确定'),
      headerAlign: 'center',
      contentAlign: 'center',
      footerAlign: 'center',
      onConfirm() {
        window.changeConfirm = false;
        resolve(true);
      },
      onClose() {
        reject(false);
      },
    });
  });
};
