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
    class="diff-detail">
    <bk-button
      v-bk-tooltips="t('查看变更的Diff')"
      class="mr8"
      text
      theme="primary"
      @click.stop="handleDiffDetail">
      <audit-icon type="diff" />
    </bk-button>
    <audit-sideslider
      v-model:is-show="isShow"
      :quick-close="isClosed"
      :show-footer="false"
      :title="data.instance_name"
      :width="960">
      <diff-detail :data="data" />
    </audit-sideslider>
  </span>
</template>
<script setup lang="ts">
  import {
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import DiffDetail from './components/diff-detail.vue';

  interface Props {
    data: Record<string, any>;
  }

  defineProps<Props>();

  const { t } = useI18n();

  const isShow = ref(false);

  const isClosed = true;
  const handleDiffDetail = async () => {
    isShow.value = true;
  };
</script>
<style>
.diff-detail {
  position: absolute;
  left: -16px;
}

</style>
