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
    v-if="!showAddCount"
    class="custom-constant-trigger"
    @click="() => showAddCount = true">
    <audit-icon
      class="plus-icon"
      type="plus-circle" />
    <span>{{ t('自定义常量') }}</span>
  </div>
  <div
    v-else
    class="custom-constant-input">
    <bk-input
      v-model="inputValue"
      autofocus
      :placeholder="t('请输入')"
      @enter="confirmValue" />
    <audit-icon
      class="confirm-icon"
      type="check-line"
      @click="confirmValue" />
    <audit-icon
      class="cancel-icon"
      type="close"
      @click="() => showAddCount = false" />
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Props {
    onConfirm: (value: string) => void;
  }

  const props = defineProps<Props>();
  const { t } = useI18n();

  const showAddCount = ref(false);
  const inputValue = ref('');

  const confirmValue = () => {
    if (inputValue.value.trim()) {
      props.onConfirm(inputValue.value.trim());
    }
    showAddCount.value = false;
    inputValue.value = '';
  };
</script>

<style lang="postcss" scoped>
.custom-constant-trigger {
  color: #63656e;
  text-align: center;
  flex: 1;
  cursor: pointer;

  .plus-icon {
    margin-right: 5px;
    font-size: 14px;
    color: #979ba5;
  }
}

.custom-constant-input {
  display: flex;
  width: 100%;
  padding: 0 5px;
  align-items: center;

  .confirm-icon {
    padding: 0 5px;
    font-size: 15px;
    color: #2caf5e;
    cursor: pointer;
  }

  .cancel-icon {
    font-size: 15px;
    color: #c4c6cc;
    cursor: pointer;
  }
}
</style>
