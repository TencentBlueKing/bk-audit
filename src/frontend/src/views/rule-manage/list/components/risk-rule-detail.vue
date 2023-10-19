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
  <bk-loading :loading="detailLoading || applicationListLoading || fieldLoading || strategyListLoading">
    <div class="riskrule-detail-wrap">
      <render-info-block>
        <render-info-item :label="t('规则ID')">
          {{ data.rule_id }}
        </render-info-item>
      </render-info-block>
      <render-info-block>
        <render-info-item :label="t('规则名称')">
          {{ data.name }}
        </render-info-item>
      </render-info-block>
      <render-info-block>
        <render-info-item
          class="condition-render-item"
          :label="t('适用范围')">
          <div
            v-for="(item,index) in data.scope"
            :key="index"
            class="condition-item">
            <div
              v-if="index"
              class="condition-equation mr4 mb4">
              AND
            </div>
            <div class="condition-key mr4 mb4">
              {{ riskFieldMap[item.field] || item.field }}
            </div>
            <div class="condition-method mr4 mb4">
              {{ item.operator }}
            </div>
            <div
              v-for="(value, valIndex) in item.value"
              :key="valIndex"
              class="condition-value mr4 mb4">
              {{ item.field==='strategy_id'
                ? strategyList.find(sItem=>sItem.value.toString() === value.toString())?.label || value
                : value }}
            </div>
          </div>
        </render-info-item>
      </render-info-block>
      <render-info-block>
        <render-info-item :label="t('优先级')">
          {{ data.priority_index }}
        </render-info-item>
      </render-info-block>

      <render-info-block>
        <render-info-item :label="t('处理套餐')">
          {{ processApplication || '--' }}
        </render-info-item>
      </render-info-block>

      <render-info-block>
        <render-info-item :label="t('套餐参数')">
          <div
            v-if="Object.values(paramsDetailData).length"
            style="padding: 16px 12px;background: rgb(245 247 250 / 100%)">
            <render-info-item
              v-for="item in Object.values(paramsDetailData)"
              :key="item.key"
              :label="item.name">
              {{ riskFieldMap[data.pa_params[item.key].field] || data.pa_params[item.key].field }}
            </render-info-item>
          </div>
          <span v-else>--</span>
        </render-info-item>
      </render-info-block>

      <render-info-block>
        <render-info-item :label="t('自动关单')">
          {{ data.auto_close_risk ? t('套餐执行成功后自动关单') : '--' }}
        </render-info-item>
      </render-info-block>
    </div>
  </bk-loading>
</template>

<script setup lang='ts'>
  import {
    computed,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ProcessApplicationManageService from '@service/process-application-manage';
  import RiskManageService from '@service/risk-manage';
  import SoapManageService from '@service/soap-manage';
  import StrategyManageService from '@service/strategy-manage';

  import type RiskRuleManageModel from '@model/risk-rule/risk-rule';

  import useRequest from '@hooks/use-request';

  import RenderInfoBlock from '@views/strategy-manage/list/components/render-info-block.vue';
  import RenderInfoItem from '@views/strategy-manage/list/components/render-info-item.vue';

  interface Props{
    data: RiskRuleManageModel
  }
  const props = defineProps<Props>();

  const { t } = useI18n();
  const riskFieldMap = ref<Record<string, string>>({});

  const processApplication = computed(() => {
    if (!props.data) return '';
    const params = processApplicationList.value
      .find(item => item.id === props.data.pa_id);
    if (params) {
      fetchDetail({
        id: params.sops_template_id,
      });
    }
    return params?.name;
  });

  // 获取所有策略列表
  const {
    run: fetchAllStrategyList,
    data: strategyList,
    loading: strategyListLoading,
  } = useRequest(StrategyManageService.fetchAllStrategyList, {
    defaultValue: [],
  });
  // 获取处理套餐列表
  const {
    data: processApplicationList,
    loading: applicationListLoading,
  } = useRequest(ProcessApplicationManageService.fetchApplicationsAll, {
    defaultValue: [],
    manual: true,
  });

  //  获取风险可用字段
  const {
    loading: fieldLoading,
  } = useRequest(RiskManageService.fetchFields, {
    defaultValue: [],
    manual: true,
    onSuccess(data) {
      riskFieldMap.value = data.reduce((res, item) => {
        res[item.id] = item.name;
        return res;
      }, {} as Record<string, string>);
    },
  });
  // 获取处理套餐详情
  const {
    run: fetchDetail,
    loading: detailLoading,
    data: paramsDetailData,
  } = useRequest(SoapManageService.fetchDetail, {
    defaultValue: {},
  });
  watch(() => props.data, () => {
    if (props.data && props.data.scope) {
      props.data.scope.forEach(({ field }:{field: string}) => {
        if (field === 'strategy_id') {
          fetchAllStrategyList();
        }
      });
    }
  }, {
    immediate: true,
  });
</script>
<style scoped lang="postcss">
.riskrule-detail-wrap{
  padding: 24px 32px;

  .mr4{
    margin-right: 4px;
  }

  .mb4{
    margin-bottom: 4px;
  }

  .scope-render-item {
    .info-label{
      margin-top:2px;
    }
  }

  .condition-item:last-child {
    /* margin-top: -2px; */
    margin-bottom: 0;
  }

  .condition-item {
    display: flex;
    margin-bottom: 8px;
    flex-wrap: wrap;

    .condition-equation {
      padding: 2px 8px;
      color: #3a84ff;
      text-align: center;
      background: #edf4ff;
      border-radius: 2px;
    }

    .condition-key {
      padding: 2px 8px;
      color: #788779;
      background: #dde9de;
      border-radius: 2px;
    }

    .condition-method {
      padding: 2px 8px;
      color: #fe9c00;
      background: #fff1db;
      border-radius: 2px;
    }

    .condition-value {
      padding: 2px 8px;
      color: #63656e;
      background: #f0f1f5;
      border-radius: 2px;
    }
  }

}
</style>
