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
  <bk-dialog
    v-model:is-show="localVisible"
    :title="t('最新数据样本')"
    width="960">
    <template #header>
      <div class="sample-dialog-header">
        <span class="sample-dialog-title">{{ t('最新数据样本') }}</span>
        <span class="sample-dialog-subtitle">{{ subtitle }}</span>
      </div>
    </template>
    <div class="sample-dialog-body">
      <scene-table
        :columns="sampleTableColumns"
        :data="data"
        :limit="10"
        :limit-list="[10, 20, 50]"
        :max-height="480"
        show-pagination />
    </div>
    <template #footer />
  </bk-dialog>
</template>

<script setup lang="ts">
  import {
    computed,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import SceneTable from './scene-table.vue';

  const props = defineProps<{
    isShow: boolean;
    subtitle: string;
    data: Array<{ fieldName: string; fieldLabel: string; value: string }>;
  }>();

  const emit = defineEmits<{
    'update:isShow': [value: boolean];
  }>();

  const { t } = useI18n();

  const localVisible = computed({
    get: () => props.isShow,
    set: (val: boolean) => emit('update:isShow', val),
  });

  const sampleTableColumns = [
    {
      colKey: 'fieldName',
      title: () => t('字段名'),
      width: 200,
    },
    {
      colKey: 'fieldLabel',
      title: () => t('字段中文名'),
      width: 200,
    },
    {
      colKey: 'value',
      title: () => t('值'),
    },
  ];
</script>

<style lang="postcss" scoped>
  .sample-dialog-header {
    display: flex;
    align-items: center;
  }

  .sample-dialog-title {
    font-size: 20px;
    font-weight: 700;
    color: #313238;
  }

  .sample-dialog-subtitle {
    padding-left: 12px;
    margin-left: 12px;
    font-size: 14px;
    color: #979ba5;
    border-left: 1px solid #dcdee5;
  }

  .sample-dialog-body {
    padding: 0;
  }
</style>
