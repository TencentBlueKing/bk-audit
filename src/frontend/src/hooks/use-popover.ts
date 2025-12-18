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
  onBeforeMount,
  onMounted } from 'vue';

import {
  createPopper,
  flip,
  preventOverflow,
} from '@popperjs/core';

export default function () {
  let referenceElIns: HTMLElement;
  let floatingElIns: HTMLElement;
  const create = (referenceEl: HTMLElement, floatingEl: HTMLElement) => {
    referenceElIns = referenceEl;
    floatingElIns = floatingEl;
    const {
      width,
    } = referenceElIns.getBoundingClientRect();

    Object.assign(floatingElIns.style, {
      display: 'block',
      width: `${width}px`,
    });
    return createPopper(referenceElIns, floatingElIns, {
      placement: 'bottom',
      modifiers: [
        preventOverflow,
        flip,
        {
          name: 'offset',
          options: {
            offset: ({ placement }: { placement: string }) => {
              if (placement === 'bottom') {
                return [0, 10];
              }
              return [10, 0];
            },
          },
        },
        {
          name: 'flip',
          options: {
            rootBoundary: 'document',
          },
        },
      ],
    });
  };

  const hide = () => {
    Object.assign(floatingElIns.style, {
      display: 'none',
    });
  };

  const show = () => {
    Object.assign(floatingElIns.style, {
      display: 'block',
    });
  };

  onMounted(() => {
    document.addEventListener('click', hide);
  });

  onBeforeMount(() => {
    document.removeEventListener('click', hide);
  });

  return {
    create,
    show,
    hide,
  };
}
