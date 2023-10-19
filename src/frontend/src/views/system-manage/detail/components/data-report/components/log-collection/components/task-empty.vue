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
  <div class="no-task">
    <img
      src="/static/images/empty.svg"
      style="height: 100px; margin-top: 22px;">
    <div style="font-size: 14px;">
      {{ t('暂无任务') }}，
      <router-link
        :to="{
          name: 'collectorCreate',
          params: {
            systemId: route.params.id
          }
        }">
        {{ t('立即新建') }}
      </router-link>
    </div>
    <!-- <div>
      <router-link
        :to="{
          name: 'collectorCreate',
          params: {
            systemId: route.params.id
          }
        }">
        {{ t('新建采集') }}
      </router-link>
    </div> -->
  </div>
</template>
<script setup lang="ts">
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  const { t } = useI18n();
  const route = useRoute();
</script>
<style lang="postcss" scoped>
  .no-task {
    min-height: 300px;
    font-size: 12px;
    line-height: 22px;
    color: #63656e;
    text-align: center;
  }
</style>
