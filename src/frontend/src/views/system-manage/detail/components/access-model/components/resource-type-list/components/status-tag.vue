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
    v-bk-tooltips="{
      content: statusMsg,
      disabled: status !== 'failed' || !statusMsg
    }"
    class="status-tag"
    :style="styles">
    {{ renderText }}
  </div>
</template>
<script setup lang="ts">
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Props{
    status: 'failed' | 'preparing' | 'running' | 'closed',
    statusMsg: string,
  }
  const props = defineProps<Props>();

  const { t } = useI18n();

  const statusStyle = {
    closed: {
      background: '#F0F1F5',
      color: '#979BA5',
    },
    preparing: {
      background: '#E1ECFF',
      color: '#3A84FF',
    },
    failed: {
      background: '#FFEEEE',
      color: '#EA3636',
    },
    running: {
      background: '#E5F6EA',
      color: '#3FC06D',
    },
  };

  const renderText = computed(() => {
    const textMap = {
      closed: t('停用'),
      running: t('启用'),
      preparing: t('启用中'),
      failed: t('启用失败'),
    } as Record<string, string>;

    return textMap[props.status];
  });

  const styles = computed(() => statusStyle[props.status] || { background: '#E5F6EA', color: '#3FC06D' });

</script>
<style lang="postcss" scoped>
  .status-tag {
    display: inline-block;
    padding: 2px 4px;
    font-weight: bold;
    line-height: 16px;
    text-align: center;
    border-radius: 2px;
  }
</style>
