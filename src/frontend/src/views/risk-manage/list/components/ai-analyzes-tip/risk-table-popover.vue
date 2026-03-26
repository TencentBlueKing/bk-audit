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
    <bk-popover
      ext-cls="risk-table-popover"
      placement="bottom-start"
      theme="light"
      trigger="click"
      @after-hidden="handleAfterHidden"
      @after-show="handleAfterShow">
      <span class="risk-count">{{ count }}</span>
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
    <audit-icon
      class="link-icon"
      type="jump-link"
      @click.stop="handleClick" />
  </div>
</template>

<script setup lang="tsx">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import RiskManageService from '@service/risk-manage';
  import StrategyManageService from '@service/strategy-manage';

  import useRequest from '@hooks/use-request';

  import Tooltips from '@components/show-tooltips-text/index.vue';

  import RiskLevel from '@views/risk-manage/list/components/risk-level.vue';


  interface RiskItem {
    current_operator: Array<string>;
    event_end_time: string;
    event_time: string;
    operator: Array<string>;
    risk_id: string;
    risk_label: string;
    risk_level: string
    status: string;
    strategy_id: number;
    title: string;
  }

  interface Props {
    count: number;
    reportId: string | number;
  }

  const props = withDefaults(defineProps<Props>(), {});
  const router = useRouter();
  const loading = ref(true);
  const { t } = useI18n();

  const riskList = ref<RiskItem[]>([]);

  const riskTableColumns = [
    {
      label: t('风险ID'),
      field: 'risk_id',
      minWidth: 180,
      showOverflowTooltip: true,
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
      showOverflowTooltip: true,

    },
    {
      label: t('风险等级'),
      field: 'risk_level',
      width: 100,
      render: ({ data }: { data?: RiskItem }) => {
        if (!data) return '--';
        return <RiskLevel levelData={levelData.value} data={data}></RiskLevel>;
      },
    },
  ];
  const {
    data: levelData,
    run: fetchRiskLevel,
  } = useRequest(StrategyManageService.fetchRiskLevel, {
    defaultValue: {},
  });
  // 报告关联风险列表
  const {
    run: getReportRiskList,
  } = useRequest(RiskManageService.getReportRiskList, {
    defaultValue: [],
    onSuccess(data) {
      loading.value = false;
      // 空值保护，确保 riskList 始终为数组
      riskList.value = data?.results ?? [];
      // 获取对应风险等级（仅在有数据时请求）
      if (riskList.value.length > 0) {
        fetchRiskLevel({
          strategy_ids: riskList.value.map((item: RiskItem) => item.strategy_id).join(','),
        });
      }
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

  // 点击跳转图标，获取报告关联风险列表，提取所有 risk_id，新开标签页跳转到「所有风险」页面搜索
  const handleClick = () => {
    RiskManageService.getReportRiskList({
      report_id: props.reportId,
      page: 1,
      page_size: props.count === 0 ? 10 : props.count,
    }).then((data) => {
      const riskIds = (data?.results ?? []).map((item: RiskItem) => item.risk_id).join(',');
      if (riskIds) {
        const route = router.resolve({
          name: 'riskManageList',
          query: {
            risk_id: riskIds,
          },
        });
        window.open(route.href, '_blank');
      }
    });
  };
</script>

<style lang="postcss" scoped>
.risk-count-cell {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.risk-count {
  color: #63656e;
  text-decoration: underline;
  cursor: pointer;
  text-underline-offset: 2px;
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
