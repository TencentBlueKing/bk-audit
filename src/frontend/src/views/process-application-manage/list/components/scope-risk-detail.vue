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
  <div style="padding: 24px 32px;">
    <render-list
      ref="scopeListRef"
      :border="['row']"
      class="audit-highlight-table mt16 rule-table"
      :columns="scopeTableColumn"
      :data-source="scopeRiskDataSource" />
  </div>
</template>

<script setup lang='tsx'>
  import {
    onMounted,
    ref,
  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';

  import ProcessApplicationManageService from '@service/process-application-manage';

  import type ProcessApplicationManageModel from '@model/application/application';

  import Tooltips from '@components/show-tooltips-text/index.vue';

  interface Props{
    data: ProcessApplicationManageModel
  }
  const props = defineProps<Props>();
  const scopeRiskDataSource = ProcessApplicationManageService.fetchRuleList;
  const { t } = useI18n();
  const scopeListRef = ref();
  const scopeTableColumn = [
    {
      label: () => t('规则ID'),
      field: () => 'rule_id',
      render: ({ data }: { data: { rule_id: string } }) => <Tooltips data={data.rule_id} />,
      sort: 'custom',
    },
    {
      label: () => t('规则名称'),
      field: () => 'name',
      sort: 'custom',
      render: ({ data }: { data: { name: string, rule_id: number,} }) => {
        const to = {
          name: 'ruleManageList',
          query: {
            rule_id: data.rule_id,
          },
        };
        return <router-link to = {to} target='_blank'>
          <Tooltips data={data.name} />
        </router-link>;
      },
    },
    {
      label: () => t('规则状态'),
      field: () => 'is_enabled',
      render: ({ data }: { data: { is_enabled: string } }) => (
        <bk-tag type={data.is_enabled ? 'success' : ''}>{data.is_enabled ? t('启用') : t('停用')}</bk-tag>
      ),
    },
  ];

  onMounted(() => {
    if (!props.data) return;
    scopeListRef.value.fetchData({
      id: props.data.id,
      page: 1,
    });
  });
</script>
<style scoped lang="postcss">
.rule-table :deep(thead th) {
  background-color: #f5f7fa;
}
</style>
