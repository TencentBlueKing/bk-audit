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
  <div class="preview-result">
    <div class="preview-result-header">
      {{ t('结果预览') }}
    </div>
    <bk-exception
      v-if="empty"
      class="result-empty"
      scene="part"
      type="empty" />
    <scroll-faker>
      <view-host
        :data="hostList"
        v-bind="$attrs" />
      <view-node
        :data="nodeList"
        v-bind="$attrs" />
      <view-service-template
        :data="serviceTemplateList"
        v-bind="$attrs" />
      <view-set-template
        :data="setTemplateList"
        v-bind="$attrs" />
    </scroll-faker>
  </div>
</template>
<script setup lang="ts">
  import { useI18n } from 'vue-i18n';

  import type HostInstanceStatusModel from '@model/biz/host-instance-status';
  import type NodeInstanceStatusModel from '@model/biz/node-instance-status';
  import type TemplateTopoModel from '@model/biz/template-topo';

  import ViewHost from './view-host.vue';
  import ViewNode from './view-node.vue';
  import ViewServiceTemplate from './view-service-template.vue';
  import ViewSetTemplate from './view-set-template.vue';

  interface Props {
    empty: boolean;
    hostList: Array<HostInstanceStatusModel>;
    nodeList: Array<NodeInstanceStatusModel>;
    serviceTemplateList: Array<TemplateTopoModel>;
    setTemplateList: Array<TemplateTopoModel>
  }

  defineProps<Props>();
  const { t } = useI18n();

</script>
<style lang="postcss">
  .preview-result {
    position: relative;
    height: 550px;

    .preview-result-header {
      padding: 8px 24px;
      font-size: 14px;
      line-height: 22px;
      color: #313238;
    }

    .result-empty {
      position: absolute;
      top: 50%;
      transform: translateY(-50%);
    }
  }
</style>
