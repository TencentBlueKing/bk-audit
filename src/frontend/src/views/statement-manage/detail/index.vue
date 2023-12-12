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
    onMounted,
    watch,
  } from 'vue';
  import {
    useRoute,
  } from 'vue-router';

  import IamApplyDataModel from '@model/iam/apply-data';

  import useMessage from '@hooks/use-message';

  import {
    permissionDialog,
  } from '@utils/assist';

  interface Error {
    data: Record<string, any>,
    message: string,
    status: number
  }

  const route = useRoute();
  const { messageError } = useMessage();

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
      // 弹框展示没权限提示
      permissionDialog(iamResult);
    } else {
      messageError(err.message);
    }
  };

  const render = () => {
    window.BkVisionSDK.init(
      '#panel',
      route.params.id,
      {
        apiPrefix: `${window.PROJECT_CONFIG.AJAX_URL_PREFIX}/bkvision/`,
        handleError,
      },
    );
  };

  const init = async  () => {
    try {
      // 样式文件
      const link = document.createElement('link');
      link.href = 'https://staticfile.qq.com/bkvision/p7e76e4518060411cb65c6bc2eaea9c03/latest/main.css?v=1701524891';
      link.rel = 'stylesheet';
      document.body.append(link);
      await loadScript('https://staticfile.qq.com/bkvision/p7e76e4518060411cb65c6bc2eaea9c03/latest/chunk-vendors.js?v=1701524891');
      await loadScript('https://staticfile.qq.com/bkvision/p7e76e4518060411cb65c6bc2eaea9c03/latest/chunk-bk-magic-vue.js?v=1701524891');
      await loadScript('https://staticfile.qq.com/bkvision/p7e76e4518060411cb65c6bc2eaea9c03/latest/main.js?v=1701524891');
      render();
    } catch (error) {
      console.error(error);
    }
  };

  watch(() => route, () => {
    if (route.params.id !== '' && route.name === 'statementManageDetail') {
      render();
    }
  }, {
    deep: true,
  });

  onMounted(() => {
    init();
  });
</script>
