<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<template>
  <div class="risk-discovery-rules">
    <template v-if="!detailLoading && displayRules.length">
      <div
        v-for="(rule, ruleIndex) in displayRules"
        :key="ruleIndex"
        class="rule-item-card">
        <div class="rule-item-header">
          <span class="rule-name">{{ rule.name }}</span>
        </div>
        <div class="rule-item-content">
          <div class="rule-field-row">
            <span class="rule-field-label">{{ t('命中条件') }}:</span>
            <div class="rule-field-value">
              <rule-condition-display
                :operator-map="operatorMap"
                :where="rule.where" />
            </div>
          </div>
          <div class="rule-field-row">
            <span class="rule-field-label">{{ t('风险单标题') }}:</span>
            <span class="rule-field-value">{{ rule.risk_title || '--' }}</span>
          </div>
          <div class="rule-field-row">
            <span class="rule-field-label">{{ t('命中等级') }}:</span>
            <span class="rule-field-value">
              <span
                v-if="rule.risk_level && riskLevelMap[rule.risk_level]"
                class="risk-level-tag"
                :style="{ backgroundColor: riskLevelMap[rule.risk_level].color }">
                {{ riskLevelMap[rule.risk_level].label }}
              </span>
              <span v-else>--</span>
            </span>
          </div>
          <div class="rule-field-row">
            <span class="rule-field-label">{{ t('风险危害') }}:</span>
            <span class="rule-field-value">{{ rule.risk_hazard || '--' }}</span>
          </div>
          <div class="rule-field-row">
            <span class="rule-field-label">{{ t('处理指引') }}:</span>
            <span class="rule-field-value">{{ rule.risk_guidance || '--' }}</span>
          </div>
          <template v-if="showRuleNoticeGroups">
            <div class="rule-field-row">
              <span class="rule-field-label">{{ t('风险单处理人') }}:</span>
              <span class="rule-field-value">
                {{ resolveGroupNames(rule.processor, userGroupList) }}
              </span>
            </div>
            <div class="rule-field-row">
              <span class="rule-field-label">{{ t('关注人') }}:</span>
              <span class="rule-field-value">
                {{ resolveGroupNames(rule.follower, userGroupList) }}
              </span>
            </div>
          </template>
        </div>
      </div>
    </template>
    <bk-exception
      v-else-if="!detailLoading"
      class="risk-discovery-rules-empty"
      scene="part"
      type="empty">
      {{ t('暂无风险发现规则') }}
    </bk-exception>
  </div>
</template>
<script setup lang="ts">
  import { computed, onMounted } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import StrategyManageService from '@service/strategy-manage';

  import CommonDataModel from '@model/strategy/common-data';
  import type StrategyModel from '@model/strategy/strategy';

  import useRequest from '@hooks/use-request';

  import RuleConditionDisplay from './rule-condition-display.vue';
  import { useStrategyDetailRules } from './use-strategy-detail-rules';

  import { isPlatformStrategyRoute } from '../../utils/strategy-routes';

  interface Props {
    data: StrategyModel,
    userGroupList: Array<{ id: number; name: string }>,
    detailLoading?: boolean,
  }

  const props = defineProps<Props>();
  const { t } = useI18n();
  const route = useRoute();

  const showRuleNoticeGroups = computed(() => !isPlatformStrategyRoute(route.name));

  const strategyData = computed(() => props.data);
  const {
    displayRules,
    riskLevelMap,
    resolveGroupNames,
  } = useStrategyDetailRules(strategyData);

  const {
    data: commonData,
    run: fetchStrategyCommon,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonDataModel(),
  });

  const operatorMap = computed(() => (
    commonData.value.rule_audit_condition_operator || []
  ).reduce((res, item) => {
    res[item.value] = item.label;
    return res;
  }, {} as Record<string, string>));

  onMounted(() => {
    fetchStrategyCommon();
  });
</script>
<style scoped lang="postcss">
.risk-discovery-rules {
  padding-top: 24px;
  background: #fff;

  .rule-item-card {
    margin-bottom: 12px;
    overflow: hidden;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px;

    &:last-child {
      margin-bottom: 0;
    }
  }

  .rule-item-header {
    display: flex;
    align-items: center;
    height: 40px;
    padding: 0 16px;
    background: #f0f1f5;
    border-bottom: 1px solid #dcdee5;
  }

  .rule-name {
    font-size: 14px;
    font-weight: 600;
    line-height: 22px;
    color: #313238;
  }

  .rule-item-content {
    padding: 16px 24px 20px;
    background: #fff;
  }

  .rule-field-row {
    display: flex;
    margin-bottom: 16px;
    line-height: 22px;

    &:last-child {
      margin-bottom: 0;
    }
  }

  .rule-field-label {
    flex: 0 0 100px;
    min-width: 100px;
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

  .risk-discovery-rules-empty {
    display: flex;
    min-height: 320px;
    align-items: center;
    justify-content: center;
  }
}
</style>
