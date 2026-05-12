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
import type { RouteLocationNormalizedLoaded, Router } from 'vue-router';

import i18n from '@language/index.js';

interface ChangeConfirmOptions {
  message?: string;
  route?: RouteLocationNormalizedLoaded;
  router?: Router;
}

export const changeConfirm = (options?: string | ChangeConfirmOptions): Promise<boolean> => {
  const { t, te } = i18n.global;

  // 兼容旧调用方式：直接传字符串 message
  const opts: ChangeConfirmOptions = typeof options === 'string'
    ? { message: options }
    : options || {};
  const { message = '离开将会导致未保存信息丢失', route, router } = opts;

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
      class: 'change-confirm-info-box',
      onConfirm() {
        window.changeConfirm = false;
        if (route && route.meta.changeSceneIsBackedList && router) {
          console.log('返回', route.meta.ListPageName);
          // 延迟跳转，等待 syncSceneIdToRoute 的 router.replace 及 route.query watcher 完成后再导航
          setTimeout(() => {
            router.push({
              name: route.meta.ListPageName as string,
            });
          }, 0);
        }
        resolve(true);
      },
      onClose() {
        reject(false);
      },
    });
  });
};
