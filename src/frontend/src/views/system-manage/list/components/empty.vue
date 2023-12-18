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
    :style="{
      display: 'flex',
      'flex-direction': 'column',
      'justify-content': 'center',
      height: 'calc(100vh - 140px)',
      'text-align': 'center',
    }">
    <img
      src="@images/empty.svg"
      style="height: 200px; margin-top: -100px;">
    <div
      style="margin-top: 8px; font-size: 24px; line-height: 32px; color: #63656e;">
      暂无应用系统
    </div>
    <div style="margin-top: 16px; font-size: 14px; line-height: 22px; color: #979ba5;">
      <span>相关流程，请查阅 </span>
      <a href="/">文档</a>
    </div>
  </div>
</template>
<script setup lang="ts">
</script>
