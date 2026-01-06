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
import type {
  CancelTokenSource,
} from 'axios';
import {
  onBeforeUnmount,
  onMounted,
  type Ref,
  ref,
} from 'vue';

import { getCancelTokenSource } from '@utils/request';

import execRequest from './exec-request';

interface IOptions<T> {
  defaultValue: T;
  manual?: boolean;
  defaultParams?: object;
  loop?: boolean;
  loopOnError?: boolean; // 轮询时错误也继续轮询
  onSuccess?: (result:T) => void;
  onFinally?: () => void; // 请求完成时调用（无论成功还是失败）
  holdLoading?: boolean;
}
interface IResult<T> {
  loading: Ref<boolean>;
  data: Ref<T>;
  error: Ref<boolean>;
  errorMessage: Ref<string>;
  run: (params?: object) => Promise<T>;
  refresh: () => void;
  cancel: () => void;
  loop: () => () => void;
}


export default function <T> (
  service: (params: any) => Promise<T>,
  customOptions = {} as IOptions<T>,
):IResult<T> {
  const options = Object.assign({}, {
    defaultValue: null,
    manual: false,
    defaultParams: {},
    loop: false,
    holdLoading: false,
  }, customOptions);

  const loading = ref(false);
  const error = ref(false);
  const errorMessage = ref('');
  const data = ref<Ref<T>>(options.defaultValue as any);

  let paramsMemo = {};
  let cancelTokenSource: CancelTokenSource;

  const run = (params = {} as Record<string, any>) => {
    paramsMemo = params || {};
    const requestHandler = options.holdLoading ? execRequest(service(params), () => {
      loading.value = true;
    }) : (() => {
      loading.value = true;
      return service(params);
    })();
    const handler = requestHandler.then((result) => {
      data.value = result;
      error.value = false; // 成功时清除错误状态
      options.onSuccess?.(data.value);
      return result;
    })
      .catch((errorMsg) => {
        error.value = true;
        errorMessage.value = errorMsg.message;
        throw errorMsg;
      })
      .finally(() => {
        loading.value = false;
        options.onFinally?.();
      }) as Promise<T>;
    cancelTokenSource = getCancelTokenSource();
    return handler;
  };

  const refresh = () => {
    run(paramsMemo);
  };

  const cancel = () => {
    if (cancelTokenSource) {
      cancelTokenSource.cancel();
    }
  };

  const loop = () => {
    let isCancelled = false;
    let timer: number;
    const exexHandler = () => {
      service(paramsMemo)
        .then((result) => {
          data.value = result;
          error.value = false;
          if (isCancelled) {
            return isCancelled;
          }
          timer = setTimeout(() => {
            exexHandler();
          }, 2000);
        })
        .catch(() => {
          error.value = true;
          // 如果配置了 loopOnError，错误时也继续轮询
          if (options.loopOnError && !isCancelled) {
            timer = setTimeout(() => {
              exexHandler();
            }, 2000);
          }
        });
    };
    exexHandler();

    const cancelLoop = () => {
      isCancelled = true;
      clearTimeout(timer);
    };
    onBeforeUnmount(() => {
      cancelLoop();
    });
    return cancelLoop;
  };

  onMounted(() => {
    if (options.manual) {
      run(options.defaultParams);
    }
  });

  onBeforeUnmount(() => {
    cancel();
  });

  return {
    loading,
    data,
    error,
    errorMessage,
    run,
    refresh,
    cancel,
    loop,
  };
}
