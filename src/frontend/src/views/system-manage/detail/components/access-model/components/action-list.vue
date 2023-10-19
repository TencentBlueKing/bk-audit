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
  <div class="access-model-operation-list">
    <div style="margin-bottom: 16px; font-size: 14px;">
      {{ t('操作') }}
    </div>
    <bk-loading :loading="loading">
      <bk-table
        :border="['outer']"
        :columns="tableColumn"
        :data="data" />
    </bk-loading>
  </div>
</template>
<script setup lang="tsx">
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import MetaManageService from '@service/meta-manage';

  import type SystemActionModel from '@model/meta/system-action';

  import useRequest from '@hooks/use-request';

  const { t } = useI18n();
  const tableColumn = [
    {
      label: () => t('操作 ID'),
      field: () => 'action_id',
    },
    {
      label: () => t('操作事件名称'),
      render: ({ data }: {data: SystemActionModel}) => (
        data.description ? (
        <span
          class="tips"
          v-bk-tooltips={ t(data.description) }>
          {data.name}
        </span>)
          : (<span>{data.name}</span>)
      ),
    },
    {
      label: () => t('风险等级'),
      render: ({ data }: {data: SystemActionModel}) => (
        <render-sensitivity-level value={data.sensitivity} />
      ),
    },
    {
      label: () => t('操作事件类型'),
      showOverflowTooltip: true,
      render: ({ data }: {data: SystemActionModel}) => data.type || '--',
    },
  ];

  const route = useRoute();

  const {
    loading,
    data,
  }  = useRequest(MetaManageService.fetchSystemActionList, {
    defaultParams: {
      id: route.params.id,
    },
    defaultValue: [],
    manual: true,
  });
</script>
<style lang="postcss">
.access-model-operation-list {
  padding: 16px 24px;
  margin-top: 16px;
  color: #313238;
  background-color: #fff;
  border-radius: 2px;
  box-shadow: 0 1px 2px 0 rgb(0 0 0 / 16%);

  .sensitivity-tag {
    display: inline-block;
    height: 22px;
    padding: 0 10px;
    line-height: 22px;
    color: #ea3536;
    background: #feebea;
    border-radius: 2px;
  }

  .not-sensitivity-tag {
    display: inline-block;
    height: 22px;
    padding: 0 10px;
    line-height: 22px;
    color: #63656e;
    background: #f0f1f5;
    border-radius: 2px;
  }
}
</style>
