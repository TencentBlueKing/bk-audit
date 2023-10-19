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
import { customRef } from 'vue';

export default <T>(value: T, delay = 200) => {
  let timeout: number;
  let localValue = value;
  return customRef((track, trigger) => ({
    get() {
      track();
      return localValue;
    },
    set(newValue) {
      clearTimeout(timeout);
      timeout = setTimeout(() => {
        localValue = newValue;
        trigger();
      }, delay);
    },
  }));
};
