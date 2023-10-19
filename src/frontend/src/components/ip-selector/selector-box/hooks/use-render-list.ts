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
  type ComputedRef,
  reactive,
  type Ref,
  ref,
  watch,
} from 'vue';

import useDebouncedRef from '@hooks/use-debounced-ref';

import { encodeRegexp } from '@utils/assist';

type TResult<T> = {
  showPagination: Ref<boolean>,
  searchKey: Ref<string>
  pagination: {
    modelValue: number;
    count: number;
    limit: number;
  },
  searchList:  ComputedRef<Array<T>>,
  renderList: ComputedRef<Array<T>>
}

export default function <T> (list: Ref<Array<T>>, filterCallback: (p:T, rule: RegExp)=>boolean): TResult<T> {
  const searchKey = useDebouncedRef('');
  const showPagination = ref(false);
  const pagination = reactive({
    modelValue: 1,
    count: list.value.length,
    limit: 10,
  });

  const searchList = computed(() => {
    if (!searchKey.value) {
      return list.value;
    }
    const searchRule = new RegExp(encodeRegexp(searchKey.value), 'i');
    return list.value.reduce((result, item) => {
      if (filterCallback(item, searchRule)) {
        result.push(item);
      }
      return result;
    }, [] as T[]);
  });

  const renderList = computed(() => searchList.value.slice(
    (pagination.modelValue - 1) * pagination.limit,
    pagination.limit * pagination.modelValue,
  ));

  watch(searchKey, () => {
    pagination.modelValue = 1;
    pagination.count = searchList.value.length;
  });
  watch(searchList, (list) => {
    pagination.count = list.length;
    showPagination.value = list.length > 0 && list.length > pagination.limit;
  }, {
    immediate: true,
  });


  return {
    showPagination,
    searchKey,
    pagination,
    searchList,
    renderList,
  };
}
