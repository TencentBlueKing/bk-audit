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
  <div class="risk-count-cell">
    <span>{{ count }}</span>
    <bk-popover
      ext-cls="risk-table-popover"
      placement="bottom-start"
      theme="light"
      trigger="click"
      @after-hidden="handleAfterHidden"
      @after-show="handleAfterShow">
      <audit-icon
        class="link-icon"
        type="jump-link"
        @click.stop />
      <template #content>
        <bk-loading :loading="loading">
          <div class="risk-table-popover-content">
            <bk-table
              :border="['outer', 'row']"
              :columns="riskTableColumns"
              :data="riskList"
              :max-height="320"
              size="small"
              width="300" />
          </div>
        </bk-loading>
      </template>
    </bk-popover>
  </div>
</template>

<script setup lang="tsx">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskManageService from '@service/risk-manage';

  import useRequest from '@hooks/use-request';

  import Tooltips from '@components/show-tooltips-text/index.vue';


  interface RiskItem {
    risk_id: string;
    title: string;
    risk_level: string;
  }

  interface Props {
    count: number;
    reportId: string | number;
  }

  const props = withDefaults(defineProps<Props>(), {});
  const loading = ref(true);
  const { t } = useI18n();

  const riskList = ref<RiskItem[]>([]);

  const riskTableColumns = [
    {
      label: t('风险ID'),
      field: 'risk_id',
      minWidth: 180,
      render: (args: { data?: RiskItem }) => {
        const { data } = args;
        if (!data) return '--';
        const to = {
          name: 'riskManageDetail',
          params: {
            riskId: data.risk_id,
          },
        };
        return <router-link to={to}>
          <Tooltips data={data.risk_id} />
        </router-link>;
      },
    },
    {
      label: t('风险标题'),
      field: 'title',
      minWidth: 160,
    },
    {
      label: t('风险等级'),
      field: 'risk_level',
      width: 100,

    },
  ];
  // 报告关联风险列表
  const {
    run: getReportRiskList,
  } = useRequest(RiskManageService.getReportRiskList, {
    defaultValue: [],
    onSuccess(data) {
      loading.value = false;
      riskList.value = data.results;
    },
  });
  const handleAfterShow = () => {
    console.log({
      report_id: props.reportId,
      page: 1,
      page_size: props.count === 0 ? 10 : props.count,
    });

    getReportRiskList({
      report_id: props.reportId,
      page: 1,
      page_size: props.count === 0 ? 10 : props.count,
    });
  };
  const handleAfterHidden = () => {
    riskList.value = [];
    loading.value = true;
  };
</script>

<style lang="postcss" scoped>
.risk-count-cell {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.link-icon {
  font-size: 12px;
  color: #3a84ff;
  cursor: pointer;
}

.risk-table-popover-content {
  width: 600px;
}

:deep(.risk-id-link) {
  color: #3a84ff;
  cursor: pointer;
}

:deep(.risk-id-link:hover) {
  text-decoration: underline;
}
</style>
