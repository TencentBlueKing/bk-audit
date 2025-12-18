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
  <div class="perimission-page">
    <div class="perimission-page-container">
      <render-result :data="data" />
      <div class="perimission-page-footer">
        <bk-button
          v-if="!isApplyed"
          :disabled="data.hasPermission"
          theme="primary"
          @click="handleGoApply">
          {{ t('去申请') }}
        </bk-button>
        <bk-button
          v-else
          theme="primary"
          @click="handleApplyed">
          {{ t('已申请') }}
        </bk-button>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import {
    Button as BkButton,
  } from 'bkui-vue';
  import {
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type ApplyDataModel from '@model/iam/apply-data';

  import RenderResult from './render-result.vue';

  interface Props {
    data: ApplyDataModel
  }

  const props = defineProps<Props>();
  const { t } = useI18n();

  const isApplyed = ref(false);

  const handleGoApply = () => {
    isApplyed.value = true;
    window.open(props.data.apply_url, '_blank');
  };

  const handleApplyed = () => {
    window.location.reload();
  };

</script>
<style lang="postcss" scoped>
  .perimission-page {
    display: flex;
    align-items: center;
    height: 100%;

    .perimission-page-container {
      width: 768px;
      padding: 24px;
      margin: 60px auto;
      background-color: #fff;
      border-radius: 2px;
      box-shadow: 0 1px 2px 0 rgb(0 0 0 / 5%);
    }

    .perimission-page-footer {
      margin: 24px auto 6px;
      text-align: center;
    }
  }
</style>
