<!--
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
-->
<template>
  <div style="width: 100%;height: 100%;">
    <div id="panel" />
  </div>
</template>
<script setup lang="ts">
  import {
    nextTick,
    watch,
  } from 'vue';
  import {
    useRoute,
  } from 'vue-router';

  import IamApplyDataModel from '@model/iam/apply-data';

  import useMessage from '@hooks/use-message';

  import useEventBus from '@/hooks/use-event-bus';

  interface Error {
    data: Record<string, any>,
    message: string,
    status: number
  }

  const route = useRoute();
  const { messageError } = useMessage();
  const {  emit } = useEventBus();
  let app: any;

  // 校验id是否为有效值
  const isValidId = (id: any): boolean => {
    if (!id) return false;
    if (id === 'undefined' || id === 'null') return false;
    if (typeof id === 'string' && id.trim() === '') return false;
    return true;
  };

  const loadScript = (src: string) => new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.onload = () => resolve(script);
    script.onerror = () => reject(new Error(`Failed to load script: ${src}`));
    document.head.appendChild(script);
  });

  const handleError = (_type: 'dashboard' | 'chart' | 'action' | 'others', err: Error) => {
    if (err.data.code === '9900403') {
      const iamResult = new IamApplyDataModel(err.data.data || {});
      // 页面展示没权限提示
      emit('permission-page', iamResult);
    } else {
      messageError(err.message);
    }
  };

  const init = async  () => {
    // 校验id是否有效
    if (!isValidId(route.params.id)) {
      console.warn('Invalid panel id:', route.params.id);
      return;
    }

    try {
      await loadScript('https://staticfile.qq.com/bkvision/pbb9b207ba200407982a9bd3d3f2895d4/latest/main.js');
      app = await window.BkVisionSDK.init(
        '#panel',
        route.params.id,
        {
          apiPrefix: `${window.PROJECT_CONFIG.AJAX_URL_PREFIX}/bkvision/`,
          chartToolMenu: [
            { type: 'tool', id: 'fullscreen', build_in: true },
            { type: 'tool', id: 'refresh', build_in: true },
            { type: 'menu', id: 'excel', build_in: true },
          ],
          handleError,
        },
      );
    } catch (error) {
      console.error(error);
    }
  };

  watch(() => route, () => {
    // 增加更严谨的id校验
    if (isValidId(route.params.id) && route.name === 'statementManageDetail') {
      nextTick(() => {
        if (app) {
          app.unmount();
        }
        init();
      });
    }
  }, {
    deep: true,
    immediate: true,
  });

</script>
