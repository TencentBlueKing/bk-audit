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
  <div class="job-plan">
    <bk-alert
      style="margin-bottom: 16px;"
      theme="info"
      title="消息的提示文字">
      <template #title>
        <span>
          {{ t('如需上报详细的资源数据，请参照') }}

          <a
            :href="configData.help_info.schema"
            target="_blank">{{ t('文档指引') }}</a>
        </span>
      </template>
    </bk-alert>
    <bk-loading :loading="loading">
      <bk-table
        :border="['outer']"
        :columns="tableColumn"
        :data="schemaData">
        <template #empty>
          <bk-exception
            scene="part"
            style="height: 280px;padding-top: 40px;color: #63656e;"
            type="empty">
            {{ t('暂无数据') }}
          </bk-exception>
        </template>
      </bk-table>
    </bk-loading>
  </div>
</template>
<script setup lang="tsx">
  import {
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
  } from 'vue-router';

  import MetaManageService from '@service/meta-manage';
  import RootManageService from '@service/root-manage';

  import ConfigModel from '@model/root/config';

  import useRequest from '@hooks/use-request';

  interface Props{
    data: Record<string, any>;
  }
  const props = defineProps<Props>();
  const { t } = useI18n();

  const tableColumn = [
    {
      label: () => t('字段 ID'),
      field: () => 'id',
    },
    {
      label: () => t('字段含义(中)'),
      field: () => 'description',
    },
    {
      label: () => t('字段含义(英)'),
      field: () => 'description_en',
    },
  ];
  const route = useRoute();
  const {
    loading,
    data: schemaData,
  // eslint-disable-next-line vue/no-setup-props-destructure
  } = useRequest(MetaManageService.fetchResourceTypeSchema, {
    defaultParams: {
      system_id: route.params.id,
      id: props.data.resource_type_id,
      resource_type_id: props.data.resource_type_id,
    },
    manual: true,
    defaultValue: [],
  });

  const {
    data: configData,
  } =  useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
  });
</script>
<style lang="postcss" scoped>
  .job-plan {
    padding: 28px 40px;
  }
</style>
