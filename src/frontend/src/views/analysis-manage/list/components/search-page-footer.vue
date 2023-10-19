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
  <div
    id="search-page-footer"
    class="search-page-footer">
    <div>
      <p>
        <a
          v-for="(item, index) in data.footer"
          :key="index"
          class="footer-content"
          :href="item.url"
          target="_blank">
          <span class="y-axis"> | </span>
          {{ item.text }}</a>
      </p>
    </div> <div>
      <p>{{ data.copyright }} {{ data.version }}</p>
    </div>
  </div>
</template>
<script setup lang="ts">
  import RootManageService from '@service/root-manage';

  import ConfigModel from '@model/root/config';

  import useRequest from '@hooks/use-request';

  const {
    data,
  } =  useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
  });
</script>
<style lang="postcss">
  .search-page-footer {
    position: fixed;
    right: 0;
    bottom: 0;
    left: 60px;
    display: flex;
    height: 52px;
    font-size: 12px;
    color: #63656e;
    background: #f5f6fa;
    background-color: #f5f6fa;
    border-top: 1px solid #dcdee5;
    align-items: center;
    flex-direction: column;
    justify-content: center;

    .y-axis {
      color: #63656e;
    }

    .footer-content:first-child .y-axis {
      display: none;
    }
  }

</style>
