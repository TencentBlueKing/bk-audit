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
            class="pa-param-list">
            <render-info-item
              v-for="item in sortedParams"
              :key="item.key"
              class="pa-param-item"
              :label="item.name">
              <div
                v-if="shouldShowUserTags(item)"
                class="pa-param-user-tags">
                <span
                  v-for="(tag, tagIndex) in getUserTagValues(item.key)"
                  :key="`${tag}-${tagIndex}`"
                  class="pa-param-user-tag">
                  {{ tag }}
                </span>
                <span
                  v-if="!getUserTagValues(item.key).length"
                  class="pa-param-empty">--</span>
              </div>
              <span
                v-else-if="getFieldRefText(item.key)"
                class="pa-param-user-tag">
                {{ getFieldRefText(item.key) }}
              </span>
              <template v-else>
                {{ getParamDisplayText(item.key) }}
              </template>
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

  import {
    isParamFieldReference,
    resolveParamFieldReference,
  } from '@/utils/assist/pa-param-field-ref';

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

  const sortedParams = computed(() => (
    Object.values(paramsDetailData.value || {})
      .filter(item => item.show_type === 'show' && !item.is_hide)
      .sort((a, b) => (a.index || 0) - (b.index || 0))
  ));

  const getParamValue = (key: string) => props.data.pa_params?.[key];

  const getParamConfig = (key: string) => paramsDetailData.value?.[key];

  interface SelectOption {
    text: string;
    value: string | number;
  }

  const isFieldRef = (field: unknown): field is string => (
    typeof field === 'string' && field !== ''
  );

  const getKnownRiskFieldIds = () => Object.keys(riskFieldMap.value);

  const isFieldReference = (key: string) => {
    const param = getParamValue(key);
    const config = getParamConfig(key);
    if (!param || !config) {
      return false;
    }
    return isParamFieldReference(param, config.custom_type || '', getKnownRiskFieldIds());
  };

  const resolveFieldReferenceId = (param: { field?: unknown; value?: unknown }, key: string) => (
    resolveParamFieldReference(param, getParamConfig(key)?.custom_type || '', getKnownRiskFieldIds())
  );

  const getRiskFieldDisplayName = (fieldId: string) => (
    riskFieldMap.value[fieldId] || fieldId
  );

  const parseSelectOptions = (configItem: Record<string, any> | undefined): SelectOption[] => {
    if (!configItem) {
      return [];
    }
    try {
      const itemsText = configItem.value?.items_text
        || configItem.enum?.[0]?.items_text
        || configItem.form_schema?.items_text
        || (typeof configItem.value === 'string' && configItem.custom_type === 'select'
          ? configItem.value
          : '');
      if (!itemsText) {
        return [];
      }
      const parsed = typeof itemsText === 'string' ? JSON.parse(itemsText) : itemsText;
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  };

  const getSelectOptionText = (key: string, val: unknown) => {
    if (val === undefined || val === null || val === '') {
      return '';
    }
    const options = parseSelectOptions(getParamConfig(key));
    const matched = options.find(item => item.value?.toString() === String(val));
    return matched?.text ?? String(val);
  };

  const formatDisplayValue = (key: string, val: unknown) => {
    if (getParamConfig(key)?.custom_type === 'select') {
      return getSelectOptionText(key, val);
    }
    return String(val);
  };

  const normalizeToTagValues = (val: unknown): string[] => {
    if (Array.isArray(val)) {
      return val.map(item => String(item)).filter(Boolean);
    }
    if (val !== undefined && val !== null && val !== '') {
      return [String(val)];
    }
    return [];
  };

  const shouldShowUserTags = (item: { custom_type?: string; key: string }) => (
    item.custom_type === 'bk_user_selector' && !isFieldReference(item.key)
  );

  const getUserTagValues = (key: string): string[] => (
    normalizeToTagValues(getParamValue(key)?.value)
  );

  const getFieldRefText = (key: string) => {
    const param = getParamValue(key);
    if (!param || !isFieldReference(key)) {
      return '';
    }
    const fieldId = resolveFieldReferenceId(param, key)
      || (isFieldRef(param.field) ? param.field : '');
    return fieldId ? getRiskFieldDisplayName(fieldId) : '';
  };

  const getParamDisplayText = (key: string) => {
    const param = getParamValue(key);
    if (!param) {
      return '--';
    }
    if (isFieldReference(key)) {
      return getFieldRefText(key) || '--';
    }
    const { value } = param;
    if (value === undefined || value === null || value === '') {
      return '--';
    }
    if (Array.isArray(value)) {
      return value.map(val => formatDisplayValue(key, val)).join(', ');
    }
    return formatDisplayValue(key, value);
  };

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
    run: fetchFields,
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
    fetchFields();
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
.riskrule-detail-wrap {
  padding: 24px 32px;

  .mr4 {
    margin-right: 4px;
  }

  .mb4 {
    margin-bottom: 4px;
  }

  .scope-render-item {
    .info-label {
      margin-top: 2px;
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

  .pa-param-list {
    padding: 16px 12px;
    background: rgb(245 247 250 / 100%);

    :deep(.pa-param-item) {
      align-items: flex-start;
      margin-bottom: 12px;

      &:last-child {
        margin-bottom: 0;
      }

      .info-label {
        min-width: 180px;
        flex: 0 0 180px;
        line-height: 20px;
      }

      .info-value {
        overflow: visible;
        line-height: 20px;
        text-overflow: unset;
      }
    }
  }

  .pa-param-user-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .pa-param-user-tag {
    display: inline-flex;
    padding: 2px 8px;
    font-size: 12px;
    line-height: 20px;
    color: #63656e;
    background: #f0f1f5;
    border-radius: 2px;
  }

  .pa-param-empty {
    color: #63656e;
  }

}
</style>
