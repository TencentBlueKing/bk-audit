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
  <collapse-box v-if="data.length > 0">
    <template #title>
      <div>{{ t('已选') }}<span class="number">{{ data.length }}</span>{{ t('个') }}{{ t('节点') }}</div>
    </template>
    <template #action>
      <collapse-extend-action>
        <div @click="handlRemoveAll">
          {{ t('移除所有') }}
        </div>
      </collapse-extend-action>
    </template>
    <div>
      <callapse-content-item
        v-for="(item, index) in data"
        :key="index"
        @remove="handleRemove(item)">
        {{ item.node_path }}
      </callapse-content-item>
    </div>
  </collapse-box>
</template>
<script setup lang="ts">
  import { useI18n } from 'vue-i18n';

  import type NodeInstanceStatusModel from '@model/biz/node-instance-status';

  import CallapseContentItem from './collapse-box/content-item.vue';
  import CollapseExtendAction from './collapse-box/extend-action.vue';
  import CollapseBox from './collapse-box/index.vue';

  interface Props {
    data: Array<NodeInstanceStatusModel>
  }
  interface Emits {
    (e: 'change', type: 'dynamicTopo', value: Array<any>): void
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { t } = useI18n();

  const handleRemove = (removeTarget:NodeInstanceStatusModel) => {
    const result = props.data.reduce((result, item) => {
      if (removeTarget !== item) {
        result.push(item);
      }
      return result;
    }, [] as Array<NodeInstanceStatusModel>);

    emits('change', 'dynamicTopo', result);
  };

  const handlRemoveAll = () => {
    emits('change', 'dynamicTopo', []);
  };
</script>
