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
                  <bk-select
                    class="field-select"
                    :disabled="isStrategyRow(groupIndex, conditionIndex)"
                    :model-value="condition.field"
                    @change="(value: string) => changeField(groupIndex, conditionIndex, value)">
                    <bk-option
                      v-for="field in selectableFields(groupIndex, conditionIndex)"
                      :key="field.field"
                      :label="field.label"
                      :value="field.field" />
                  </bk-select>
                  <bk-select
                    class="operator-select"
                    :model-value="condition.operator"
                    @change="(value: string) => changeOperator(groupIndex, conditionIndex, value)">
                    <bk-option
                      v-for="item in OPERATOR_OPTIONS"
                      :key="item.value"
                      :label="item.label"
                      :value="item.value" />
                  </bk-select>
                  <bk-select
                    v-if="condition.field === 'strategy_id'"
                    class="value-input"
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
                  <bk-input
                    v-else
                    class="value-input"
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
            :content="t('只有命中策略条件时不允许误报加白')"
            :disabled="!falsePositiveDisabled"
            placement="top"
            reference-cls="false-positive-tip"
            theme="dark">
            <span class="false-positive-wrap">
              <bk-radio
                :disabled="falsePositiveDisabled"
                label="false_positive">
                {{ t('误报加白') }}
              </bk-radio>
            </span>
          </bk-popover>
          <bk-radio label="risk_acceptance">
            {{ t('冒险加白') }}
          </bk-radio>
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
      v-if="showApplyHint && !roleText.isAdmin.value"
      class="type-alert"
      theme="info"
      :title="t(roleText.text.value.applyHint)" />
  </div>
</template>
<script setup lang="ts">
  import dayjs from 'dayjs';
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

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

  import useWhitelistRoleText from '@hooks/use-whitelist-role-text';

  import {
    calcExpireAt,
    createDefaultScope,
    createGroup,
    createStrategyCondition,
    DURATION_OPTIONS,
    everyGroupHasStrategy,
    FALLBACK_CONDITION_FIELDS,
    hasStrategyOnlyGroup,
    OPERATOR_OPTIONS,
  } from '@components/risk-whitelist/constants';

  interface Props {
    record?: RiskWhitelist | null;
    showApplyHint?: boolean;
    embedded?: boolean;
    initialScope?: MatchScope | null;
  }

  const props = withDefaults(defineProps<Props>(), {
    record: null,
    showApplyHint: false,
    embedded: false,
    initialScope: null,
  });

  const { t } = useI18n();
  const roleText = useWhitelistRoleText();

  const scope = ref<MatchScope>(createDefaultScope());
  const whitelistType = ref<WhitelistType>('false_positive');
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

  const isEdit = computed(() => Boolean(props.record?.id));
  const falsePositiveDisabled = computed(() => hasStrategyOnlyGroup(scope.value));
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

  const markDirty = () => {
    dirty.value = true;
  };

  const fillFromRecord = (record: RiskWhitelist | null) => {
    dirty.value = false;
    renewedExpire.value = '';
    renewedActive.value = false;
    renewEditing.value = false;
    if (!record) {
      scope.value = props.initialScope?.groups?.length
        ? JSON.parse(JSON.stringify(props.initialScope))
        : createDefaultScope();
      whitelistType.value = hasStrategyOnlyGroup(scope.value) ? 'risk_acceptance' : 'false_positive';
      validityMode.value = whitelistType.value === 'risk_acceptance' ? '1m' : 'permanent';
      customDays.value = 1;
      customExpire.value = '';
      reason.value = '';
      return;
    }
    scope.value = JSON.parse(JSON.stringify(record.match_scope?.groups?.length
      ? record.match_scope
      : createDefaultScope()));
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
    }
  });
  watch(falsePositiveDisabled, (disabled) => {
    if (disabled && whitelistType.value === 'false_positive') {
      whitelistType.value = 'risk_acceptance';
    }
  });

  const applyStrategyNames = (named: Array<{ id: string; name: string }>) => {
    if (!named.length) return;
    const nameMap = new Map(named.map(item => [item.id, item.name]));
    strategyOptions.value = [
      ...named,
      ...strategyOptions.value.filter(item => !nameMap.has(item.id)),
    ];
    scope.value = {
      ...scope.value,
      groups: scope.value.groups.map(group => ({
        ...group,
        conditions: group.conditions.map((condition) => {
          if (condition.field !== 'strategy_id') return condition;
          const name = nameMap.get(String(condition.value));
          return name ? { ...condition, value_display: name } : condition;
        }),
      })),
    };
  };

  const loadSelectedStrategyNames = async () => {
    const ids = [...new Set(scope.value.groups.flatMap(group => group.conditions)
      .filter(item => item.field === 'strategy_id' && item.value)
      .map(item => String(item.value)))];
    const named = (await Promise.all(ids.map(async (id) => {
      const numericId = Number(id);
      if (!numericId) return null;
      const current = strategyOptions.value.find(item => item.id === id);
      if (current && current.name !== id && !/^\d+$/.test(current.name)) return null;
      try {
        const info = await StrategyManageService.fetchStrategyInfo({ strategy_id: numericId });
        if (!info?.strategy_name) return null;
        return { id, name: `${info.strategy_name}(${id})` };
      } catch {
        return null;
      }
    }))).filter((item): item is { id: string; name: string } => !!item);
    applyStrategyNames(named);
  };

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

  const searchStrategy = (keyword = '') => {
    seedSelectedStrategies();
    strategyLoading.value = true;
    StrategyManageService.fetchStrategyList({
      name: keyword,
      page: 1,
      page_size: 20,
    }).then((data) => {
      const fetched = (data.results || []).map(item => ({
        id: String(item.strategy_id),
        name: `${item.strategy_name}(${item.strategy_id})`,
      }));
      const selected = scope.value.groups.flatMap(group => group.conditions)
        .filter(item => item.field === 'strategy_id' && item.value)
        .map(item => ({ id: String(item.value), name: item.value_display || String(item.value) }));
      const ids = new Set(fetched.map(item => item.id));
      strategyOptions.value = [
        ...selected.filter(item => !ids.has(item.id)),
        ...fetched,
      ];
      return loadSelectedStrategyNames();
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

  const selectableFields = (groupIndex: number, conditionIndex: number) => {
    if (isStrategyRow(groupIndex, conditionIndex)) {
      return FALLBACK_CONDITION_FIELDS.filter(item => item.field === 'strategy_id');
    }
    return FALLBACK_CONDITION_FIELDS.filter(item => item.field !== 'strategy_id');
  };

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
  };

  const toggleInnerConnector = (groupIndex: number) => {
    const group = scope.value.groups[groupIndex];
    const next: LogicConnector = innerConnector(group) === 'and' ? 'or' : 'and';
    group.conditions.forEach((condition, index) => {
      if (index > 0) condition.connector = next;
    });
    markDirty();
  };

  const changeWhitelistType = (value: WhitelistType) => {
    whitelistType.value = value;
    markDirty();
  };

  const changeValidityMode = (value: ValidityMode) => {
    if (value === 'permanent' && whitelistType.value === 'risk_acceptance') return;
    validityMode.value = value;
    markDirty();
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
  };

  const changeReason = (value: string) => {
    reason.value = value;
    markDirty();
  };

  const changeField = (groupIndex: number, conditionIndex: number, field: string) => {
    const meta = FALLBACK_CONDITION_FIELDS.find(item => item.field === field);
    if (!meta) return;
    markDirty();
    patchCondition(groupIndex, conditionIndex, {
      field: meta.field,
      field_name: meta.name,
      field_label: meta.label,
      operator: 'eq',
      value: '',
      value_display: '',
    });
  };

  const changeOperator = (groupIndex: number, conditionIndex: number, value: string) => {
    patchCondition(groupIndex, conditionIndex, { operator: value as CompareOperator });
    markDirty();
  };

  const changeStrategy = (groupIndex: number, conditionIndex: number, value: string) => {
    markDirty();
    const option = strategyOptions.value.find(item => item.id === value);
    patchCondition(groupIndex, conditionIndex, {
      value,
      value_display: option?.name || value,
    });
  };

  const changeTextValue = (groupIndex: number, conditionIndex: number, value: string) => {
    markDirty();
    patchCondition(groupIndex, conditionIndex, {
      value,
      value_display: value,
    });
  };

  const addCondition = (groupIndex: number, conditionIndex: number) => {
    const field = FALLBACK_CONDITION_FIELDS[1];
    const next: MatchCondition = {
      field: field.field,
      field_name: field.name,
      field_label: field.label,
      operator: 'eq',
      value: '',
      value_display: '',
      connector: 'and',
    };
    scope.value.groups[groupIndex].conditions.splice(conditionIndex + 1, 0, next);
    markDirty();
  };

  const canRemoveCondition = (groupIndex: number, conditionIndex: number) => {
    const group = scope.value.groups[groupIndex];
    if (group.conditions.length <= 1) return false;
    return !isStrategyRow(groupIndex, conditionIndex);
  };

  const removeCondition = (groupIndex: number, conditionIndex: number) => {
    const group = scope.value.groups[groupIndex];
    if (group.conditions.length === 1) {
      scope.value.groups.splice(groupIndex, 1);
      markDirty();
      return;
    }
    group.conditions.splice(conditionIndex, 1);
    markDirty();
  };

  const removeGroup = (groupIndex: number) => {
    if (scope.value.groups.length <= 1) return;
    scope.value.groups.splice(groupIndex, 1);
    markDirty();
  };

  const addGroup = () => {
    markDirty();
    scope.value.groups.push(createGroup(scope.value.groups.length ? 'and' : 'and'));
    if (!scope.value.groups[scope.value.groups.length - 1].conditions.length) {
      scope.value.groups[scope.value.groups.length - 1].conditions.push(createStrategyCondition());
    }
  };

  const validate = () => {
    scopeError.value = '';
    validityError.value = '';
    reasonError.value = '';
    const missingValue = scope.value.groups.some(group => group.conditions.some(item => !item.value));
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
      match_scope: scope.value,
      whitelist_type: whitelistType.value,
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

  .false-positive-wrap {
    display: inline-flex;
    align-items: center;
  }

  :deep(.false-positive-tip) {
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
    border: 1px solid var(--bk-theme-color-warn-2);
    border-radius: var(--bk-theme-tag-radius);
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
    grid-template-columns: 260px 160px minmax(0, 1fr) minmax(40px, auto);
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

  .field-select {
    width: 260px;
  }

  .operator-select {
    width: 160px;
  }

  .value-input {
    min-width: 0;
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
    width: 80px;
    height: 32px;
    margin-right: -var(--bk-theme-space-2);
    font-size: var(--bk-theme-font-size-sm);
    line-height: 30px;
    color: var(--bk-theme-text-strong);
    cursor: pointer;
    background: var(--bk-theme-surface-default);
    border: 1px solid var(--bk-theme-text-disabled);
  }

  .duration-item:first-child {
    border-radius: var(--bk-theme-control-radius) 0 0 var(--bk-theme-control-radius);
  }

  .duration-item:last-child {
    border-radius: 0 var(--bk-theme-control-radius) var(--bk-theme-control-radius) 0;
  }

  .duration-item.is-active {
    position: relative;
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
</style>
