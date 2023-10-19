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
  <bk-loading :loading="loading">
    <div class="collector-deploy-log">
      <scroll-faker>
        <!-- eslint-disable vue/no-v-html -->
        <pre
          class="deploy-log-content"
          v-html="data || '--'" />
      </scroll-faker>
    </div>
  </bk-loading>
</template>
<script setup lang="ts">
  import CollectorManageService from '@service/collector-manage';

  import useRequest from '@hooks/use-request';

  interface Props {
    collectorConfigId: number,
    instanceId: string
  }
  const props = defineProps<Props>();

  const {
    data,
    loading,
  // eslint-disable-next-line vue/no-setup-props-destructure
  } = useRequest(CollectorManageService.fetchCollectorTaskDetail, {
    defaultValue: '...',
    defaultParams: {
      collector_config_id: props.collectorConfigId,
      instance_id: props.instanceId,
    },
    manual: true,
  });
</script>
<style lang="postcss">
  .collector-deploy-log {
    height: calc(100vh - 60px);
    padding: 16px 24px;
    font-size: 12px;
    line-height: 22px;
    color: #c4c6cc;
    background: #242424;

    .deploy-log-content {
      word-wrap: break-word;
      white-space: pre-wrap;
    }
  }
</style>
