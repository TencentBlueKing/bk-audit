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
  <span
    aria-hidden="true"
    class="select-checkbox-loading">
    <i />
    <i />
    <i />
  </span>
</template>

<style lang="postcss" scoped>
  .select-checkbox-loading {
    display: inline-flex;
    width: 16px;
    height: 16px;
    align-items: center;
    justify-content: center;
    gap: 2px;
    vertical-align: middle;
    flex-shrink: 0;
  }

  .select-checkbox-loading i {
    display: block;
    width: 3px;
    height: 3px;
    background-color: #3a84ff;
    border-radius: 50%;
    animation: select-checkbox-loading-bounce .9s infinite ease-in-out;
  }

  .select-checkbox-loading i:nth-child(2) {
    animation-delay: .15s;
  }

  .select-checkbox-loading i:nth-child(3) {
    animation-delay: .3s;
  }

  @keyframes select-checkbox-loading-bounce {
    0%,
    80%,
    100% {
      opacity: 35%;
      transform: scale(.85);
    }

    40% {
      opacity: 100%;
      transform: scale(1);
    }
  }
</style>
