<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<template>
  <div class="risk-discovery-rules">
    <template v-if="!detailLoading && displayRules.length">
      <div
        v-for="(rule, ruleIndex) in displayRulesWithTags"
        :key="ruleIndex"
        class="rule-item-card">
        <div class="rule-item-header">
          <span class="rule-name">{{ rule.name }}</span>
        </div>
        <div class="rule-item-content">
          <div class="rule-field-row">
            <span class="rule-field-label">{{ t('命中条件') }}：</span>
            <div class="rule-field-value">
              <rule-condition-display
                :aggregate-list="aggregateList"
                :operator-map="operatorMap"
                :where="rule.where" />
            </div>
          </div>
          <div class="rule-field-row">
            <span class="rule-field-label">{{ t('风险单标题') }}：</span>
            <span class="rule-field-value">{{ rule.risk_title || '--' }}</span>
          </div>
          <div class="rule-field-row">
            <span class="rule-field-label">{{ t('命中等级') }}：</span>
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
            <span class="rule-field-label">{{ t('风险危害') }}：</span>
            <span class="rule-field-value multiline-text">{{ rule.risk_hazard || '--' }}</span>
          </div>
          <div class="rule-field-row">
            <span class="rule-field-label">{{ t('处理指引') }}：</span>
            <span class="rule-field-value multiline-text">{{ rule.risk_guidance || '--' }}</span>
          </div>
          <template v-if="showRuleNoticeGroups">
            <div class="rule-field-row">
              <span class="rule-field-label">{{ t('风险单处理人') }}：</span>
              <div class="rule-field-value notice-group-tags">
                <template v-if="rule.processorTags.length">
                  <bk-tag
                    v-for="item in rule.processorTags"
                    :key="`processor-${item.id}`"
                    class="notice-group-tag">
                    {{ item.name }}
                  </bk-tag>
                </template>
                <span v-else>--</span>
              </div>
            </div>
            <div class="rule-field-row">
              <span class="rule-field-label">{{ t('关注人') }}：</span>
              <div class="rule-field-value notice-group-tags">
                <template v-if="rule.followerTags.length">
                  <bk-tag
                    v-for="item in rule.followerTags"
                    :key="`follower-${item.id}`"
                    class="notice-group-tag">
                    {{ item.name }}
                  </bk-tag>
                </template>
                <span v-else>--</span>
              </div>
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

  import NoticeGroupManageService from '@service/notice-group';
  import StrategyManageService from '@service/strategy-manage';

  import CommonDataModel from '@model/strategy/common-data';
  import type StrategyModel from '@model/strategy/strategy';

  import useRequest from '@hooks/use-request';

  import RuleConditionDisplay from './rule-condition-display.vue';
  import {
    type NoticeGroupOption,
    resolveNoticeGroupTags,
    toNoticeGroupIds,
    useStrategyDetailRules,
  } from './use-strategy-detail-rules';

  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  import { isEmptyDispatchConditions } from '../../strategy-create/utils/strategy-protocol';
  import { getStrategyListScopeParams, isPlatformStrategyRoute } from '../../utils/strategy-routes';

  interface Props {
    data: StrategyModel,
    userGroupList: Array<{ id: number; name: string }>,
    detailLoading?: boolean,
  }

  const props = defineProps<Props>();
  const { t } = useI18n();
  const route = useRoute();

  const showRuleNoticeGroups = computed(() => !isPlatformStrategyRoute(route.name));

  const isGlobalStrategy = computed(() => (
    props.data?.visibility?.binding_type === 'platform_binding'
    || props.data?.binding_type === 'platform_binding'
  ));

  const currentSceneId = computed(() => {
    const { scene_id: sceneId } = getStrategyListScopeParams(route);
    return sceneId || getSceneSystemParams().scope_id;
  });

  const matchDispatchRuleByScene = (rule: Record<string, any>, sceneId: string | number) => {
    if (rule.target_scene_id !== undefined && rule.target_scene_id !== null && rule.target_scene_id !== '') {
      if (String(rule.target_scene_id) === String(sceneId)) {
        return true;
      }
    }
    return (rule.scene_ids || []).some((id: unknown) => String(id) === String(sceneId));
  };

  const pickDispatchNotice = (rule?: Record<string, any>) => {
    if (!rule) {
      return {
        processor: [] as Array<string | number>,
        follower: [] as Array<string | number>,
      };
    }
    return {
      processor: toNoticeGroupIds(rule.processor ?? rule.processors),
      follower: toNoticeGroupIds(rule.follower ?? rule.notice_users),
    };
  };

  const sceneDispatchNotice = computed(() => {
    if (!isGlobalStrategy.value) {
      return null;
    }
    const sceneId = currentSceneId.value;
    if (sceneId === undefined || sceneId === null || sceneId === '') {
      return null;
    }
    const dispatchRules = props.data?.dispatch_rules || [];
    const matched = dispatchRules.find((rule: Record<string, any>) => (
      matchDispatchRuleByScene(rule, sceneId)
    ));
    if (matched) {
      return pickDispatchNotice(matched);
    }
    const defaultRule = dispatchRules.find((rule: Record<string, any>) => (
      isEmptyDispatchConditions(rule?.conditions)
    ));
    return pickDispatchNotice(defaultRule);
  });

  const strategyData = computed(() => props.data);
  const {
    displayRules,
    riskLevelMap,
  } = useStrategyDetailRules(strategyData);

  const {
    data: commonData,
    run: fetchStrategyCommon,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonDataModel(),
  });

  const {
    data: selectGroupList,
    run: fetchSelectGroupList,
  } = useRequest(NoticeGroupManageService.fetchGroupSelectList, {
    defaultValue: [],
    manual: true,
  });

  const noticeGroupList = computed<NoticeGroupOption[]>(() => {
    const map = new Map<string, NoticeGroupOption>();
    (props.userGroupList || []).forEach((item) => {
      map.set(String(item.id), item);
    });
    (selectGroupList.value || []).forEach((item) => {
      map.set(String(item.id), item);
    });
    return Array.from(map.values());
  });

  const displayRulesWithTags = computed(() => displayRules.value.map((rule) => {
    const processor = sceneDispatchNotice.value?.processor ?? rule.processor;
    const follower = sceneDispatchNotice.value?.follower ?? rule.follower;
    return {
      ...rule,
      processorTags: resolveNoticeGroupTags(processor, noticeGroupList.value),
      followerTags: resolveNoticeGroupTags(follower, noticeGroupList.value),
    };
  }));

  const operatorMap = computed(() => (
    commonData.value.rule_audit_condition_operator || []
  ).reduce((res, item) => {
    res[item.value] = item.label;
    return res;
  }, {} as Record<string, string>));

  const aggregateList = computed(() => commonData.value.rule_audit_aggregate_type || []);

  onMounted(() => {
    fetchStrategyCommon();
    const { scene_id: sceneId } = getStrategyListScopeParams(route);
    fetchSelectGroupList(sceneId ? { scene_id: sceneId } : undefined);
  });
</script>
<style scoped lang="postcss">
.risk-discovery-rules {
  background: var(--audit-neutral-bg-04);

  .rule-item-card {
    margin-bottom: var(--audit-space-16);
    overflow: hidden;
    background: var(--audit-neutral-bg-02);
    border: 1px solid var(--audit-neutral-border-02);
    border-radius: var(--audit-radius-control);

    &:last-child {
      margin-bottom: 0;
    }
  }

  .rule-item-header {
    display: flex;
    align-items: center;
    height: 32px;
    padding: 0 var(--audit-space-16);
    background: var(--audit-neutral-bg-01);
  }

  .rule-name {
    font-size: var(--audit-font-size-sm);
    font-weight: var(--audit-font-weight-bold);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-02);
  }

  .rule-item-content {
    padding: var(--audit-space-16);
    background: var(--audit-neutral-bg-02);
  }

  .rule-field-row {
    display: flex;
    gap: var(--audit-space-8);
    align-items: flex-start;
    min-height: 32px;
    padding: 6px 0;
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);

    &:last-child {
      margin-bottom: 0;
    }
  }

  .rule-field-label {
    flex: 0 0 84px;
    width: 84px;
    min-width: 84px;
    overflow: visible;
    color: var(--audit-neutral-text-02);
    text-align: right;
    white-space: nowrap;
  }

  .rule-field-value {
    flex: 1;
    min-width: 0;
    color: var(--audit-neutral-text-01);
    word-break: break-all;

    &.multiline-text {
      white-space: pre-line;
      word-break: break-word;
    }
  }

  .notice-group-tags {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
  }

  .notice-group-tag {
    margin: 0 4px 4px 0;
  }

  .risk-level-tag {
    display: inline-flex;
    align-items: center;
    height: 22px;
    padding: 0 var(--audit-space-8);
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-bg-04);
    border-radius: var(--audit-radius-control);
  }

  .risk-discovery-rules-empty {
    display: flex;
    min-height: 320px;
    align-items: center;
    justify-content: center;
  }
}
</style>
