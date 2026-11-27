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
  <div
    class="risk-whitelist-form"
    :class="{ 'is-embedded': embedded }">
    <div class="form-item is-required">
      <div class="form-label">
        {{ t('匹配范围') }}
      </div>
      <div class="form-content">
        <div
          class="scope-editor"
          :class="{ 'has-outer': scope.groups.length > 1 }">
          <div class="group-list">
            <button
              v-if="scope.groups.length > 1"
              class="outer-logic"
              type="button"
              @click="toggleOuterConnector">
              {{ outerConnector.toUpperCase() }}
            </button>
            <div
              v-for="(group, groupIndex) in scope.groups"
              :key="groupIndex"
              class="scope-group"
              :style="{ paddingLeft: groupPaddingLeft(group) }">
              <template v-if="scope.groups.length > 1">
                <div class="outer-row-line" />
                <div
                  v-if="groupIndex > 0"
                  class="outer-col outer-col-top" />
                <div
                  v-if="groupIndex < scope.groups.length - 1"
                  class="outer-col outer-col-bottom" />
              </template>
              <audit-icon
                v-if="scope.groups.length > 1"
                class="group-delete"
                type="delete"
                @click="removeGroup(groupIndex)" />
              <div
                class="group-rows"
                :class="{ 'has-inner': group.conditions.length > 1 }">
                <button
                  v-if="group.conditions.length > 1"
                  class="inner-logic"
                  type="button"
                  @click="toggleInnerConnector(groupIndex)">
                  {{ innerConnector(group) }}
                </button>
                <div
                  v-for="(condition, conditionIndex) in group.conditions"
                  :key="`${groupIndex}-${conditionIndex}`"
                  class="scope-row">
                  <div
                    v-if="group.conditions.length > 1"
                    class="inner-row-line" />
                  <div
                    v-if="conditionIndex < group.conditions.length - 1"
                    class="inner-col-line" />
                  <bk-popover
                    v-if="isStrategyRow(groupIndex, conditionIndex)"
                    :content="t('此条件为必要条件，禁止调整')"
                    placement="top"
                    theme="dark">
                    <span class="locked-select-wrap">
                      <bk-select
                        class="field-select"
                        disabled
                        :model-value="condition.field">
                        <bk-option
                          :label="condition.field_label || condition.field_name || condition.field"
                          :value="condition.field" />
                      </bk-select>
                    </span>
                  </bk-popover>
                  <span
                    v-else
                    class="locked-select-wrap">
                    <match-scope-field-select
                      :disabled="isPrefillLocked(groupIndex, conditionIndex)"
                      :event-fields="eventFieldsByGroup(groupIndex)"
                      :event-loading="eventFieldsLoadingByGroup(groupIndex)"
                      :label="condition.field_label || condition.field_name || condition.field"
                      :model-value="condition.field"
                      :risk-fields="RISK_CONDITION_FIELDS"
                      :strategy-id="groupStrategyId(groupIndex)"
                      @change="(payload) => changeField(groupIndex, conditionIndex, payload)" />
                  </span>
                  <bk-popover
                    :content="t('此条件为必要条件，禁止调整')"
                    :disabled="!isStrategyRow(groupIndex, conditionIndex)"
                    placement="top"
                    theme="dark">
                    <span class="locked-select-wrap">
                      <!-- 仅命中策略固定等于；其它字段按 string/number 给出操作符列表 -->
                      <bk-select
                        class="operator-select"
                        :clearable="false"
                        :disabled="isPrefillLocked(groupIndex, conditionIndex) || isStrategyRow(groupIndex, conditionIndex)"
                        filterable
                        :model-value="condition.operator"
                        :placeholder="t('请选择')"
                        :popover-options="{ extCls: 'risk-whitelist-operator-select-popover' }"
                        :search-placeholder="t('请输入关键字')"
                        @change="(value: string) => changeOperator(groupIndex, conditionIndex, value)">
                        <bk-option
                          v-for="item in operatorsForCondition(groupIndex, condition)"
                          :key="item.value"
                          :label="item.label"
                          :value="item.value">
                          <span
                            v-bk-tooltips="operatorOptionTip(item.label)"
                            class="operator-option-label"
                            @mouseenter="(e: MouseEvent) => syncOperatorOptionOverflow(item.label, e)">
                            {{ item.label }}
                          </span>
                        </bk-option>
                      </bk-select>
                    </span>
                  </bk-popover>
                  <bk-select
                    v-if="condition.field === 'strategy_id'"
                    class="value-input"
                    :disabled="isPrefillLocked(groupIndex, conditionIndex)"
                    filterable
                    :loading="strategyLoading"
                    :model-value="condition.value"
                    :placeholder="t('请选择策略')"
                    :remote-method="searchStrategy"
                    @change="(value: string) => changeStrategy(groupIndex, conditionIndex, value)">
                    <bk-option
                      v-for="item in strategyOptions"
                      :key="item.id"
                      :label="item.name"
                      :value="item.id" />
                  </bk-select>
                  <span
                    v-else-if="isValuelessOperator(condition.operator)"
                    class="value-input value-input--empty" />
                  <bk-input
                    v-else
                    class="value-input"
                    :disabled="isPrefillLocked(groupIndex, conditionIndex)"
                    :model-value="condition.value"
                    :placeholder="t('请输入值')"
                    @update:model-value="(value: string) => changeTextValue(groupIndex, conditionIndex, value)" />
                  <div class="icon-group">
                    <audit-icon
                      class="expr-action-icon"
                      type="add-fill"
                      @click="addCondition(groupIndex, conditionIndex)" />
                    <audit-icon
                      v-if="canRemoveCondition(groupIndex, conditionIndex)"
                      class="expr-action-icon"
                      type="reduce-fill"
                      @click="removeCondition(groupIndex, conditionIndex)" />
                  </div>
                </div>
              </div>
            </div>
          </div>
          <button
            class="add-group"
            type="button"
            @click="addGroup">
            <audit-icon
              class="add-group-icon"
              type="add" />
            <span>{{ t('添加条件组') }}</span>
          </button>
        </div>
        <div
          v-if="scopeError"
          class="field-error">
          {{ scopeError }}
        </div>
      </div>
    </div>

    <div class="form-item is-required">
      <div class="form-label">
        {{ t('加白类型') }}
      </div>
      <div class="form-content">
        <bk-radio-group
          class="type-radios"
          :model-value="whitelistType"
          @change="changeWhitelistType">
          <bk-popover
            :content="falsePositiveTip"
            :disabled="!falsePositiveTip"
            placement="top"
            reference-cls="type-radio-tip"
            theme="dark">
            <span class="type-radio-wrap">
              <bk-radio
                :disabled="isTypeLocked || falsePositiveDisabled"
                label="false_positive">
                {{ t('误报加白') }}
              </bk-radio>
            </span>
          </bk-popover>
          <bk-popover
            :content="typeLockedTip"
            :disabled="!typeLockedTip"
            placement="top"
            reference-cls="type-radio-tip"
            theme="dark">
            <span class="type-radio-wrap">
              <bk-radio
                :disabled="isTypeLocked"
                label="risk_acceptance">
                {{ t('冒险加白') }}
              </bk-radio>
            </span>
          </bk-popover>
        </bk-radio-group>
        <bk-alert
          v-if="whitelistType === 'risk_acceptance'"
          class="type-alert risk-warning"
          theme="warning"
          :title="t('风险告警：冒险加白表示风险真实存在，可能带来安全风险，必须设置有效期。因冒险加白导致重大安全事故的，申请人需承担主要责任，请谨慎操作')" />
      </div>
    </div>

    <div class="form-item is-required is-validity">
      <div class="form-label">
        {{ t('有效期') }}
      </div>
      <div class="form-content">
        <template v-if="showDurationPicker">
          <div class="duration-line">
            <div
              class="duration-group"
              role="radiogroup">
              <button
                v-for="item in DURATION_OPTIONS"
                :key="item.id"
                class="duration-item"
                :class="{
                  'is-active': validityMode === item.id,
                  'is-disabled': item.id === 'permanent' && whitelistType === 'risk_acceptance',
                }"
                :disabled="item.id === 'permanent' && whitelistType === 'risk_acceptance'"
                type="button"
                @click="changeValidityMode(item.id)">
                {{ t(item.name) }}
              </button>
            </div>
            <bk-date-picker
              v-if="validityMode === 'custom'"
              append-to-body
              class="custom-expire"
              :clearable="false"
              :disabled-date="disablePastDate"
              ext-popover-cls="risk-whitelist-date-dropdown"
              format="yyyy-MM-dd HH:mm:ss"
              :model-value="customExpire"
              :placeholder="t('请选择到期时间')"
              type="datetime"
              @update:model-value="changeCustomExpire" />
          </div>
          <!-- 新建/选期限时展示预计到期时间，对齐 Figma「默认 1 个月并展示到期时间」 -->
          <div
            v-if="showExpirePreview"
            class="expire-preview">
            {{ t('到期时间') }}：{{ expectedExpire }}
          </div>
          <bk-alert
            v-if="showSwitchHint"
            class="type-alert"
            theme="info"
            :title="t('切换后将从现在起计算到期时间。预计到期时间为：{time}', { time: expectedExpire })" />
        </template>
        <template v-else>
          <div class="expire-line">
            <div class="expire-box">
              <span>{{ renewedExpire || record?.expire_at || '--' }}</span>
              <span
                v-if="validityView === 'expired'"
                class="expired-text">{{ t('已到期') }}</span>
            </div>
            <bk-button
              v-if="validityView === 'active' || validityView === 'expired'"
              class="renew-link"
              text
              theme="primary"
              @click="startRenew">
              {{ t('续期') }}
            </bk-button>
          </div>
          <bk-alert
            v-if="validityView === 'disabled'"
            class="type-alert"
            theme="warning"
            :title="t('当前为停用状态。如需延长有效期，请先启用后再续期。')" />
          <bk-alert
            v-if="validityView === 'expired'"
            class="type-alert"
            theme="danger"
            :title="t('当前期限已到期。如需延长使用，请续期。')" />
        </template>
        <div
          v-if="validityError"
          class="field-error">
          {{ validityError }}
        </div>
      </div>
    </div>

    <div class="form-item is-required is-reason">
      <div class="form-label">
        {{ t('加白原因') }}
      </div>
      <div class="form-content">
        <bk-input
          :maxlength="500"
          :model-value="reason"
          :placeholder="t('请输入加白原因')"
          :rows="2"
          show-word-limit
          type="textarea"
          @update:model-value="changeReason" />
        <div
          v-if="reasonError"
          class="field-error">
          {{ reasonError }}
        </div>
      </div>
    </div>

    <bk-alert
      v-if="showApplyHint && applyHintText"
      class="type-alert"
      theme="info"
      :title="t(applyHintText)" />
  </div>
</template>
<script setup lang="ts">
  import dayjs from 'dayjs';
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskManageService from '@service/risk-manage';
  import StrategyManageService from '@service/strategy-manage';

  import type RiskWhitelist from '@model/risk-whitelist/whitelist';
  import type {
    CompareOperator,
    LogicConnector,
    MatchCondition,
    MatchGroup,
    MatchScope,
    ValidityMode,
    WhitelistPayload,
    WhitelistType,
  } from '@model/risk-whitelist/whitelist';

  import useWhitelistRoleText, { getWhitelistApplyHint } from '@hooks/use-whitelist-role-text';

  import {
    calcExpireAt,
    createDefaultScope,
    createGroup,
    DURATION_OPTIONS,
    everyGroupHasStrategy,
    FALLBACK_CONDITION_FIELDS,
    getFirstStrategySeed,
    getOperatorsForField,
    hasStrategyOnlyGroup,
    isValuelessOperator,
    RISK_CONDITION_FIELDS,
  } from '@components/risk-whitelist/constants';
  import MatchScopeFieldSelect, {
    type EventFieldOption,
    type FieldSelectPayload,
  } from '@components/risk-whitelist/match-scope-field-select.vue';

  interface Props {
    record?: RiskWhitelist | null;
    showApplyHint?: boolean;
    embedded?: boolean;
    initialScope?: MatchScope | null;
    /** 风险所属 / 规则所属场景；用于场景域管理员判权 */
    sceneId?: string | number | null;
    /** 锁定加白类型（如标记误报同时加白仅允许 false_positive） */
    lockedType?: WhitelistType | null;
  }

  const props = withDefaults(defineProps<Props>(), {
    record: null,
    showApplyHint: false,
    embedded: false,
    initialScope: null,
    sceneId: null,
    lockedType: null,
  });

  const { t } = useI18n();
  const roleText = useWhitelistRoleText(computed(() => props.sceneId ?? props.record?.scene_id ?? null));

  const scope = ref<MatchScope>(createDefaultScope());
  const whitelistType = ref<WhitelistType>('false_positive');
  const applyHintText = computed(() => (
    getWhitelistApplyHint(whitelistType.value, roleText.isAdmin.value)
  ));
  const validityMode = ref<ValidityMode>('permanent');
  const customDays = ref(1);
  const customExpire = ref('');
  const reason = ref('');
  const scopeError = ref('');
  const validityError = ref('');
  const reasonError = ref('');
  const dirty = ref(false);
  const renewedExpire = ref('');
  const renewedActive = ref(false);
  const renewEditing = ref(false);
  const strategyLoading = ref(false);
  const strategyOptions = ref<Array<{ id: string; name: string }>>([]);
  /** 按命中策略缓存事件字段全量（与场景风险搜索同源接口） */
  const eventFieldsCache = ref<Record<string, EventFieldOption[]>>({});
  const eventFieldsLoadingMap = ref<Record<string, boolean>>({});
  /** 风险单带入的 strategy_id / raw_event_id，按设计稿整行禁用 */
  const lockedPrefillKeys = ref<Set<string>>(new Set());

  const isEdit = computed(() => Boolean(props.record?.id));
  /** 后端编辑接口不接收类型：编辑态或外部锁定（如误报加白）时类型只读 */
  const isTypeLocked = computed(() => isEdit.value || Boolean(props.lockedType));
  const prefillLockKey = (field: string, value: string) => `${field}\u0001${value}`;

  const syncLockedPrefillKeys = (scopeSource?: MatchScope | null) => {
    const next = new Set<string>();
    if (props.embedded && scopeSource?.groups?.length) {
      scopeSource.groups.forEach((group) => {
        group.conditions.forEach((condition) => {
          if (
            (condition.field === 'strategy_id' || condition.field === 'raw_event_id')
            && condition.value
          ) {
            next.add(prefillLockKey(condition.field, String(condition.value)));
          }
        });
      });
    }
    lockedPrefillKeys.value = next;
  };

  const isPrefillLocked = (groupIndex: number, conditionIndex: number) => {
    const condition = scope.value.groups[groupIndex]?.conditions[conditionIndex];
    if (!condition?.field || condition.value === undefined || condition.value === null || condition.value === '') {
      return false;
    }
    return lockedPrefillKeys.value.has(prefillLockKey(condition.field, String(condition.value)));
  };
  const falsePositiveDisabled = computed(() => hasStrategyOnlyGroup(scope.value));
  /** 编辑 / 外部锁定时类型只读，hover 说明原因 */
  const typeLockedTip = computed(() => {
    if (!isTypeLocked.value) return '';
    return isEdit.value ? t('编辑时不可修改加白类型') : t('不可修改');
  });
  const falsePositiveTip = computed(() => {
    if (typeLockedTip.value) return typeLockedTip.value;
    if (falsePositiveDisabled.value) return t('只有命中策略条件时不允许误报加白');
    return '';
  });
  const expectedExpire = computed(() => {
    if (validityMode.value === 'custom') {
      const picked = dayjs(customExpire.value);
      return picked.isValid() ? picked.format('YYYY-MM-DD HH:mm:ss') : '--';
    }
    return calcExpireAt(validityMode.value, customDays.value);
  });

  const validityView = computed(() => {
    if (!isEdit.value || !props.record) return 'picker';
    if (props.record.is_permanent || props.record.validity_mode === 'permanent') {
      return validityMode.value === 'permanent' ? 'picker' : 'permanent-switch';
    }
    if (props.record.status === 'disabled') return 'disabled';
    if (props.record.status === 'expired' && !renewedActive.value) return 'expired';
    return 'active';
  });

  const showDurationPicker = computed(() => (
    !props.record
    || validityView.value === 'picker'
    || validityView.value === 'permanent-switch'
    || renewEditing.value
  ));

  const showSwitchHint = computed(() => (
    validityMode.value !== 'permanent'
    && (renewEditing.value || validityView.value === 'permanent-switch')
  ));

  /** 快捷期限展示预计到期时间；自定义已有日期选择器，不再重复展示 */
  const showExpirePreview = computed(() => (
    showDurationPicker.value
    && validityMode.value !== 'permanent'
    && validityMode.value !== 'custom'
    && !showSwitchHint.value
  ));

  const markDirty = () => {
    dirty.value = true;
    window.changeConfirm = true;
  };

  /** 只清对应字段的校验，避免改加白原因时把匹配范围错误一并抹掉 */
  const clearScopeError = () => {
    if (scopeError.value) scopeError.value = '';
  };
  const clearReasonError = () => {
    if (reasonError.value) reasonError.value = '';
  };
  const clearValidityError = () => {
    if (validityError.value) validityError.value = '';
  };

  /** 命中策略强制等于；空值操作符清空 value；非法操作符回落到该字段首个可用项 */
  const normalizeCondition = (
    condition: MatchCondition,
    fieldType?: string | null,
  ): MatchCondition => {
    if (condition.field === 'strategy_id') {
      return {
        ...condition,
        operator: 'eq',
        field_name: condition.field_name || '风险命中策略(ID)',
        field_label: condition.field_label || '风险命中策略(ID)(strategy_id)',
      };
    }
    const operators = getOperatorsForField(condition.field, fieldType);
    const allowed = operators.some(item => item.value === condition.operator);
    const nextOperator = allowed
      ? condition.operator
      : (operators[0]?.value || 'eq');
    if (isValuelessOperator(nextOperator)) {
      return {
        ...condition,
        operator: nextOperator,
        value: '',
        value_display: '',
      };
    }
    return {
      ...condition,
      operator: nextOperator,
    };
  };

  const normalizeScope = (input: MatchScope): MatchScope => ({
    groups: (input.groups || []).map(group => ({
      ...group,
      conditions: (group.conditions || []).map(condition => normalizeCondition(condition)),
    })),
  });

  const fillFromRecord = (record: RiskWhitelist | null) => {
    dirty.value = false;
    // 表单重置时清离开确认；抽屉打开时 audit-sideslider 会再设为 popover
    if (window.changeConfirm === true) {
      window.changeConfirm = false;
    }
    renewedExpire.value = '';
    renewedActive.value = false;
    renewEditing.value = false;
    if (!record) {
      const nextScope = props.initialScope?.groups?.length
        ? JSON.parse(JSON.stringify(props.initialScope))
        : createDefaultScope();
      scope.value = normalizeScope(nextScope);
      syncLockedPrefillKeys(props.initialScope);
      if (props.lockedType) {
        whitelistType.value = props.lockedType;
      } else {
        whitelistType.value = hasStrategyOnlyGroup(scope.value) ? 'risk_acceptance' : 'false_positive';
      }
      validityMode.value = whitelistType.value === 'risk_acceptance' ? '1m' : 'permanent';
      customDays.value = 1;
      customExpire.value = '';
      reason.value = '';
      return;
    }
    lockedPrefillKeys.value = new Set();
    scope.value = normalizeScope(JSON.parse(JSON.stringify(record.match_scope?.groups?.length
      ? record.match_scope
      : createDefaultScope())));
    whitelistType.value = record.whitelist_type;
    validityMode.value = record.is_permanent ? 'permanent' : (record.validity_mode || '1m');
    customDays.value = record.custom_days || 1;
    customExpire.value = record.validity_mode === 'custom' ? (record.expire_at || '') : '';
    reason.value = record.reason || '';
  };

  watch(() => props.record, fillFromRecord, { immediate: true });
  watch(whitelistType, (type) => {
    if (type === 'risk_acceptance' && validityMode.value === 'permanent') {
      validityMode.value = '1m';
      return;
    }
    // 误报加白默认永久；从冒险切回时恢复默认，避免仍停在 1 个月
    if (type === 'false_positive' && !isEdit.value) {
      validityMode.value = 'permanent';
      customExpire.value = '';
    }
  });
  watch(falsePositiveDisabled, (disabled) => {
    if (isTypeLocked.value) return;
    if (disabled && whitelistType.value === 'false_positive') {
      whitelistType.value = 'risk_acceptance';
    }
  });
  watch(() => props.lockedType, (type) => {
    if (type && !isEdit.value) {
      whitelistType.value = type;
      if (type === 'risk_acceptance' && validityMode.value === 'permanent') {
        validityMode.value = '1m';
      }
    }
  });

  const seedSelectedStrategies = () => {
    const selected = scope.value.groups.flatMap(group => group.conditions)
      .filter(item => item.field === 'strategy_id' && item.value)
      .map(item => ({ id: String(item.value), name: item.value_display || String(item.value) }));
    const selectedIds = new Set(selected.map(item => item.id));
    strategyOptions.value = [
      ...selected,
      ...strategyOptions.value.filter(item => !selectedIds.has(item.id)),
    ];
  };

  /** 从风险单带入时已有策略：只展示当前风险策略，不拉全量列表（与后端 risk_id 预填口径一致） */
  const isRiskBoundStrategy = computed(() => {
    if (!props.embedded || !props.initialScope?.groups?.length) return false;
    return props.initialScope.groups.some(group => (
      group.conditions.some(item => item.field === 'strategy_id' && item.value)
    ));
  });

  /** 菜单新建：策略列表就绪后，空命中策略默认选第一条（不可为空）；属初始化，不标脏 */
  const ensureDefaultStrategy = () => {
    if (isEdit.value || isRiskBoundStrategy.value) return;
    if (!strategyOptions.value.length) return;
    const first = strategyOptions.value[0];
    scope.value.groups = scope.value.groups.map(group => ({
      ...group,
      conditions: group.conditions.map((condition) => {
        if (condition.field !== 'strategy_id' || condition.value) return normalizeCondition(condition);
        return normalizeCondition({
          ...condition,
          operator: 'eq',
          value: first.id,
          value_display: first.name,
        });
      }),
    }));
  };

  /**
   * 菜单新建：暂用风险侧 /risks/strategies/。
   * 风险单加白：只保留当前风险策略，不请求列表。
   * 后端白名单专用策略选项接口就绪后再统一替换。
   */
  const searchStrategy = (keyword = '') => {
    seedSelectedStrategies();
    if (isRiskBoundStrategy.value) {
      strategyOptions.value = scope.value.groups.flatMap(group => group.conditions)
        .filter(item => item.field === 'strategy_id' && item.value)
        .map(item => ({ id: String(item.value), name: item.value_display || String(item.value) }));
      strategyLoading.value = false;
      return;
    }
    strategyLoading.value = true;
    const end = dayjs();
    const start = end.subtract(182, 'day');
    StrategyManageService.fetchScopedStrategyList({
      risk_view_type: 'all',
      start_time: start.format('YYYY-MM-DD HH:mm:ss'),
      end_time: end.format('YYYY-MM-DD HH:mm:ss'),
      isNeedSceneParams: true,
    }).then((data) => {
      const kw = String(keyword || '').trim().toLowerCase();
      const fetched = (Array.isArray(data) ? data : [])
        .map((item) => {
          const id = String(item.value ?? '');
          const label = String(item.label || '').trim();
          return {
            id,
            name: label ? `${label}(${id})` : id,
          };
        })
        .filter(item => item.id)
        .filter(item => !kw || item.name.toLowerCase().includes(kw) || item.id.includes(kw));
      const selected = scope.value.groups.flatMap(group => group.conditions)
        .filter(item => item.field === 'strategy_id' && item.value)
        .map(item => ({ id: String(item.value), name: item.value_display || String(item.value) }));
      const ids = new Set(fetched.map(item => item.id));
      strategyOptions.value = [
        ...selected.filter(item => !ids.has(item.id)),
        ...fetched,
      ];
      // 无关键词的首轮拉取：空策略默认第一条
      if (!kw) ensureDefaultStrategy();
    })
      .catch(() => {
        seedSelectedStrategies();
      })
      .finally(() => {
        strategyLoading.value = false;
      });
  };

  searchStrategy();

  const scopeValueKey = (input?: MatchScope | null) => (
    (input?.groups || []).map(group => (
      group.conditions.map(item => [item.field, item.operator, String(item.value ?? '')].join('\u0001')).join('\u0002')
    )).join('\u0003')
  );

  const shouldTakeDisplay = (current: string, incoming: string, value: string) => {
    if (!incoming || incoming === current) return false;
    // 详情还没带上策略名时，不要用原始值盖掉已经解析出的名称
    if (incoming === value && current && current !== value) return false;
    return true;
  };

  const syncScopeValueDisplay = (incoming?: MatchScope | null) => {
    if (!incoming?.groups?.length) return;
    const nameByValue = new Map<string, string>();
    let scopeChanged = false;
    const groups = scope.value.groups.map((group, groupIndex) => {
      const incomingGroup = incoming.groups[groupIndex];
      if (!incomingGroup) return group;
      return {
        ...group,
        conditions: group.conditions.map((condition, conditionIndex) => {
          const incomingCondition = incomingGroup.conditions[conditionIndex];
          if (!incomingCondition) return condition;
          const sameValue = condition.field === incomingCondition.field
            && condition.operator === incomingCondition.operator
            && String(condition.value ?? '') === String(incomingCondition.value ?? '');
          const nextDisplay = incomingCondition.value_display || '';
          if (!sameValue || !shouldTakeDisplay(condition.value_display, nextDisplay, String(condition.value ?? ''))) {
            return condition;
          }
          scopeChanged = true;
          if (condition.field === 'strategy_id') {
            nameByValue.set(String(condition.value), nextDisplay);
          }
          return { ...condition, value_display: nextDisplay };
        }),
      };
    });
    if (scopeChanged) {
      scope.value = { ...scope.value, groups };
    }
    if (!nameByValue.size) return;
    const known = new Set(strategyOptions.value.map(item => item.id));
    strategyOptions.value = [
      ...strategyOptions.value.map(item => (
        nameByValue.has(item.id) ? { ...item, name: nameByValue.get(item.id) || item.name } : item
      )),
      ...[...nameByValue.entries()]
        .filter(([id]) => !known.has(id))
        .map(([id, name]) => ({ id, name })),
    ];
  };

  watch(() => props.initialScope, (incoming) => {
    if (props.record) return;
    if (scopeValueKey(incoming) === scopeValueKey(scope.value)) {
      syncScopeValueDisplay(incoming);
      return;
    }
    if (!dirty.value) {
      fillFromRecord(null);
      searchStrategy();
    }
  });

  const outerConnector = computed(() => scope.value.groups[1]?.connector || 'and');
  const innerConnector = (group: MatchGroup) => group.conditions[1]?.connector || 'and';
  const groupPaddingLeft = (group: MatchGroup) => {
    const hasNested = scope.value.groups.some(item => item.conditions.length > 1);
    return group.conditions.length > 1 || hasNested ? '55px' : '16px';
  };

  const isStrategyRow = (groupIndex: number, conditionIndex: number) => (
    conditionIndex === 0 && scope.value.groups[groupIndex].conditions[0].field === 'strategy_id'
  );

  const groupStrategyId = (groupIndex: number) => {
    const strategy = scope.value.groups[groupIndex]?.conditions
      .find(item => item.field === 'strategy_id' && item.value);
    return strategy ? String(strategy.value) : '';
  };

  /**
   * 解析条件字段类型：
   * - 风险字段 / 未拉到事件列表：undefined → 走内置 meta 或 string 兜底
   * - 事件列表命中：返回 field_type（含 null，由 map 兜底为 string）
   */
  const resolveConditionFieldType = (
    groupIndex: number,
    field: string,
  ): string | null | undefined => {
    if (field === 'strategy_id') return undefined;
    const meta = FALLBACK_CONDITION_FIELDS.find(item => item.field === field);
    if (meta?.field_group === 'risk') return undefined;
    const strategyId = groupStrategyId(groupIndex);
    if (!strategyId) return undefined;
    const list = eventFieldsCache.value[strategyId];
    if (!list) return undefined;
    const found = list.find(item => item.field_name === field);
    if (!found) return undefined;
    return found.field_type ?? null;
  };

  const operatorsForCondition = (groupIndex: number, condition: MatchCondition) => (
    getOperatorsForField(condition.field, resolveConditionFieldType(groupIndex, condition.field))
  );

  /** 操作符选项溢出时才出 tip，避免短文案也弹 */
  const operatorOptionOverflowMap = ref<Record<string, boolean>>({});

  const operatorOptionTip = (label: string) => ({
    content: label,
    disabled: !operatorOptionOverflowMap.value[label],
    delay: 80,
    placement: 'right' as const,
  });

  const syncOperatorOptionOverflow = (label: string, event: MouseEvent) => {
    const el = event.currentTarget as HTMLElement | null;
    const overflowed = Boolean(el && el.scrollWidth > el.clientWidth + 1);
    if (operatorOptionOverflowMap.value[label] === overflowed) return;
    operatorOptionOverflowMap.value = {
      ...operatorOptionOverflowMap.value,
      [label]: overflowed,
    };
  };

  const normalizeEventFieldItem = (item: Record<string, any>): EventFieldOption => {
    const fieldName = String(item.field_name || item.field || '');
    const displayName = String(item.display_name || item.name || fieldName);
    return {
      id: String(item.id || `${fieldName}:${displayName}`),
      field_name: fieldName,
      display_name: displayName,
      field_type: item.field_type ?? null,
      ...(item.type === 'basic_event_field' ? { type: item.type } : {}),
    };
  };

  const ensureEventFields = (strategyId: string) => {
    if (
      !strategyId
      || Object.prototype.hasOwnProperty.call(eventFieldsCache.value, strategyId)
      || eventFieldsLoadingMap.value[strategyId]
    ) {
      return;
    }
    eventFieldsLoadingMap.value = {
      ...eventFieldsLoadingMap.value,
      [strategyId]: true,
    };
    RiskManageService.fetchEventFields({ strategy_ids: [strategyId] })
      .then((data) => {
        const list = (Array.isArray(data) ? data : [])
          .map(item => normalizeEventFieldItem(item))
          .filter(item => item.field_name);
        eventFieldsCache.value = {
          ...eventFieldsCache.value,
          [strategyId]: list,
        };
        // 事件字段类型就绪后，按类型校正已选操作符（非法则回落默认）
        realignOperatorsByEventFieldTypes(strategyId);
      })
      .catch(() => {
        eventFieldsCache.value = {
          ...eventFieldsCache.value,
          [strategyId]: [],
        };
      })
      .finally(() => {
        eventFieldsLoadingMap.value = {
          ...eventFieldsLoadingMap.value,
          [strategyId]: false,
        };
      });
  };

  /** 事件字段列表返回后，按 field_type 校正同策略条件下的操作符 */
  const realignOperatorsByEventFieldTypes = (strategyId: string) => {
    let changed = false;
    const nextGroups = scope.value.groups.map((group, groupIndex) => {
      if (groupStrategyId(groupIndex) !== strategyId) return group;
      return {
        ...group,
        conditions: group.conditions.map((condition) => {
          if (condition.field === 'strategy_id') return condition;
          const fieldType = resolveConditionFieldType(groupIndex, condition.field);
          if (fieldType === undefined) return condition;
          const next = normalizeCondition(condition, fieldType);
          if (next.operator !== condition.operator) changed = true;
          return next;
        }),
      };
    });
    if (changed) {
      scope.value = { ...scope.value, groups: nextGroups };
    }
  };

  const syncEventFieldsForScope = () => {
    scope.value.groups.forEach((_, index) => {
      const strategyId = groupStrategyId(index);
      if (strategyId) ensureEventFields(strategyId);
    });
  };

  const eventFieldsByGroup = (groupIndex: number) => {
    const strategyId = groupStrategyId(groupIndex);
    return strategyId ? (eventFieldsCache.value[strategyId] || []) : [];
  };

  const eventFieldsLoadingByGroup = (groupIndex: number) => {
    const strategyId = groupStrategyId(groupIndex);
    return Boolean(strategyId && eventFieldsLoadingMap.value[strategyId]);
  };

  watch(
    () => scope.value.groups.map((group, index) => `${index}:${groupStrategyId(index)}`).join('|'),
    () => {
      syncEventFieldsForScope();
    },
    { immediate: true },
  );

  const patchGroup = (groupIndex: number, patch: Partial<MatchScope['groups'][number]>) => {
    scope.value = {
      ...scope.value,
      groups: scope.value.groups.map((group, index) => (
        index === groupIndex ? { ...group, ...patch } : group
      )),
    };
  };

  const patchCondition = (groupIndex: number, conditionIndex: number, patch: Partial<MatchCondition>) => {
    const group = scope.value.groups[groupIndex];
    patchGroup(groupIndex, {
      conditions: group.conditions.map((condition, index) => (
        index === conditionIndex ? { ...condition, ...patch } : condition
      )),
    });
  };

  const toggleOuterConnector = () => {
    const next: LogicConnector = outerConnector.value === 'and' ? 'or' : 'and';
    scope.value.groups.forEach((group, index) => {
      if (index > 0) group.connector = next;
    });
    markDirty();
    clearScopeError();
  };

  const toggleInnerConnector = (groupIndex: number) => {
    const group = scope.value.groups[groupIndex];
    const next: LogicConnector = innerConnector(group) === 'and' ? 'or' : 'and';
    group.conditions.forEach((condition, index) => {
      if (index > 0) condition.connector = next;
    });
    markDirty();
    clearScopeError();
  };

  const changeWhitelistType = (value: WhitelistType) => {
    if (isTypeLocked.value) return;
    whitelistType.value = value;
    markDirty();
  };

  const changeValidityMode = (value: ValidityMode) => {
    if (value === 'permanent' && whitelistType.value === 'risk_acceptance') return;
    validityMode.value = value;
    markDirty();
    clearValidityError();
  };

  const startRenew = () => {
    renewEditing.value = true;
    markDirty();
  };

  const disablePastDate = (date: Date) => dayjs(date).endOf('day').isBefore(dayjs());

  const changeCustomExpire = (value: string | Date) => {
    const picked = dayjs(value);
    customExpire.value = picked.isValid() ? picked.format('YYYY-MM-DD HH:mm:ss') : '';
    if (picked.isValid()) {
      customDays.value = Math.max(Math.ceil(picked.diff(dayjs(), 'hour', true) / 24), 1);
    }
    markDirty();
    clearValidityError();
  };

  const changeReason = (value: string) => {
    reason.value = value;
    markDirty();
    clearReasonError();
  };

  const changeField = (groupIndex: number, conditionIndex: number, payload: FieldSelectPayload) => {
    if (!payload?.field) return;
    markDirty();
    clearScopeError();
    const fieldType = payload.field_group === 'event'
      ? (payload.field_type ?? null)
      : undefined;
    const operators = getOperatorsForField(payload.field, fieldType);
    patchCondition(groupIndex, conditionIndex, normalizeCondition({
      field: payload.field,
      field_name: payload.field_name,
      field_label: payload.field_label,
      operator: operators[0]?.value || 'eq',
      value: '',
      value_display: '',
      connector: scope.value.groups[groupIndex].conditions[conditionIndex]?.connector || 'and',
    }, fieldType));
  };

  const changeOperator = (groupIndex: number, conditionIndex: number, value: string) => {
    if (isStrategyRow(groupIndex, conditionIndex)) return;
    markDirty();
    clearScopeError();
    const condition = scope.value.groups[groupIndex].conditions[conditionIndex];
    patchCondition(groupIndex, conditionIndex, normalizeCondition({
      ...condition,
      operator: value as CompareOperator,
    }, resolveConditionFieldType(groupIndex, condition.field)));
  };

  const changeStrategy = (groupIndex: number, conditionIndex: number, value: string) => {
    markDirty();
    clearScopeError();
    const option = strategyOptions.value.find(item => item.id === value);
    patchCondition(groupIndex, conditionIndex, {
      operator: 'eq',
      value,
      value_display: option?.name || value,
    });
    if (value) ensureEventFields(String(value));
  };

  const changeTextValue = (groupIndex: number, conditionIndex: number, value: string) => {
    markDirty();
    clearScopeError();
    patchCondition(groupIndex, conditionIndex, {
      value,
      value_display: value,
    });
  };

  const addCondition = (groupIndex: number, conditionIndex: number) => {
    const field = FALLBACK_CONDITION_FIELDS.find(item => item.field === 'raw_event_id')
      || FALLBACK_CONDITION_FIELDS.find(item => item.field !== 'strategy_id')
      || FALLBACK_CONDITION_FIELDS[1];
    const next: MatchCondition = {
      field: field.field,
      field_name: field.name,
      field_label: field.label,
      operator: field.operators[0]?.value || 'eq',
      value: '',
      value_display: '',
      connector: 'and',
    };
    scope.value.groups[groupIndex].conditions.splice(conditionIndex + 1, 0, next);
    markDirty();
    clearScopeError();
  };

  const canRemoveCondition = (groupIndex: number, conditionIndex: number) => {
    const group = scope.value.groups[groupIndex];
    if (group.conditions.length <= 1) return false;
    if (isPrefillLocked(groupIndex, conditionIndex)) return false;
    return !isStrategyRow(groupIndex, conditionIndex);
  };

  const removeCondition = (groupIndex: number, conditionIndex: number) => {
    const group = scope.value.groups[groupIndex];
    if (group.conditions.length === 1) {
      scope.value.groups.splice(groupIndex, 1);
      markDirty();
      clearScopeError();
      return;
    }
    group.conditions.splice(conditionIndex, 1);
    markDirty();
    clearScopeError();
  };

  const removeGroup = (groupIndex: number) => {
    if (scope.value.groups.length <= 1) return;
    scope.value.groups.splice(groupIndex, 1);
    markDirty();
    clearScopeError();
  };

  const addGroup = () => {
    markDirty();
    clearScopeError();
    // 新增条件组：命中策略锁定；值默认与第一组一致；组间连接沿用原默认 and（需 OR 时用户可切换）
    const seed = getFirstStrategySeed(scope.value);
    scope.value.groups.push(createGroup('and', seed));
  };

  const validate = () => {
    scopeError.value = '';
    validityError.value = '';
    reasonError.value = '';
    const missingValue = scope.value.groups.some(group => group.conditions.some(item => (
      !isValuelessOperator(item.operator) && !item.value
    )));
    if (!scope.value.groups.length || missingValue) {
      scopeError.value = t('请完善匹配范围');
    } else if (!everyGroupHasStrategy(scope.value)) {
      scopeError.value = t('每个条件组都必须包含命中策略');
    } else if (whitelistType.value === 'false_positive' && falsePositiveDisabled.value) {
      scopeError.value = t('只有命中策略条件时不允许误报加白');
    }
    if (!reason.value.trim()) {
      reasonError.value = t('请输入加白原因');
    }
    if (whitelistType.value === 'risk_acceptance' && validityMode.value === 'permanent') {
      validityError.value = t('冒险加白必须设置有效期');
    } else if (validityMode.value === 'custom') {
      const picked = dayjs(customExpire.value);
      if (!customExpire.value || !picked.isValid() || !picked.isAfter(dayjs())) {
        validityError.value = t('请选择晚于当前时间的到期时间');
      }
    }
    return !scopeError.value && !reasonError.value && !validityError.value;
  };

  const isValidityEditable = () => (
    renewEditing.value
    || validityView.value === 'picker'
    || validityView.value === 'permanent-switch'
  );

  const getPayload = (): WhitelistPayload => {
    const payload: WhitelistPayload = {
      match_scope: normalizeScope(scope.value),
      whitelist_type: props.lockedType || whitelistType.value,
      reason: reason.value.trim(),
    };
    if (isValidityEditable()) {
      payload.validity_mode = validityMode.value;
      if (validityMode.value === 'custom') {
        const picked = dayjs(customExpire.value);
        payload.expire_at = picked.format('YYYY-MM-DD HH:mm:ss');
        payload.custom_days = Math.max(Math.ceil(picked.diff(dayjs(), 'hour', true) / 24), 1);
      }
    }
    return payload;
  };

  const getValidityPreview = () => {
    const editable = isValidityEditable();
    if (!editable) {
      return {
        editable,
        expireAt: renewedExpire.value || props.record?.expire_at || '',
      };
    }
    if (validityMode.value === 'custom') {
      const picked = dayjs(customExpire.value);
      return {
        editable,
        expireAt: picked.isValid() ? picked.format('YYYY-MM-DD HH:mm:ss') : '',
      };
    }
    return {
      editable,
      expireAt: '',
    };
  };

  const applyRenewed = (expireAt: string, mode: ValidityMode, days = 1) => {
    renewedExpire.value = expireAt;
    renewedActive.value = true;
    validityMode.value = mode;
    customDays.value = days;
  };

  const isDirty = () => dirty.value;

  defineExpose({
    validate,
    getPayload,
    applyRenewed,
    isDirty,
    getValidityPreview,
  });
</script>
<style lang="postcss" scoped>
  .risk-whitelist-form {
    padding: var(--bk-theme-space-24) var(--bk-theme-space-24) 0;
    overflow: visible;
  }

  .risk-whitelist-form.is-embedded {
    padding: 0;
  }

  .risk-whitelist-form.is-embedded .form-item {
    flex-direction: column;
  }

  .risk-whitelist-form.is-embedded .form-label {
    width: auto;
    padding-top: 0;
    margin-bottom: var(--bk-theme-space-8);
    text-align: left;
  }

  .risk-whitelist-form.is-embedded .form-content {
    margin-left: 0;
  }

  .form-item {
    display: flex;
    flex-direction: column;
    margin-bottom: var(--bk-theme-space-24);
  }

  .form-item:last-child {
    margin-bottom: 0;
  }

  .form-label {
    width: auto;
    flex-shrink: 0;
    margin-bottom: var(--bk-theme-space-8);
    font-family: var(--bk-theme-font-family);
    font-size: var(--bk-theme-font-size-sm);
    font-style: normal;
    font-weight: var(--bk-theme-font-weight-regular);
    line-height: var(--bk-theme-line-height-sm);
    color: var(--bk-theme-text-default);
    text-align: left;
  }

  .is-required .form-label::after {
    margin-left: var(--bk-theme-space-2);
    color: var(--bk-theme-color-danger-2);
    content: '*';
  }

  .is-validity .form-label {
    height: 16px;
    line-height: 16px;
  }

  .is-reason {
    margin-bottom: 0;
  }

  .is-reason .form-label {
    margin-bottom: var(--bk-theme-space-6);
  }

  .form-content {
    flex: 1;
    min-width: 0;
  }

  .type-radios {
    display: inline-flex;
    gap: var(--bk-theme-space-24);
    align-items: center;
    height: 20px;
    line-height: 20px;
  }

  .type-radios :deep(.bk-radio) {
    height: 20px;
    line-height: 20px;
  }

  .type-radios :deep(.bk-radio-label) {
    font-size: 12px;
  }

  .risk-warning :deep(.bk-alert-title) {
    line-height: var(--bk-theme-line-height-sm);
    white-space: nowrap;
  }

  .type-radio-wrap {
    display: inline-flex;
    align-items: center;
  }

  :deep(.type-radio-tip) {
    display: inline-flex;
    vertical-align: middle;
  }

  .group-list {
    position: relative;
  }

  .scope-editor.has-outer .group-list {
    width: calc(100% - 40px);
    margin-left: var(--bk-theme-space-32);
  }

  .outer-logic,
  .inner-logic {
    position: absolute;
    z-index: 1;
    width: 28px;
    height: 28px;
    padding: 0;
    font-size: var(--bk-theme-font-size-sm);
    line-height: 26px;
    color: var(--bk-theme-color-warn-2);
    text-align: center;
    cursor: pointer;
    background: var(--bk-theme-surface-default);
    border: 1px solid var(--bk-theme-color-warn-3);
    border-radius: var(--bk-theme-tag-radius);
  }

  .outer-logic:hover,
  .inner-logic:hover {
    background: var(--bk-theme-status-warn-bg);
  }

  .outer-logic {
    top: calc(50% - 14px);
    left: -36px;
    width: 32px;
  }

  .scope-group {
    position: relative;
    padding: var(--bk-theme-space-16) var(--bk-theme-space-24) var(--bk-theme-space-16) var(--bk-theme-space-16);
    margin-bottom: var(--bk-theme-space-12);
    background: var(--bk-theme-surface-subtle);
    border-radius: var(--bk-theme-radius-8);
  }

  .risk-whitelist-form.is-embedded .scope-group {
    background: var(--bk-theme-surface-default);
  }

  .outer-row-line {
    position: absolute;
    top: 50%;
    left: -20px;
    width: 20px;
    height: 0;
    border-top: 1px dashed var(--bk-theme-border-default);
  }

  .outer-col {
    position: absolute;
    left: -20px;
    width: 0;
    height: calc(50% + 6px);
    border-left: 1px dashed var(--bk-theme-border-default);
  }

  .outer-col-top {
    top: 0;
    transform: translateY(-6px);
  }

  .outer-col-bottom {
    top: 50%;
  }

  .group-delete {
    position: absolute;
    top: 5px;
    right: 5px;
    font-size: 14px;
    color: var(--bk-theme-text-weak);
    cursor: pointer;
  }

  .inner-logic {
    top: calc(50% - 10px);
    left: 14px;
    width: 30px;
    height: 20px;
    line-height: 18px;
  }

  .scope-row {
    position: relative;
    display: grid;
    /* 操作符 180；字段相对原 260 略收，值列仍自适应 */
    grid-template-columns: 240px 180px minmax(0, 1fr) minmax(40px, auto);
    gap: var(--bk-theme-space-8);
    align-items: center;
  }

  .scope-row + .scope-row {
    margin-top: var(--bk-theme-space-8);
  }

  .inner-row-line {
    position: absolute;
    top: 16px;
    left: -25px;
    width: 25px;
    height: 0;
    border-top: 1px dashed var(--bk-theme-border-default);
  }

  .inner-col-line {
    position: absolute;
    top: 16px;
    left: -25px;
    width: 0;
    height: 40px;
    border-left: 1px dashed var(--bk-theme-border-default);
  }

  /* 字段/操作符共用 wrap，宽度跟各自 grid 列走，不能写死 260px（会撑破操作符列叠到 value） */
  .locked-select-wrap {
    display: block;
    width: 100%;
    min-width: 0;
  }

  .field-select,
  .operator-select {
    width: 100%;
  }

  .locked-select-wrap :deep(.match-scope-field-trigger) {
    width: 100%;
  }

  /* 命中策略行操作符禁用：置灰即可，不必再显示禁止光标 */
  .operator-select :deep(.is-disabled),
  .operator-select.is-disabled,
  .operator-select :deep(.bk-select-tag.is-disabled),
  .operator-select :deep(.bk-input.is-disabled) {
    cursor: default;
  }

  .operator-option-label {
    display: block;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .value-input {
    min-width: 0;
  }

  .value-input--empty {
    display: block;
    height: 32px;
  }

  .icon-group {
    display: flex;
    gap: var(--bk-theme-space-12);
    align-items: center;
    height: 32px;
    font-size: 14px;
    line-height: 1;
    color: var(--bk-theme-text-disabled);
  }

  .expr-action-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }

  .add-group {
    display: flex;
    gap: var(--bk-theme-space-4);
    align-items: center;
    justify-content: flex-start;
    width: 100%;
    height: 32px;
    padding: 0 var(--bk-theme-space-12);
    font-size: var(--bk-theme-font-size-sm);
    font-weight: var(--bk-theme-font-weight-regular);
    line-height: var(--bk-theme-line-height-sm);
    color: var(--bk-theme-color-brand-2);
    text-align: left;
    cursor: pointer;
    background: var(--bk-theme-surface-subtle);
    border: 1px dashed var(--bk-theme-border-default);
    border-radius: var(--bk-theme-radius-8);
  }

  .add-group-icon {
    font-size: 12px;
  }

  .duration-line {
    display: flex;
    gap: var(--bk-theme-space-8);
    align-items: center;
  }

  .duration-group {
    display: flex;
    flex-shrink: 0;
  }

  .duration-item {
    position: relative;
    width: 80px;
    height: 32px;
    font-size: var(--bk-theme-font-size-sm);
    line-height: 30px;
    color: var(--bk-theme-text-strong);
    cursor: pointer;
    background: var(--bk-theme-surface-default);
    border: 1px solid var(--bk-theme-border-default);
  }

  .duration-item + .duration-item {
    margin-left: -1px;
  }

  .duration-item + .duration-item {
    margin-left: -1px;
  }

  .duration-item:first-child {
    border-radius: var(--bk-theme-control-radius) 0 0 var(--bk-theme-control-radius);
  }

  .duration-item:last-child {
    border-radius: 0 var(--bk-theme-control-radius) var(--bk-theme-control-radius) 0;
  }

  .duration-item.is-active {
    z-index: 1;
    color: var(--bk-theme-color-brand-2);
    background: var(--bk-theme-color-brand-6);
    border-color: var(--bk-theme-color-brand-2);
  }

  .duration-item.is-disabled {
    color: var(--bk-theme-text-disabled);
    cursor: not-allowed;
    background: var(--bk-theme-surface-subtle);
  }

  .form-content :deep(textarea) {
    height: 60px;
    min-height: 60px;
  }

  .form-content :deep(.bk-textarea--max-length) {
    word-spacing: -0.42em;
  }

  .type-alert {
    margin-top: var(--bk-theme-space-8);
  }

  .custom-expire {
    flex: 1;
    min-width: 200px;
    margin-top: 0;
  }

  .expire-preview {
    margin-top: var(--bk-theme-space-8);
    font-size: var(--bk-theme-font-size-sm);
    line-height: var(--bk-theme-line-height-sm);
    color: var(--bk-theme-text-default);
  }

  .field-tip,
  .field-error {
    margin-top: var(--bk-theme-space-4);
    font-size: var(--bk-theme-font-size-sm);
  }

  .field-tip {
    color: var(--bk-theme-color-warn-1);
  }

  .field-error {
    color: var(--bk-theme-color-danger-2);
  }

  .expire-line {
    display: flex;
    gap: var(--bk-theme-space-12);
    align-items: center;
  }

  .expire-box {
    display: flex;
    gap: var(--bk-theme-space-8);
    align-items: center;
    width: 240px;
    height: 32px;
    padding: 0 var(--bk-theme-space-8);
    font-size: var(--bk-theme-font-size-sm);
    line-height: var(--bk-theme-line-height-sm);
    color: var(--bk-theme-text-strong);
    background: var(--bk-theme-surface-subtle);
    border-radius: var(--bk-theme-tag-radius);
  }

  .expired-text {
    color: var(--bk-theme-color-danger-2);
  }

  .renew-link {
    height: 32px;
    padding: 0;
    font-size: var(--bk-theme-font-size-sm);
  }

  .input-suffix {
    padding-right: var(--bk-theme-space-8);
    color: var(--bk-theme-text-weak);
  }
</style>
<style lang="postcss">
  .risk-whitelist-date-dropdown {
    z-index: 30000;
  }

  /* 宽度跟随触发器；仅补齐选项省略样式，溢出靠 tip */
  .risk-whitelist-operator-select-popover .operator-option-label {
    display: block;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
