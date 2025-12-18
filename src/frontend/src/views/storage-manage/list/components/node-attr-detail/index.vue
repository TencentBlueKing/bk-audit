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
  <span>
    <span
      v-show="isShow"
      class="show-node-attr-detail-btn"
      @click="handleShowDialog">
      <audit-icon type="view" />
      查看实例列表
    </span>
    <bk-dialog
      v-model:isShow="isShowDialog"
      dialog-type="show"
      :quick-close="false"
      theme="primary"
      :title="title"
      :width="840">
      <bk-table
        :border="['outer']"
        :columns="columns"
        :data="data" />
    </bk-dialog>
  </span>
</template>
<script setup lang="ts">
  import {
    computed,
    ref,
  } from 'vue';

  import type NodeAttrModel from '@model/storage/node-attr';

  const props = defineProps<{
    data: Array<NodeAttrModel>
  }>();

  const isShow = computed(() => props.data.length > 0);
  const isShowDialog = ref(false);

  const columns = [
    {
      label: () => 'ID',
      field: () => 'id',
    },
    {
      label: () => 'Name',
      field: () => 'name',
    },
    {
      label: () => 'Host',
      field: () => 'ip',
    },
  ];

  const title = computed(() => {
    if (!isShow.value) {
      return '';
    }
    const { attr, value } = props.data[0];
    return `${attr}:${value}`;
  });

  const handleShowDialog = () => {
    isShowDialog.value = true;
  };
</script>
<style lang="postcss">
  .show-node-attr-detail-btn {
    display: inline-block;
    padding-left: 8px;
    font-size: 12px;
    color: #3a84ff;
    cursor: pointer;
  }
</style>
