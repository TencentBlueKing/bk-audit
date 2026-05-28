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
  <div class="tool-status-creating">
    <div class="tool-status-creating-icon">
      <audit-icon
        class="loading-icon"
        svg
        type="loading" />
    </div>
    <div class="tool-status-creating-text">
      {{ isEditMode ? t('工具正在更新中，请稍等...') : t('工具正在创建中，请稍等...') }}
    </div>
  </div>
</template>
<script setup lang='ts'>
  import { useI18n } from 'vue-i18n';

  interface Props {
    isEditMode: boolean;
  }

  defineProps<Props>();
  const { t } = useI18n();
</script>
<style lang="postcss" scoped>
.tool-status-creating {
  display: flex;
  height: 360px;
  background-color: #fff;
  flex-direction: column;
  justify-content: center;
  align-items: center;

  .tool-status-creating-icon {
    margin-bottom: 10px;
    font-size: 64px;
    color: blue;

    .loading-icon {
      animation: loading 1s linear infinite;
    }
  }
}

@keyframes loading {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

</style>
