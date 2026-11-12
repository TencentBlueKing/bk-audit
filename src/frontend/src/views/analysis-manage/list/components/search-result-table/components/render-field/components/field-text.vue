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
  <div class="render-field-text">
    <div class="bk-theme-cell-tip text">
      <slot />
    </div>
  </div>
</template>

<style lang="postcss" scoped>
  .render-field-text {
    display: inline-flex;
    max-width: 100%;
    height: calc(var(--bk-theme-table-row-height) - var(--bk-theme-space-8) - var(--bk-theme-space-8));
    vertical-align: top;
    cursor: pointer;
    align-items: center;

    .text {
      max-width: 100%;
      overflow: hidden;
      font-size: var(--bk-theme-font-size-sm);
      line-height: var(--bk-theme-line-height-sm);
      color: var(--bk-theme-text-default);
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
</style>
