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
  <div class="strategy-create-card-part">
    <div
      class="card-part-title">
      <slot name="title">
        <span>
          {{ title }}
        </span>
      </slot>
      <audit-icon
        v-if="showIcon"
        :type="isCollapse ? 'angle-line-up' : 'angle-line-down'"
        @click="handleChangeCollapse" />
    </div>

    <div
      v-show="showContent && !isCollapse"
      class="card-part-content">
      <slot name="content" />
    </div>
  </div>
</template>

<script setup lang='ts'>
  import {
    ref,
  } from 'vue';

  interface Props{
    title?: string,
    showContent?:boolean,
    showIcon?:boolean,
  }
  withDefaults(defineProps<Props>(), {
    showContent: true,
    showIcon: true,
    title: '',
  });

  const isCollapse = ref(false);

  const handleChangeCollapse = () => {
    isCollapse.value = !isCollapse.value;
  };
</script>

<style scoped lang="postcss">
.strategy-create-card-part {
  /* width: 82%; */
  margin-bottom: 16px;
  background: #FFF;
  border-radius: 2px;
  box-shadow: 0 1px 2px 0 #00000029;

  >.card-part-title {
    display: flex;
    height: 53px;
    padding:0 16px;

    /* font-family: PingFangSC-SNaNpxibold; */
    font-size: 14px;
    font-weight: 600;
    color: #313238;
    align-items: center;
    justify-content: space-between;

    >.audit-icon{
      cursor: pointer;
    }
  }

  >.card-part-content{
    padding:10px 16px 0;
    border-top: 1px solid #F0F1F5;
  }
}
</style>
