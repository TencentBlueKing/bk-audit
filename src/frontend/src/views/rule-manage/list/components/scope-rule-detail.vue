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
      :data-source="scopeRiskDataSource"
      :need-empty-search-tip="false" />
  </div>
</template>

<script setup lang='tsx'>
  import type { Column } from 'bkui-vue/lib/table/props';
  import {
    onMounted,
    ref,
  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';

  import RiskRuleManageService from '@service/rule-manage';

  import type RiskRuleManageModel from '@model/risk-rule/risk-rule';

  import EditTag from '@components/edit-box/tag.vue';
  import Tooltips from '@components/show-tooltips-text/index.vue';
  // import useRequest from '@hooks/use-request';
  interface Props{
    data: RiskRuleManageModel
  }
  const props = defineProps<Props>();

  const scopeRiskDataSource = RiskRuleManageService.fetchScopeRisks;
  const { t } = useI18n();
  const scopeListRef = ref();
  const scopeTableColumn = [
    {
      label: () => t('风险ID'),
      field: () => 'risk_id',
      render: ({ data }: { data: { risk_id: string } }) => {
        const to = {
          name: 'riskManageDetail',
          params: {
            riskId: data.risk_id,
          },
        };
        return <router-link to={to} target='_blank'>
          <Tooltips data={data.risk_id} />
        </router-link>;
      },
    },
    {
      label: () => t('风险描述'),
      field: () => 'event_content',
      render: ({ data }: { data: {event_content: string} }) => <Tooltips data={data.event_content} />,
    },
    {
      label: () => t('责任人'),
      field: () => 'operator',
      render: ({ data }: { data: { operator: string[] } }) => <EditTag data={ data.operator} />,
    },
    {
      label: () => t('发现时间'),
      field: () => 'event_time',
      width: 180,
      render: ({ data }: { data: {event_time: string} }) => data.event_time || '--',
    },
  ] as Column[];
  onMounted(() => {
    if (!props.data) return;
    scopeListRef.value.fetchData({
      id: props.data.rule_id,
      page: 1,
    });
  });
</script>
<style scoped lang="postcss">
.rule-table :deep(thead th) {
  background-color: #f5f7fa;
}
</style>
