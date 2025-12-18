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
  <bk-popover
    ext-cls="link-data-join-type"
    :is-show="isShow"
    placement="bottom"
    theme="light"
    trigger="click"
    @after-hidden="handleAfterShow"
    @after-show="handleAfterShow">
    <div class="join-type">
      <relation-ship
        active
        :join-type="joinType"
        type="gray" />
    </div>
    <template #content>
      <div
        v-for="type in joinTypeList"
        :key="type.value"
        class="join-type-list"
        :class="[type.value === joinType ? 'active' : '']"
        @click="() => handleSelectJoinType(type.value)">
        <relation-ship
          :active="type.value === joinType"
          :height="10"
          :join-type="type.value"
          style="margin-right: 5px;"
          type="gray"
          :width="10" />
        <span>{{ type.label }}</span>
      </div>
    </template>
  </bk-popover>
</template>
<script setup lang="ts">
  import { ref } from 'vue';

  interface Props {
    joinTypeList: Array<Record<string, any>>
  }

  defineProps<Props>();

  const joinType = defineModel<string>('joinType', {
    default: 'left_join',
  });

  const isShow = ref(false);

  const handleSelectJoinType = (type: string) => {
    joinType.value = type;
    isShow.value = false;
  };

  const handleAfterShow = (value: { isShow: boolean}) => {
    isShow.value = value.isShow;
  };
</script>
<style scoped lang="postcss">
  .join-type {
    display: flex;
    width: 46px;
    height: 32px;
    margin-bottom: 8px;
    cursor: pointer;
    background: #e1ecff;
    border: 1px solid #9bc0ff;
    border-radius: 4px;
    align-items: center;
    justify-content: center;
  }

  .join-type-list {
    display: flex;
    align-items: center;
    padding: 12px;
    cursor: pointer;

    &:hover {
      background-color: #f5f7fa;
    }
  }

  .active {
    color: #3a84ff;
    background-color: #e1ecff;
  }
</style>
<style>
.link-data-join-type {
  padding: 4px 0 !important;
}
</style>
