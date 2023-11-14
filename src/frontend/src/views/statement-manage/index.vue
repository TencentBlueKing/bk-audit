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

  const route = useRoute();
  const loadScript = (src: string) => new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.onload = () => resolve(script);
    script.onerror = () => reject(new Error(`Failed to load script: ${src}`));
    document.head.appendChild(script);
  });

  const render = () => {
    window.BkVisionSDK.init(
      '#panel',
      route.params.id,
      {
        filter: {},
        waterMark: { content: 'bk-vision' },
        apiPrefix: `${window.PROJECT_CONFIG.AJAX_URL_PREFIX}/bkvision/`,
      },
    );
  };

  const init = async  () => {
    try {
      // 样式文件
      const link = document.createElement('link');
      link.href = '//staticfile.qq.com/bkvision/p8e3a7f52d95c45d795cb6f90955f2800/latest/main.css';
      link.rel = 'stylesheet';
      document.body.append(link);
      await loadScript('//staticfile.qq.com/bkvision/p8e3a7f52d95c45d795cb6f90955f2800/latest/chunk-vendors.js?v={{STATIC_VERSION}}');
      await loadScript('//staticfile.qq.com/bkvision/p8e3a7f52d95c45d795cb6f90955f2800/latest/chunk-bk-magic-vue.js?v={{STATIC_VERSION}}');
      await loadScript('//staticfile.qq.com/bkvision/p8e3a7f52d95c45d795cb6f90955f2800/latest/main.js?v={{STATIC_VERSION}}');
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
