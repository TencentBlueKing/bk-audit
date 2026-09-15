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
  <div class="config">
    <card-part-vue
      :is-open="false"
      :show-icon="false"
      :title="t('基础配置')">
      <template #content>
        <div>
          <audit-form
            ref="formRef"
            class="example"
            form-type="vertical"
            :model="formData"
            :rules="rules">
            <div class="base-form-item">
              <bk-form-item
                class="base-item"
                property="strategy_id"
                required>
                <template #label>
                  <span
                    v-bk-tooltips="t('手动创建风险单，事件字段来源于审计策略配置')"
                    class="dashed-underline">{{ t("审计策略") }}</span>
                </template>
                <bk-select
                  v-model="formData.strategy_id"
                  class="bk-select"
                  filterable
                  @change="handleStrategyChange">
                  <bk-option
                    v-for="item in strategyResults"
                    :id="item.strategy_id"
                    :key="item.strategy_id"
                    :disabled="item.status !== 'running'"
                    :name="`${item.strategy_name} (${item.strategy_id})`"
                    :popover-options="{ boundary: 'parent'}">
                    <bk-popover
                      v-if="item.status !== 'running'"
                      max-width="800px"
                      placement="top"
                      theme="light">
                      <div style="width: 100%;height: 100%; color: #c4c6cc;">
                        {{ `${item.strategy_name} (${item.strategy_id})` }}
                      </div>
                      <template #content>
                        <div>
                          {{ t('该策略已停用，暂不支持创建风险单') }}
                        </div>
                      </template>
                    </bk-popover>
                    <span v-else>
                      {{ `${item.strategy_name} (${item.strategy_id})` }}
                    </span>
                  </bk-option>
                </bk-select>
              </bk-form-item>

              <bk-form-item
                class="base-item"
                :label="t('风险发现规则')"
                property="strategy_rule_id"
                required>
                <bk-select
                  v-model="formData.strategy_rule_id"
                  class="bk-select"
                  :disabled="!formData.strategy_id"
                  filterable
                  :loading="strategyDetailLoading"
                  :placeholder="formData.strategy_id ? t('请选择') : t('请先选择审计策略')"
                  @change="handleRuleChange">
                  <bk-option
                    v-for="item in ruleOptions"
                    :id="item.id"
                    :key="item.id"
                    :name="item.name" />
                </bk-select>
              </bk-form-item>
            </div>

            <div
              v-if="selectedRule"
              class="rule-detail">
              <div class="rule-field-row">
                <span class="rule-field-label">{{ t('命中条件') }}:</span>
                <div class="rule-field-value">
                  <rule-condition-display
                    :operator-map="operatorMap"
                    :where="selectedRule.where" />
                </div>
              </div>
              <div class="rule-field-row">
                <span class="rule-field-label">{{ t('风险单标题') }}:</span>
                <span class="rule-field-value">{{ selectedRule.risk_title || '--' }}</span>
              </div>
              <div class="rule-field-row">
                <span class="rule-field-label">{{ t('命中等级') }}:</span>
                <span class="rule-field-value">
                  <span
                    v-if="selectedRule.risk_level && riskLevelMap[selectedRule.risk_level]"
                    class="risk-level-tag"
                    :style="{ backgroundColor: riskLevelMap[selectedRule.risk_level].color }">
                    {{ riskLevelMap[selectedRule.risk_level].label }}
                  </span>
                  <span v-else>--</span>
                </span>
              </div>
              <div class="rule-field-row">
                <span class="rule-field-label">{{ t('风险危害') }}:</span>
                <span class="rule-field-value">{{ selectedRule.risk_hazard || '--' }}</span>
              </div>
              <div class="rule-field-row">
                <span class="rule-field-label">{{ t('处理指引') }}:</span>
                <span class="rule-field-value">{{ selectedRule.risk_guidance || '--' }}</span>
              </div>
            </div>

            <div class="base-form-item">
              <bk-form-item
                class="base-item"
                :label="t('事件发生时间')"
                property="event_time"
                required>
                <bk-date-picker
                  v-model="formData.event_time"
                  append-to-body
                  clearable
                  type="datetime" />
              </bk-form-item>
            </div>
          </audit-form>
        </div>
      </template>
    </card-part-vue>
    <card-part-vue
      :is-open="false"
      :show-icon="false"
      :title="t('事件数据')">
      <template #content>
        <div
          v-if="!formData.strategy_id || eventList.length === 0"
          class="event-empty">
          <bk-exception
            scene="part"
            type="empty">
            <div>{{ t('暂无数据') }}</div>
            <div class="event-empty-tip">
              {{ formData.strategy_id ? t('该策略暂无事件数据字段') : t('请先选择审计策略') }}
            </div>
          </bk-exception>
        </div>
        <div
          v-else
          class="event-table">
          <div class="table-heard">
            <div class="table-index border-right">
              #
            </div>
            <div class="table-label border-right">
              <span class="table-text">{{ t('字段名称') }}</span>
            </div>
            <div class="table-type border-right">
              <span class="table-text">
                {{ t('表单类型') }}
              </span>
            </div>
            <div class="table-value">
              <span class="table-text">{{ t('字段值') }}
              </span>
            </div>
          </div>
          <div
            v-for="(item, index) in eventList"
            :key="index"
            class="table-list">
            <div class="table-index border-right">
              {{ index + 1 }}
            </div>
            <div
              class="table-label border-right field-type-box">
              <span
                v-bk-tooltips="{
                  content: item?.description,
                  disabled: item?.description === '',
                  placement: 'top'
                }"
                class="table-text"
                :class="item?.description !== '' ? 'dashed-underline' : '' ">
                <tool-tip-text
                  :data="`${item?.field_name}(${item?.display_name})`"
                  :line="1"
                  placement="top"
                  style="
                  padding: 0;
                  vertical-align: middle;
                  "
                  theme="light" />
              </span>
            </div>
            <div class="table-type border-right">
              <bk-select
                v-model="item.typeValue"
                behavior="simplicity"
                class="field-type-list"
                :filterable="false"
                style=" height: 100%;background-color: #fff;">
                <bk-option
                  v-for="type in item.fieldTypeList"
                  :id="type.typeValue"
                  :key="type.typeValue"
                  :name="type.label" />
              </bk-select>
            </div>
            <div class="table-value">
              <field-com
                :key="`${item.field_name}-${item.typeValue}`"
                ref="fieldComRef"
                :initial-value="item.valueText"
                :type="item.typeValue"
                @update="(val: any) => handlerUpdate(val, item)" />
            </div>
          </div>
        </div>
      </template>
    </card-part-vue>
  </div>
</template>

  <script lang="ts" setup>
  import { computed, nextTick, onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import CommonDataModel from '@model/strategy/common-data';

  import useRequest from '@hooks/use-request';

  import CardPartVue from '../../../scene-config/tool-manege/create-tool/components/card-part.vue';
  import RuleConditionDisplay from '../../../strategy-manage/list/components/rule-condition-display.vue';
  import {
    getRuleWhere,
    type RuleDisplayItem,
  } from '../../../strategy-manage/list/components/use-strategy-detail-rules';
  import { parseStrategyDetailToForm } from '../../../strategy-manage/strategy-create/utils/strategy-protocol';

  import fieldCom from './field-components.vue';

  import ToolTipText from '@/components/show-tooltips-text/index.vue';
  import { convertGMTTimeToStandard, convertToTimestamp } from '@/utils/assist/timestamp-conversion';

  interface Props {
    useAllStrategyList?: boolean;
  }

  interface Exposes{
    getEditData: () => void;
    handlerReturnData: (data: any) => void;
    validate: () => void;
  }
  interface Emits {
    (e: 'validateSuccess'): void
    (e: 'getselectedRiskValue', data: any): void
  }

  const props = withDefaults(defineProps<Props>(), {
    useAllStrategyList: false,
  });

  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const formData = ref({
    strategy_id: '' as string | number,
    strategy_rule_id: '' as string | number,
    event_time: new Date(),
  });
  const rules = {
    strategy_id: [{
      required: true,
      message: t('请选择审计策略'),
      trigger: 'change',
    }],
    strategy_rule_id: [{
      required: true,
      message: t('请选择风险发现规则'),
      trigger: 'change',
    }],
    event_time: [{
      required: true,
      message: t('请选择事件发生时间'),
      trigger: 'change',
    }],
  };
  const formRef = ref();
  const fieldComRef = ref();
  const eventList = ref<Array<Record<string, any>>>([]);
  const selectedRiskValue = ref<Record<string, any>>();
  const ruleOptions = ref<RuleDisplayItem[]>([]);
  const strategyDetailLoading = ref(false);

  const riskLevelMap: Record<string, { label: string; color: string }> = {
    HIGH: {
      label: t('高'),
      color: '#ea3636',
    },
    MIDDLE: {
      label: t('中'),
      color: '#ff9c01',
    },
    LOW: {
      label: t('低'),
      color: '#979ba5',
    },
  };

  const {
    data: commonData,
    run: fetchStrategyCommon,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonDataModel(),
    manual: true,
  });

  const operatorMap = computed(() => (
    commonData.value.rule_audit_condition_operator || []
  ).reduce((res, item) => {
    res[item.value] = item.label;
    return res;
  }, {} as Record<string, string>));

  const selectedRule = computed(() => ruleOptions.value.find(item => (
    String(item.id) === String(formData.value.strategy_rule_id)
  )));

  const buildEventList = (strategy: Record<string, any>) => {
    eventList.value = strategy?.event_data_field_configs?.map((item: Record<string, any>) => {
      let typeValueDefault = 'input';
      if (item.field_type === 'string') {
        typeValueDefault = 'input';
      }
      if (item.field_type === 'timestamp') {
        typeValueDefault = 'date-picker';
      }
      if (item.field_type === 'text') {
        typeValueDefault = 'textarea';
      }
      if (item.field_type === 'double' || item.field_type === 'float' || item.field_type === 'int' || item.field_type === 'long') {
        typeValueDefault = 'number-input';
      }
      return {
        ...item,
        typeValue: typeValueDefault,
        value: '',
        valueText: '',
        fieldTypeList: comTypeList(item.field_type),
      };
    }).filter((e: Record<string, any>) => e.is_show) || [];
  };

  const resolveRuleOptions = (strategy: Record<string, any>): RuleDisplayItem[] => {
    const parsed = parseStrategyDetailToForm(strategy);
    let ruleList: Array<Record<string, any>> = [];
    if (parsed.rules?.length) {
      ruleList = parsed.rules;
    } else if (Array.isArray(strategy.rules)) {
      ruleList = strategy.rules;
    }
    return ruleList.map((rule: Record<string, any>, index: number) => {
      const realId = rule.id ?? rule.rule_id ?? rule.strategy_rule_id;
      return {
        id: realId ?? `temp_${index}`,
        name: rule.rule_name || rule.name || `${t('规则')}${index + 1}`,
        where: getRuleWhere(rule),
        risk_title: rule.risk_title ?? strategy.risk_title ?? '',
        risk_level: rule.risk_level ?? strategy.risk_level ?? '',
        risk_hazard: rule.risk_hazard ?? strategy.risk_hazard ?? '',
        risk_guidance: rule.risk_guidance ?? strategy.risk_guidance ?? '',
        processor: rule.processor ?? [],
        follower: rule.follower ?? [],
      };
    });
  };

  const applySelectedStrategy = (strategy: Record<string, any> | undefined, keepRuleId = false) => {
    selectedRiskValue.value = strategy;
    buildEventList(strategy || {});
    ruleOptions.value = strategy ? resolveRuleOptions(strategy) : [];
    if (!keepRuleId) {
      formData.value.strategy_rule_id = '';
    }
    if (keepRuleId && formData.value.strategy_rule_id) {
      syncSelectedRuleToStrategy();
    }
  };

  const syncSelectedRuleToStrategy = () => {
    if (!selectedRiskValue.value || !selectedRule.value) {
      return;
    }
    selectedRiskValue.value = {
      ...selectedRiskValue.value,
      risk_title: selectedRule.value.risk_title,
      risk_level: selectedRule.value.risk_level,
      risk_hazard: selectedRule.value.risk_hazard,
      risk_guidance: selectedRule.value.risk_guidance,
    };
  };

  const loadStrategyDetail = async (strategyId: string | number, keepRuleId = false) => {
    strategyDetailLoading.value = true;
    try {
      const strategy = await StrategyManageService.fetchStrategyInfo({
        strategy_id: Number(strategyId),
      });
      applySelectedStrategy(strategy, keepRuleId);
    } finally {
      strategyDetailLoading.value = false;
    }
  };

  const handleStrategyChange = (value: string | number) => {
    formData.value.strategy_rule_id = '';
    ruleOptions.value = [];
    eventList.value = [];
    selectedRiskValue.value = undefined;
    if (!value) {
      return;
    }
    loadStrategyDetail(value);
  };

  const handleRuleChange = () => {
    syncSelectedRuleToStrategy();
  };

  const typeList = ref([
    {
      label: t('输入框'),
      value: 'input',
      typeValue: 'input',
    },
    {
      label: t('时间选择器'),
      value: 'date-picker',
      typeValue: 'date-picker',
    },
    {
      label: t('数字输入框'),
      value: 'number-input',
      typeValue: 'number-input',
    },
    {
      label: t('人员选择器'),
      value: 'user-selector',
      typeValue: 'user-selector',
    },
    {
      label: t('文本框'),
      value: 'textarea',
      typeValue: 'textarea',
    },
  ]);

  const comTypeList = (type: string) => {
    if (type === 'string') { // 字符串
      return typeList.value.filter((item: Record<string, any>) => item.value === 'input' || item.value === 'user-selector' || item.value === 'date-picker');
    } if (type === 'double' || type === 'float' || type === 'int' || type === 'long') { // 数字
      return typeList.value.filter((item: Record<string, any>) => item.value === 'number-input' || item.value === 'date-picker');
    } if (type === 'text') { // 文本
      return typeList.value.filter((item: Record<string, any>) => item.value === 'textarea');
    } if (type === 'timestamp') { // 时间
      return typeList.value.filter((item: Record<string, any>) => item.value === 'date-picker');
    }
    return typeList.value;
  };

  const strategyResults = ref<Array<Record<string, any>>>([]);

  const loadStrategyList = async () => {
    if (props.useAllStrategyList) {
      const data = await StrategyManageService.fetchAllStrategyList({});
      strategyResults.value = (data || []).map((item: { label: string; value: number; status?: string }) => ({
        strategy_id: item.value,
        strategy_name: item.label,
        status: item.status || 'running',
      }));
      return;
    }
    const data = await StrategyManageService.fetchStrategyList({
      strategy_type: 'rule',
    });
    strategyResults.value = data?.results || [];
  };

  const handlerUpdate = (value: any, item: any) => {
    let valueText: string | number | null = null;
    if ((item.field_type === 'long' || item.field_type === 'double' || item.field_type === 'float' || item.field_type === 'int')
      && item.typeValue === 'date-picker') {
      valueText = convertToTimestamp(value);
    } else if (item.typeValue === 'user-selector') {
      valueText = value.join(',');
    } else if (item.typeValue === 'number-input' && value !== '' && value !== null && value !== undefined) {
      valueText = Number(value);
    } else {
      valueText = value;
    }
    const target = eventList.value.find((eventItem: any) => (
      eventItem.field_name === item.field_name && eventItem.display_name === item.display_name
    ));
    if (!target) {
      return;
    }
    target.valueText = value;
    target.value = valueText;
  };

  // 表单验证
  const validate = () => {
    formRef.value.validate().then(() => {
      emits('validateSuccess');
    });
  };

  onMounted(() => {
    loadStrategyList();
    fetchStrategyCommon();
  });

  defineExpose<Exposes>({
    // 获取编辑数据
    getEditData() {
      return {
        formData: { ...formData.value, event_time: convertGMTTimeToStandard(formData.value.event_time)  },
        eventData: eventList.value,
        selectedRiskValue: selectedRiskValue.value,
        selectedRule: selectedRule.value,
      };
    },
    // 回显数据
    handlerReturnData(data: any) {
      nextTick(() => {
        formData.value = {
          ...data.formData,
          strategy_rule_id: data.formData.strategy_rule_id ?? '',
        };
        const cachedEventData = data.eventData;
        selectedRiskValue.value = data.selectedRiskValue;
        loadStrategyList().then(() => loadStrategyDetail(data.formData.strategy_id, true).then(() => {
          if (cachedEventData?.length) {
            eventList.value = cachedEventData;
          }
        }));
      });
    },
    validate() {
      validate();
    },
  });
  </script>

  <style lang="postcss" scoped>
    .config {
      width: 96%;
      margin-top: 20px;
      margin-left: 2%;

      /* background-color: #f5f7fa; */
      overflow: hidden;

      .base-form-item {
        display: flex;
        justify-content: space-between;

        .base-item {
          width: 48%;
        }
      }

      .dashed-underline {
        padding-bottom: 2px;

        /* 可选，增加文字和虚线间距 */
        border-bottom: 1px dashed #c4c6cc;
      }
    }

    .rule-detail {
      padding: 16px 20px;
      margin-bottom: 16px;
      background: #f5f7fa;
      border-radius: 2px;

      .rule-field-row {
        display: flex;
        margin-bottom: 12px;
        line-height: 22px;

        &:last-child {
          margin-bottom: 0;
        }
      }

      .rule-field-label {
        flex: 0 0 80px;
        min-width: 80px;
        color: #979ba5;
        text-align: right;
      }

      .rule-field-value {
        flex: 1;
        padding-left: 14px;
        color: #63656e;
        word-break: break-all;
      }

      .risk-level-tag {
        display: inline-block;
        min-width: 24px;
        padding: 2px 8px;
        font-size: 12px;
        line-height: 18px;
        color: #fff;
        text-align: center;
        border-radius: 2px;
      }
    }

    .event-empty {
      padding: 24px 0;

      .event-empty-tip {
        margin-top: 8px;
        font-size: 12px;
        color: #979ba5;
      }
    }

    .event-table {
      width: 96%;
      margin-top: 20px;
      margin-left: 2%;
      border: 1px solid #dcdee5;

      .border-right {
        border-right: 1px solid #dcdee5;
      }

      .field-type-box {
        display: flex;
      }

      .table-text {
        padding: 0 10px;
        line-height: 42px;
      }

      .table-heard {
        display: flex;
        height: 42px;
        line-height: 42px;
        background: #f5f7fa;
        border-bottom: 1px solid #dcdee5;
      }

      .table-list {
        display: flex;
        height: 42px;
        line-height: 42px;
        border-bottom: 1px solid #dcdee5;
      }

      .table-index {
        width: 32px;
        text-align: center;
      }

      .table-label {
        width: 270px;
      }

      .table-type {
        width: 140px;
      }

      .table-value {
        display: flex;
        width: 250px;
        height: auto;
        line-height: normal;
        flex: 1;
        align-items: center;
        justify-content: center;
      }

      .table-info-fill {
        font-size: 12px;
        color: #c4c6cc;
      }

      .event-type {
        height: 22px;
        padding: 5px 10px;
        margin-left: 10px;
        font-size: 12px;
        color: #1768ef;
        background: #e1ecff;
        border-radius: 12px;
      }

      .trigger {
        display: flex;
        margin-right: 10px;
        margin-left: 10px;
        font-size: 12px;
        line-height: 0px;
        letter-spacing: 0;
        color: #63656e;
        cursor: pointer;
        align-items: center;
        justify-content: space-between;
      }
    }

    .field-type {
      height: 20px;
      padding: 1px 5px;
      margin-top: 12px;
      margin-left: 5px;
      font-size: 12px;
      line-height: normal;
      color: #1768ef;
      background: #e1ecff;
      border-radius: 10px;
      align-items: center;
      justify-content: center;
    }

    .field-type-list {
      :deep(.bk-input) {
        border: none !important;
      }
    }
  </style>
