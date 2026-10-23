<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<!-- step-risk-rules -->
<template>
  <smart-action
    class="create-strategy-page"
    :offset-target="getSmartActionOffsetTarget">
    <div class="create-strategy-main">
      <!-- 外层白色卡片 -->
      <div class="risk-rules-card">
        <!-- 标题行 -->
        <div class="risk-rules-card-header">
          <div class="risk-rules-card-title-row">
            <span class="risk-rules-title">{{ t('风险发现规则') }}</span>
            <audit-icon
              v-bk-tooltips="{
                content: t('当一条数据源数据同时命中多条规则时，将采用自上而下的优先级匹配，仅最先匹配到的规则生效。'),
                placement: 'top-start'
              }"
              class="risk-rules-tip-icon"
              type="tishi" />
            <span class="risk-rules-tip-text">
              {{ t('当一条数据源数据同时命中多条规则时，将采用自上而下的优先级匹配，仅最先匹配到的规则生效。') }}
            </span>
          </div>
        </div>
        <div class="risk-rules-actions">
            <bk-button
              @click="handleAddRule">
              <audit-icon
                class="add-rule-icon"
                type="add" />
              {{ t('添加规则') }}
            </bk-button>
            <bk-button
              class="ml8"
              @click="handleToggleAllCollapse">
              <img
                alt=""
                class="collapse-toggle-icon"
                :src="allCollapsed ? expandIcon : collapseIcon">
              {{ allCollapsed ? t('一键展开') : t('一键收起') }}
            </bk-button>
          </div>

        <!-- 规则列表 -->
        <vuedraggable
          ref="ruleListRef"
          class="rule-list"
          ghost-class="rule-item-ghost"
          handle=".rule-drag-handle"
          item-key="id"
          :list="ruleItems"
          @end="handleRuleDragEnd">
          <template #item="{ element: rule, index }">
            <div
              class="rule-item-card"
              :class="{ 'is-collapsed': rule.collapsed }">
              <!-- 规则卡片头部：点击空白栏展开/收起 -->
              <div
                class="rule-item-header"
                @click="() => toggleCollapse(index)">
                <span
                  class="rule-drag-handle"
                  title="拖拽排序"
                  @click.stop>
                  <audit-icon type="move" />
                </span>
                <audit-icon
                  class="rule-collapse-icon"
                  :class="{ 'is-collapsed': rule.collapsed }"
                  type="angle-fill-down" />

                <!-- 规则名称（可编辑） -->
                <template v-if="rule.editingName">
                  <input
                    ref="nameInputRefs"
                    v-model="rule.name"
                    class="rule-name-input"
                    type="text"
                    @blur="() => stopEditName(index)"
                    @click.stop
                    @keydown.enter="() => stopEditName(index)">
                </template>
                <template v-else>
                  <div class="rule-name-wrap">
                    <span class="rule-name">{{ rule.name }}</span>
                    <audit-icon
                      class="rule-name-edit-icon"
                      type="edit-fill"
                      @click.stop="() => startEditName(index)" />
                  </div>
                </template>

                <!-- 头部右侧操作 -->
                <div
                  class="rule-header-actions"
                  @click.stop>
                  <audit-icon
                    v-bk-tooltips="t('复制')"
                    class="rule-action-icon"
                    type="copy"
                    @click="() => handleCloneRule(index)" />
                  <audit-popconfirm
                    v-if="ruleItems.length > 1"
                    :cancel-text="t('取消')"
                    :confirm-handler="() => handleDeleteRule(index)"
                    :confirm-text="t('删除')"
                    :content="t('确认删除「{name}」？删除后不可恢复。', { name: rule.name })"
                    placement="bottom-end"
                    :title="t('确认删除该规则？')">
                    <audit-icon
                      v-bk-tooltips="t('删除')"
                      class="rule-action-icon rule-action-delete"
                      type="delete" />
                  </audit-popconfirm>
                </div>
              </div>

              <!-- 规则卡片内容 -->
              <div
                v-show="!rule.collapsed"
                class="rule-item-content">
                <!-- 命中条件 -->
                <div class="rule-section">
                  <div class="rule-section-label is-required">
                    <span
                      v-bk-tooltips="{
                        content: t('命中匹配条件的数据记录将生成一条审计风险工单'),
                        placement: 'top-start',
                      }"
                      class="rule-section-label-tip">
                      {{ t('命中条件') }}
                    </span>
                  </div>
                  <div class="rule-section-body rule-section-body--condition">
                    <audit-form
                      :ref="(el: any) => setFormRef(el, index)"
                      class="rule-condition-form"
                      form-type="vertical"
                      :model="rule.formData">
                      <component
                        :is="strategyWayComMap[stepFormData.strategy_type]"
                        :ref="(el: any) => setComRef(el, index)"
                        :edit-data="getRuleEditData(index)"
                        :parent-configs="parentConfigs"
                        :parent-form-data="parentFormData"
                        step-mode="rules-only"
                        @update-form-data="(data: any) => updateRuleFormData(data, index)" />
                    </audit-form>
                  </div>
                </div>

                <!-- 风险单标题 -->
                <div class="rule-section is-field-narrow">
                  <div class="rule-section-label is-required">
                    {{ t('风险单标题') }}
                  </div>
                  <div class="rule-section-body">
                    <div
                      class="variable-input-content"
                      :class="[rule.variableInputActive ? 'active' : '']"
                      @click.stop="() => activateRiskTitleEdit(index)">
                      <ul class="variable-input-list">
                        <template v-if="!rule.variableInputActive">
                          <li
                            v-for="(item, i) in getDisplayRiskTitle(rule.risk_title)"
                            :key="i"
                            @click="handleClickTitleLi(index, i)">
                            <span :class="[item.isVariable ? 'is-variable' : '']">
                              {{ item.value }}
                            </span>
                          </li>
                        </template>
                        <li
                          v-else
                          class="list-item-input">
                          <input
                            :ref="(el: any) => setTitleInputRef(el, index)"
                            v-model="rule.riskTitleInputValue"
                            class="title-input"
                            type="text"
                            @click.stop="(e) => rememberTitleCaret(index, e)"
                            @keyup="(e) => rememberTitleCaret(index, e)"
                            @input="(e) => rememberTitleCaret(index, e)"
                            @keydown="(e) => handleTitleKeyDown(e, index)">
                        </li>
                      </ul>
                      <p
                        v-if="!rule.variableInputActive && !rule.risk_title"
                        class="variable-input-placeholder">
                        {{ t('请输入') }}
                      </p>
                    </div>
                    <bk-popover
                      :arrow="false"
                      ext-cls="bksec-var-popover"
                      placement="bottom-end"
                      theme="light"
                      trigger="click"
                      width="480"
                      @after-hidden="setTitleVarOpen(index, false)"
                      @after-show="setTitleVarOpen(index, true)">
                      <button
                        class="reference-variable-btn"
                        :class="{ 'is-open': titleVarOpen[index] }"
                        type="button"
                        @click="() => activateRiskTitleEdit(index)">
                        <audit-icon
                          class="reference-variable-icon"
                          type="bianliang" />
                        {{ t('引用变量') }}
                      </button>
                      <template #content>
                        <variable-popover
                          :groups="titleVariableGroups"
                          @insert="(text) => insertTitleVariable(index, text)" />
                      </template>
                    </bk-popover>
                  </div>
                </div>

                <!-- 风险等级 -->
                <div class="rule-section is-field-narrow">
                  <div class="rule-section-label is-required">
                    <span class="rule-section-label-tip is-plain">
                      {{ t('风险等级') }}
                    </span>
                  </div>
                  <div class="rule-section-body">
                    <div class="risk-level-group">
                      <button
                        v-for="level in riskLevelOptions"
                        :key="level.value"
                        class="risk-level-btn"
                        :class="[
                          `level-${level.value.toLowerCase()}`,
                          rule.risk_level === level.value ? 'is-active' : ''
                        ]"
                        type="button"
                        @click="() => rule.risk_level = level.value">
                        {{ level.label }}
                      </button>
                    </div>
                  </div>
                </div>

                <!-- 审计策略：处理人 / 关注人写入 rules；全局策略在分派规则中维护 -->
                <div
                  v-if="showRuleNoticeGroups"
                  class="rule-section rule-section-two-col">
                  <div class="rule-section-col">
                    <div class="rule-section-label is-required">
                      {{ t('风险单处理人') }}
                    </div>
                    <div class="rule-section-body">
                      <notice-group-select
                        v-model="rule.processor"
                        :check-result-map="checkResultMap"
                        :group-list="groupList"
                        :loading="isGroupLoading"
                        @refresh="refreshGroupList" />
                    </div>
                  </div>
                  <div class="rule-section-col">
                    <div class="rule-section-label">
                      {{ t('关注人') }}
                    </div>
                    <div class="rule-section-body">
                      <notice-group-select
                        v-model="rule.follower"
                        :check-result-map="checkResultMap"
                        :group-list="groupList"
                        :loading="isGroupLoading"
                        @refresh="refreshGroupList" />
                    </div>
                  </div>
                </div>

                <div class="rule-section rule-section-two-col">
                  <div class="rule-section-col">
                    <div class="rule-section-label">
                      {{ t('风险危害') }}
                    </div>
                    <div class="rule-section-body">
                      <bk-input
                        v-model="rule.risk_hazard"
                        class="rule-text-count"
                        :maxlength="100"
                        :placeholder="t('请输入')"
                        :rows="2"
                        show-word-limit
                        type="textarea" />
                    </div>
                  </div>
                  <div class="rule-section-col">
                    <div class="rule-section-label">
                      {{ t('处理指引') }}
                    </div>
                    <div class="rule-section-body">
                      <bk-input
                        v-model="rule.risk_guidance"
                        class="rule-text-count"
                        :maxlength="100"
                        :placeholder="t('请输入')"
                        :rows="2"
                        show-word-limit
                        type="textarea" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </vuedraggable>

        <!-- 空状态 -->
        <div
          v-if="ruleItems.length === 0"
          class="rule-list-empty">
          <p>{{ t('暂无规则，点击「添加规则」新增') }}</p>
        </div>
      </div>
    </div>

    <template #action>
      <bk-button @click="handlePrevious">
        {{ t('上一步') }}
      </bk-button>
      <bk-button
        class="ml8"
        theme="primary"
        @click="handleNext">
        {{ t('下一步') }}
      </bk-button>
      <bk-button
        v-if="showSaveDraftButton"
        class="ml8"
        @click="handleSaveDraft">
        {{ t('保存草稿') }}
      </bk-button>
      <bk-button
        class="ml8"
        @click="handleCancel">
        {{ t('取消') }}
      </bk-button>
    </template>
  </smart-action>
</template>
<script setup lang="ts">
  import {
    computed,
    inject,
    nextTick,
    onActivated,
    onDeactivated,
    onUnmounted,
    provide,
    reactive,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';
  import Vuedraggable from 'vuedraggable';
  import _ from 'lodash';

  import IamManageService from '@service/iam-manage';
  import NoticeManageService from '@service/notice-group';
  import StrategyManageService from '@service/strategy-manage';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';
  import StrategyFieldEvent from '@model/strategy/strategy-field-event';
  import StrategyModel from '@model/strategy/strategy';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';
  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  import collapseIcon from '@images/collapse.svg';
  import expandIcon from '@images/expand.svg';

  import Customize from '../step1/components/customize/index.vue';
  import ReferenceModel from '../step1/components/reference-model/index.vue';
  import NoticeGroupSelect from '../step3/components/notice-group-select.vue';
  import VariablePopover from '../step-bksec/variable-popover.vue';
  import type { VariableGroup, VariableItem } from '../step-bksec/variable-groups';

  import {
    getStrategyRouteNames,
    isPlatformStrategyRoute,
    isStrategyCloneRoute,
    isStrategyEditRoute,
  } from '../../../utils/strategy-routes';
  import {
    applyScheduleConfigForSubmit,
    excludeHavingFromWhere,
    hasFilledWhereConditions,
    normalizeWhereHaving,
    toNoticeGroupIds,
  } from '../../utils/strategy-protocol';
  import { STRATEGY_SHOW_SAVE_DRAFT_KEY } from '../../composables/use-strategy-config-lock';

  interface RuleItem {
    id: number;
    rule_id?: number;
    name: string;
    collapsed: boolean;
    editingName: boolean;
    variableInputActive: boolean;
    showVariablePanel: boolean;
    isVariableCopy: boolean;
    clickLiIndex: number;
    riskTitleInputValue: string;
    risk_title: string;
    risk_level: string;
    risk_hazard: string;
    risk_guidance: string;
    processor?: Array<string | number>;
    follower?: Array<string | number>;
    conditions?: Record<string, any>;
    formData: Record<string, any>;
  }

  interface Props {
    editData: StrategyModel,
    formData: Record<string, any>,
    select: Array<DatabaseTableFieldModel>,
  }

  interface Emits {
    (e: 'nextStep', step: number, params: Record<string, any>): void;
    (e: 'previousStep', step: number, params: Record<string, any>): void;
    (e: 'saveDraft', params: Record<string, any>): void;
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const titleVarOpen = reactive<Record<number, boolean>>({});
  const setTitleVarOpen = (index: number, open: boolean) => {
    titleVarOpen[index] = open;
  };

  const router = useRouter();
  const route = useRoute();
  const strategyRoutes = getStrategyRouteNames(route);
  const { t } = useI18n();
  const { messageError } = useMessage();

  const isEditMode = isStrategyEditRoute(route.name);
  const isCloneMode = isStrategyCloneRoute(route.name);
  const showSaveDraftButton = inject(STRATEGY_SHOW_SAVE_DRAFT_KEY, computed(() => true));
  // 审计策略才在发现规则里选处理人/关注人；全局策略这两项在分派规则维护，这里不请求通知组
  const showRuleNoticeGroups = !isPlatformStrategyRoute(route.name);

  const {
    data: checkResultMap,
  } = useRequest(IamManageService.check, {
    defaultParams: {
      action_ids: 'list_notice_group_v2,create_notice_group_v2',
      resources: getSceneSystemParams().scope_id,
    },
    defaultValue: {},
    manual: showRuleNoticeGroups,
  });

  const {
    loading: isGroupLoading,
    data: groupList,
    run: fetchGroupList,
  } = useRequest(NoticeManageService.fetchGroupSelectList, {
    defaultValue: [],
    defaultParams: {
      page_size: 1000,
      page: 1,
    },
    manual: showRuleNoticeGroups,
  });

  const refreshGroupList = () => {
    groupList.value = [];
    fetchGroupList();
  };

  const strategyWayComMap: Record<string, any> = {
    rule: Customize,
    model: ReferenceModel,
  };

  const formRefs = ref<Array<any>>([]);
  const formRef = computed(() => ({
    validate: (fields?: string | Array<string>) => Promise.all(formRefs.value
      .filter(Boolean)
      .map(item => item.validate(fields))),
    clearValidate: (fields?: string | Array<string>) => {
      formRefs.value.forEach(item => item?.clearValidate?.(fields));
    },
  }));
  provide('strategyStep1FormRef', formRef);

  const stepFormData = ref({
    strategy_name: '',
    strategy_type: 'rule',
    configs: {},
    status: '',
    risk_level: 'MIDDLE',
  });

  const parentFormData = computed(() => props.formData ?? {});
  const parentConfigs = computed(() => props.formData?.configs ?? {});
  const selectFields = computed(() => props.select ?? parentFormData.value.configs?.select ?? []);
  const strategyIdForFields = computed(() => String(
    props.editData?.strategy_id || props.formData?.strategy_id || '',
  ));

  const { data: strategyEvent, run: fetchTitleEventFields } = useRequest(StrategyManageService.fetchStrategyEvent, {
    defaultValue: new StrategyFieldEvent(),
    manual: false,
  });

  const toTitleVariableItem = (field: {
    field_name?: string;
    display_name?: string;
    prefix?: string;
    example?: string;
  }): VariableItem | null => {
    const fieldName = field.field_name || '';
    if (!fieldName) return null;
    const prefix = field.prefix || '';
    const token = prefix ? `${prefix}["${fieldName}"]` : fieldName;
    return {
      token,
      label: field.display_name || fieldName,
      sample: field.example || '',
      insertText: prefix ? `{{ ${token} }}` : `{{ ${fieldName} }}`,
    };
  };

  const titleVariableGroups = computed<VariableGroup[]>(() => {
    const configuredBasic = props.formData?.event_basic_field_configs || [];
    const basicSource = configuredBasic.length
      ? configuredBasic
      : (strategyEvent.value?.event_basic_field_configs || []);
    const basicItems = basicSource
      .map((item: { field_name?: string; display_name?: string; prefix?: string; example?: string }) => (
        toTitleVariableItem({ ...item, prefix: item.prefix || '' })
      ))
      .filter((item: VariableItem | null): item is VariableItem => !!item);
    const eventItems = (selectFields.value || [])
      .map((item: DatabaseTableFieldModel) => toTitleVariableItem({
        field_name: item.display_name || item.raw_name,
        display_name: item.display_name || item.raw_name,
        prefix: 'event_data',
      }))
      .filter((item: VariableItem | null): item is VariableItem => !!item);
    const groups: VariableGroup[] = [];
    if (basicItems.length) {
      groups.push({ key: 'risk', label: '基本信息', items: basicItems });
    }
    if (eventItems.length) {
      groups.push({ key: 'event', label: '事件字段', items: eventItems });
    }
    return groups;
  });

  watch(strategyIdForFields, (id) => {
    fetchTitleEventFields({ strategy_id: id });
  }, { immediate: true });

  let ruleIdSeq = 1;

  const createRule = (overrides: Partial<RuleItem> = {}): RuleItem => {
    const id = ruleIdSeq;
    ruleIdSeq += 1;
    return {
      id,
      name: overrides.name ?? `规则${id}`,
      collapsed: false,
      editingName: false,
      variableInputActive: false,
      showVariablePanel: false,
      isVariableCopy: false,
      clickLiIndex: -1,
      riskTitleInputValue: '',
      risk_title: '',
      risk_level: 'HIGH',
      risk_hazard: '',
      risk_guidance: '',
      processor: [],
      follower: [],
      formData: {},
      ...overrides,
    };
  };

  const ruleItems = ref<RuleItem[]>([createRule({ name: '规则1' })]);
  const syncedEditStrategyId = ref<number | null>(null);
  const draftRulesSynced = ref(false);

  const comRefs = ref<Array<any>>([]);
  const titleInputRefs = ref<Array<HTMLInputElement | null>>([]);
  const titleCarets = ref<number[]>([]);

  const setComRef = (el: any, index: number) => {
    comRefs.value[index] = el;
  };

  const setFormRef = (el: any, index: number) => {
    formRefs.value[index] = el;
  };

  const setTitleInputRef = (el: any, index: number) => {
    titleInputRefs.value[index] = el;
  };

  const ruleListRef = ref<HTMLElement>();

  const allCollapsed = computed(() => ruleItems.value.every(r => r.collapsed));

  const riskLevelOptions = [
    { label: t('高'), value: 'HIGH' },
    { label: t('中'), value: 'MIDDLE' },
    { label: t('低'), value: 'LOW' },
  ];

  const getDisplayRiskTitle = (riskTitle: string) => {
    const arr = riskTitle.match(/\{\{[^{}]*}}|./gs);
    if (!arr) return [];
    return arr.map(item => ({
      value: item,
      isVariable: item.startsWith('{{') && item.endsWith('}}'),
    }));
  };

  const getRiskTitleCharIndex = (
    display: Array<{ value: string }>,
    liIndex: number,
  ) => {
    if (liIndex < 0) {
      return display.reduce((sum, item) => sum + item.value.length, 0);
    }
    return display.slice(0, liIndex).reduce((sum, item) => sum + item.value.length, 0);
  };

  const getSmartActionOffsetTarget = () => document.querySelector('.create-strategy-page');

  const toggleCollapse = (index: number) => {
    ruleItems.value[index].collapsed = !ruleItems.value[index].collapsed;
  };

  const handleToggleAllCollapse = () => {
    const shouldCollapse = !allCollapsed.value;
    ruleItems.value.forEach((_, i) => {
      ruleItems.value[i].collapsed = shouldCollapse;
    });
  };

  const handleAddRule = () => {
    const newRule = createRule({ name: `规则${ruleItems.value.length + 1}` });
    ruleItems.value.push(newRule);
    nextTick(() => {
      const listEl = (ruleListRef.value as { $el?: HTMLElement } | HTMLElement | null);
      const container = (listEl && '$el' in listEl ? listEl.$el : listEl) as HTMLElement | null | undefined;
      container?.lastElementChild?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  };

  const handleCloneRule = (index: number) => {
    const source = ruleItems.value[index];
    const com = comRefs.value[index];
    const fields = com?.getFields?.({ forValidate: false })
      ?? { configs: source.formData?.configs ?? {} };
    const configs = _.cloneDeep(fields.configs ?? source.formData?.configs ?? {});
    if (!configs.where && source.conditions?.where) {
      configs.where = _.cloneDeep(source.conditions.where);
    }
    if (!Object.prototype.hasOwnProperty.call(configs, 'having') && source.conditions?.having) {
      configs.having = _.cloneDeep(source.conditions.having);
    }

    const cloned = createRule({
      name: `${source.name}_复制`,
      risk_title: `${source.risk_title || ''}${source.riskTitleInputValue || ''}`,
      risk_level: source.risk_level,
      risk_hazard: source.risk_hazard,
      risk_guidance: source.risk_guidance,
      processor: [...(source.processor ?? [])],
      follower: [...(source.follower ?? [])],
      conditions: {
        where: _.cloneDeep(configs.where),
        having: _.cloneDeep(configs.having),
      },
      formData: { configs },
    });
    ruleItems.value.splice(index + 1, 0, cloned);
    comRefs.value.splice(index + 1, 0, null);
    formRefs.value.splice(index + 1, 0, null);
    titleInputRefs.value.splice(index + 1, 0, null);
    titleCarets.value.splice(index + 1, 0, 0);
  };

  const handleDeleteRule = (index: number) => {
    if (ruleItems.value.length <= 1) {
      return Promise.resolve();
    }
    ruleItems.value.splice(index, 1);
    comRefs.value.splice(index, 1);
    formRefs.value.splice(index, 1);
    titleInputRefs.value.splice(index, 1);
    titleCarets.value.splice(index, 1);
    return Promise.resolve();
  };

  const reorderRefArray = <T, >(items: T[], oldIndex: number, newIndex: number) => {
    const next = [...items];
    const [moved] = next.splice(oldIndex, 1);
    next.splice(newIndex, 0, moved);
    return next;
  };

  const handleRuleDragEnd = (evt: { oldIndex?: number; newIndex?: number }) => {
    const { oldIndex, newIndex } = evt;
    if (oldIndex === undefined || newIndex === undefined || oldIndex === newIndex) {
      return;
    }
    comRefs.value = reorderRefArray(comRefs.value, oldIndex, newIndex);
    formRefs.value = reorderRefArray(formRefs.value, oldIndex, newIndex);
    titleInputRefs.value = reorderRefArray(titleInputRefs.value, oldIndex, newIndex);
    titleCarets.value = reorderRefArray(titleCarets.value, oldIndex, newIndex);
  };

  const startEditName = (index: number) => {
    ruleItems.value[index].editingName = true;
    nextTick(() => {
      const inputs = document.querySelectorAll<HTMLInputElement>('.rule-name-input');
      inputs[index]?.focus();
    });
  };

  const stopEditName = (index: number) => {
    ruleItems.value[index].editingName = false;
    if (!ruleItems.value[index].name.trim()) {
      ruleItems.value[index].name = `规则${index + 1}`;
    }
  };

  const commitRiskTitleEdit = (index: number) => {
    const current = ruleItems.value[index];
    if (current.riskTitleInputValue) {
      ruleItems.value[index].risk_title += current.riskTitleInputValue;
      ruleItems.value[index].riskTitleInputValue = '';
    }
    ruleItems.value[index].variableInputActive = false;
    ruleItems.value[index].showVariablePanel = false;
    ruleItems.value[index].isVariableCopy = false;
  };

  const commitAllRiskTitleEdits = () => {
    ruleItems.value.forEach((_, i) => {
      commitRiskTitleEdit(i);
    });
  };

  const getRuleRiskTitle = (rule: RuleItem) => (
    `${rule.risk_title || ''}${rule.riskTitleInputValue || ''}`
  );

  const closeOtherRiskTitleEditors = (index: number) => {
    ruleItems.value.forEach((_, i) => {
      if (i === index) return;
      const current = ruleItems.value[i];
      if (current.variableInputActive) {
        commitRiskTitleEdit(i);
      }
    });
  };

  /** 进入标题编辑，不自动打开引用变量弹窗 */
  const activateRiskTitleEdit = (index: number) => {
    const rule = ruleItems.value[index];
    // 已在编辑态：勿重置选区，否则光标会跳回行首
    if (rule.variableInputActive) {
      return;
    }
    closeOtherRiskTitleEditors(index);
    rule.variableInputActive = true;
    const display = getDisplayRiskTitle(rule.risk_title);
    const cursorPos = getRiskTitleCharIndex(display, rule.clickLiIndex);
    if (display.length) {
      rule.riskTitleInputValue = display.map(item => item.value).join('');
      rule.risk_title = '';
    }
    nextTick(() => {
      const input = titleInputRefs.value[index];
      input?.focus();
      input?.setSelectionRange(cursorPos, cursorPos);
      titleCarets.value[index] = cursorPos;
      rule.clickLiIndex = -1;
    });
  };

  const rememberTitleCaret = (index: number, event: Event) => {
    const input = event.target as HTMLInputElement;
    titleCarets.value[index] = input.selectionStart ?? input.value.length;
  };

  const insertTitleVariable = (index: number, insertText: string) => {
    const apply = () => {
      const rule = ruleItems.value[index];
      const current = rule.riskTitleInputValue || '';
      const pos = titleCarets.value[index] ?? current.length;
      rule.riskTitleInputValue = `${current.slice(0, pos)}${insertText}${current.slice(pos)}`;
      const nextPos = pos + insertText.length;
      titleCarets.value[index] = nextPos;
      nextTick(() => {
        const input = titleInputRefs.value[index];
        input?.focus();
        input?.setSelectionRange(nextPos, nextPos);
      });
    };
    if (!ruleItems.value[index].variableInputActive) {
      activateRiskTitleEdit(index);
      nextTick(apply);
      return;
    }
    apply();
  };

  const handleClickTitleLi = (ruleIndex: number, liIndex: number) => {
    ruleItems.value[ruleIndex].clickLiIndex = liIndex;
  };

  const handleTitleKeyDown = (e: KeyboardEvent, index: number) => {
    const rule = ruleItems.value[index];
    if (e.code === 'Enter') {
      e.preventDefault();
      commitRiskTitleEdit(index);
      return;
    }
    if (e.code === 'Backspace' && getDisplayRiskTitle(rule.risk_title).length) {
      const display = getDisplayRiskTitle(rule.risk_title);
      display.pop();
      rule.risk_title = display.map(item => item.value).join('');
    }
  };

  const updateRuleFormData = (data: Record<string, any>, index: number) => {
    const prev = ruleItems.value[index];
    const nextConfigs = {
      ...(prev.formData?.configs || {}),
      ...(data.configs || {}),
    };
    // 子组件初始化会回传空 where/having，不能覆盖已同步的命中条件；
    // 只在 where、having 都为空时回退，避免用户删光聚合条件后又被旧 having 填回
    const prevWhere = prev.conditions?.where;
    const prevHaving = prev.conditions?.having;
    const nextEmpty = !hasConditionGroups(nextConfigs.where)
      && !hasConditionGroups(nextConfigs.having);
    if (nextEmpty) {
      if (hasConditionGroups(prevWhere)) {
        nextConfigs.where = _.cloneDeep(prevWhere);
      }
      if (hasConditionGroups(prevHaving)) {
        nextConfigs.having = _.cloneDeep(prevHaving);
      }
    }
    if (hasConditionGroups(nextConfigs.where) || hasConditionGroups(nextConfigs.having)) {
      ruleItems.value[index].conditions = {
        where: nextConfigs.where,
        having: nextConfigs.having,
      };
    }
    ruleItems.value[index].formData = {
      ...prev.formData,
      ...data,
      configs: nextConfigs,
    };
  };

  const mergeRuleConfigs = (fieldsConfigs: Record<string, any> = {}) => {
    const parent = parentConfigs.value ?? {};
    const merged = {
      ...parent,
      ...fieldsConfigs,
    };
    // 预期结果只在第一步维护，后续步骤不允许覆盖成空
    if (parent.select?.length) {
      merged.select = parent.select;
    } else if (!fieldsConfigs.select?.length && parent.select) {
      merged.select = parent.select;
    }
    if (!fieldsConfigs.config_type && parent.config_type) {
      merged.config_type = parent.config_type;
    }
    // data_source 按字段合并，避免后续步骤回写时丢掉 system_ids 等关键字段
    if (parent.data_source || fieldsConfigs.data_source) {
      merged.data_source = {
        ...(parent.data_source || {}),
        ...(fieldsConfigs.data_source || {}),
      };
      if (
        merged.config_type === 'EventLog'
        && !merged.data_source.system_ids?.length
        && parent.data_source?.system_ids?.length
      ) {
        merged.data_source.system_ids = [...parent.data_source.system_ids];
      }
      if (!merged.data_source.rt_id && parent.data_source?.rt_id) {
        merged.data_source.rt_id = parent.data_source.rt_id;
      }
      if (!merged.data_source.source_type && parent.data_source?.source_type) {
        merged.data_source.source_type = parent.data_source.source_type;
      }
      if (!merged.data_source.link_table?.uid && parent.data_source?.link_table?.uid) {
        merged.data_source.link_table = { ...parent.data_source.link_table };
      }
    }
    if (!fieldsConfigs.schedule_config?.count_freq && parent.schedule_config) {
      merged.schedule_config = parent.schedule_config;
    }
    // 命中条件以当前规则为准；having 为 null 表示用户已删光聚合条件，不能再用父级旧值
    if (Object.prototype.hasOwnProperty.call(fieldsConfigs, 'where')) {
      merged.where = fieldsConfigs.where;
    }
    if (Object.prototype.hasOwnProperty.call(fieldsConfigs, 'having')) {
      merged.having = fieldsConfigs.having;
    }
    return applyScheduleConfigForSubmit(merged) ?? merged;
  };

  const buildStepParams = () => {
    // 标题在编辑态写在 input 里，risk_title 会被临时置空；提交/切步前必须先落盘
    commitAllRiskTitleEdits();
    const baseFormData = { ...props.formData };
    const rules = ruleItems.value.map((rule, index) => {
      const com = comRefs.value[index];
      const fields = com?.getFields?.({ forValidate: false }) ?? { configs: rule.formData?.configs ?? {} };
      const mergedConfigs = mergeRuleConfigs(fields.configs);
      const { where, having } = normalizeWhereHaving(
        fields.configs?.where ?? mergedConfigs.where ?? null,
        Object.prototype.hasOwnProperty.call(fields.configs || {}, 'having')
          ? (fields.configs.having ?? null)
          : (mergedConfigs.having ?? null),
      );
      return {
        ...(rule.rule_id ? { rule_id: rule.rule_id } : {}),
        name: rule.name,
        rule_name: rule.name,
        risk_title: getRuleRiskTitle(rule),
        risk_level: rule.risk_level,
        risk_hazard: rule.risk_hazard,
        risk_guidance: rule.risk_guidance,
        processor: toNoticeGroupIds(rule.processor ?? []),
        follower: toNoticeGroupIds(rule.follower ?? []),
        conditions: {
          where,
          having,
        },
        configs: {
          ...mergedConfigs,
          where,
          having,
        },
      };
    });

    // 预览/步骤间兼容：顶层仍带第一条规则的风险字段；提交时会按新协议剥离
    const firstRule = rules[0] ?? {};
    const topConfigs = {
      ...(firstRule.configs ?? baseFormData.configs ?? {}),
      select: baseFormData.configs?.select?.length
        ? baseFormData.configs.select
        : (firstRule.configs?.select ?? []),
    };
    delete topConfigs.where;
    delete topConfigs.having;
    const nextTopConfigs = applyScheduleConfigForSubmit(topConfigs) ?? topConfigs;
    return {
      ...baseFormData,
      risk_title: firstRule.risk_title ?? baseFormData.risk_title ?? '',
      risk_level: firstRule.risk_level ?? baseFormData.risk_level ?? 'HIGH',
      risk_hazard: firstRule.risk_hazard ?? baseFormData.risk_hazard ?? '',
      risk_guidance: firstRule.risk_guidance ?? baseFormData.risk_guidance ?? '',
      configs: nextTopConfigs,
      rules,
    };
  };

  const hasConditionGroups = (where?: { conditions?: unknown[] } | null) => (
    hasFilledWhereConditions(where)
  );

  const pickConditionWhere = (...candidates: Array<{ conditions?: unknown[] } | null | undefined>) => (
    candidates.find(item => hasConditionGroups(item))
  );

  const getRuleEditData = (index: number) => {
    const base = getMergedSourceData();
    const localRule = ruleItems.value[index];
    const formRule = props.formData?.rules?.[index] ?? {};
    const hitConditionsReset = Number(props.formData?.hit_conditions_reset_seq) > 0;
    const emptyWhere = { connector: 'and', conditions: [] };
    // 空 { conditions: [] } 不能优先生效，否则会盖住用户刚填的命中条件
    // 预期结果变更后不再回落到详情原始 where（inheritBaseCondition 已关掉）
    const pickWhere = (...candidates: Array<{ conditions?: unknown[] } | null | undefined>) => (
      pickConditionWhere(...candidates) ?? (hitConditionsReset ? emptyWhere : undefined)
    );
    const inheritBaseCondition = !hitConditionsReset && index === 0;
    const where = pickWhere(
      localRule?.conditions?.where,
      formRule.conditions?.where,
      formRule.configs?.where,
      localRule?.formData?.configs?.where,
      inheritBaseCondition ? base.configs?.where : undefined,
    );
    const having = pickWhere(
      localRule?.conditions?.having,
      formRule.conditions?.having,
      formRule.configs?.having,
      localRule?.formData?.configs?.having,
      inheritBaseCondition ? base.configs?.having : undefined,
    );
    return {
      ...base,
      configs: {
        ...(base.configs ?? {}),
        where: excludeHavingFromWhere(where, having),
        having,
      },
    };
  };

  const getMergedSourceData = () => {
    const edit = props.editData ?? {};
    const form = props.formData ?? {};
    return {
      ...edit,
      ...form,
      configs: {
        ...(edit.configs ?? {}),
        ...(form.configs ?? {}),
      },
    };
  };

  const syncStepFormMeta = (data: Record<string, any>) => {
    stepFormData.value.strategy_type = data.strategy_type || 'rule';
    stepFormData.value.strategy_name = data.strategy_name ?? '';
    stepFormData.value.status = data.status ?? '';
    stepFormData.value.risk_level = data.risk_level || 'MIDDLE';
  };

  const applyRuleItems = (data: Record<string, any>) => {
    ruleIdSeq = 1;
    if (data.rules?.length) {
      ruleItems.value = data.rules.map((r: any, i: number) => {
        const where = r.conditions?.where ?? r.configs?.where;
        const having = r.conditions?.having ?? r.configs?.having;
        const configs = {
          ...(r.configs || {}),
          ...(where ? { where: _.cloneDeep(where) } : {}),
          ...(having ? { having: _.cloneDeep(having) } : {}),
        };
        return createRule({
          rule_id: r.rule_id,
          name: r.rule_name || r.name || `规则${i + 1}`,
          risk_title: r.risk_title || '',
          risk_level: r.risk_level || 'HIGH',
          risk_hazard: r.risk_hazard || '',
          risk_guidance: r.risk_guidance || '',
          processor: toNoticeGroupIds(r.processor ?? r.processors),
          follower: toNoticeGroupIds(r.follower ?? r.notice_users),
          conditions: {
            where: configs.where,
            having: configs.having,
          },
          formData: { configs },
        });
      });
    } else {
      ruleItems.value = [createRule({
        name: '规则1',
        risk_title: data.risk_title || '',
        risk_level: data.risk_level || 'HIGH',
        risk_hazard: data.risk_hazard || '',
        risk_guidance: data.risk_guidance || '',
      })];
    }
    ruleIdSeq = Math.max(...ruleItems.value.map(item => item.id), 0) + 1;
  };

  const syncEditRuleItems = () => {
    if (!isEditMode && !isCloneMode) return;

    const data = getMergedSourceData();
    const strategyId = data.strategy_id;
    if (!strategyId) return;

    const rules = data.rules ?? [];
    const incomingHasConditions = rules.some((r: any) => (
      hasConditionGroups(r?.conditions?.where)
      || hasConditionGroups(r?.configs?.where)
    ));
    // 只看当前 UI 使用的 formData，避免 conditions 有值但 formData 已被空 where 覆盖时误判
    const localHasConditions = ruleItems.value.some(r => (
      hasConditionGroups(r?.formData?.configs?.where)
    ));

    // 已同步过且本地 UI 已有条件，或接口本身无条件时，不再覆盖
    if (syncedEditStrategyId.value === strategyId
      && (localHasConditions || !incomingHasConditions)) {
      return;
    }

    syncStepFormMeta(data);
    applyRuleItems(data);
    syncedEditStrategyId.value = strategyId;
  };

  const syncDraftRuleItems = () => {
    if (isEditMode || isCloneMode || draftRulesSynced.value) return;

    const data = props.formData;
    if (!data?.rules?.length) return;

    syncStepFormMeta(data);
    applyRuleItems(data);
    draftRulesSynced.value = true;
  };

  watch(
    () => [
      props.editData?.strategy_id,
      props.formData?.strategy_id,
      props.formData?.risk_title,
      props.formData?.risk_hazard,
      props.formData?.risk_guidance,
      props.formData?.rules?.length,
      props.formData?.rules?.map((r: any) => (
        r?.conditions?.where?.conditions?.length
        || r?.configs?.where?.conditions?.length
        || 0
      )).join(','),
      props.formData?.configs?.where?.conditions?.length,
    ],
    () => {
      syncEditRuleItems();
    },
    { immediate: true },
  );

  watch(
    () => props.formData?.rules,
    () => {
      syncDraftRuleItems();
    },
    { immediate: true, deep: true },
  );

  watch(
    () => props.formData?.hit_conditions_reset_seq,
    (seq) => {
      if (!seq) return;
      ruleItems.value = ruleItems.value.map(rule => ({
        ...rule,
        conditions: {
          where: { connector: 'and', conditions: [] },
          having: { connector: 'and', conditions: [] },
        },
        formData: {
          ...rule.formData,
          configs: {
            ...(rule.formData?.configs || {}),
            where: { connector: 'and', conditions: [] },
            having: { connector: 'and', conditions: [] },
          },
        },
      }));
      nextTick(() => {
        comRefs.value.forEach(com => com?.resetFormData?.());
      });
    },
  );

  const handlePrevious = () => {
    emits('previousStep', 1, buildStepParams());
  };

  const OPERATORS_WITHOUT_VALUE = new Set(['', 'notnull', 'isnull']);

  const getConditionNode = (item: Record<string, any>) => item?.condition ?? item;

  const hasConditionField = (condition: Record<string, any>) => {
    const field = condition?.field;
    if (!field) return false;
    if (typeof field === 'string') return field.trim() !== '';
    return Boolean(field.raw_name || field.display_name);
  };

  const hasConditionValue = (condition: Record<string, any>) => {
    const filters = condition?.filters;
    if (Array.isArray(filters) && filters.some(item => String(item ?? '').trim() !== '')) {
      return true;
    }
    const filter = condition?.filter ?? condition?.value;
    if (Array.isArray(filter)) {
      return filter.some(item => String(item ?? '').trim() !== '');
    }
    return String(filter ?? '').trim() !== '';
  };

  const findInvalidHitCondition = (where?: { conditions?: any[] } | null) => {
    const groups = where?.conditions || [];
    for (let groupIndex = 0; groupIndex < groups.length; groupIndex++) {
      const items = Array.isArray(groups[groupIndex]?.conditions) ? groups[groupIndex].conditions : [];
      for (let itemIndex = 0; itemIndex < items.length; itemIndex++) {
        const condition = getConditionNode(items[itemIndex]);
        if (hasConditionField(condition)) {
          if (!condition.operator) {
            return 'operator';
          }
          if (!OPERATORS_WITHOUT_VALUE.has(condition.operator) && !hasConditionValue(condition)) {
            return 'value';
          }
        }
      }
    }
    return null;
  };

  const handleNext = async () => {
    if (ruleItems.value.length === 0) {
      return;
    }
    if (showRuleNoticeGroups) {
      for (const rule of ruleItems.value) {
        if (!rule.processor?.length) {
          messageError(t('{label}：风险单处理人不能为空', { label: rule.name }));
          return;
        }
      }
    }
    // 验证所有规则的命中条件
    try {
      await Promise.all(ruleItems.value.map((_, index) => (
        comRefs.value[index]?.getValue?.() ?? Promise.resolve()
      )));
      for (let index = 0; index < ruleItems.value.length; index++) {
        const rule = ruleItems.value[index];
        const fields = comRefs.value[index]?.getFields?.({ forValidate: true });
        const where = fields?.configs?.where ?? rule.formData?.configs?.where ?? rule.conditions?.where;
        const having = fields?.configs?.having ?? rule.formData?.configs?.having ?? rule.conditions?.having;
        const invalidType = findInvalidHitCondition(where) || findInvalidHitCondition(having);
        if (invalidType) {
          rule.collapsed = false;
          const message = invalidType === 'operator'
            ? t('命中条件运算符不能为空')
            : t('命中条件值不能为空');
          messageError(message);
          formRefs.value[index]?.validate?.().catch(() => {});
          return;
        }
      }
      const params = buildStepParams();
      const missingWhere = params.rules.find((rule: Record<string, any>) => (
        !hasConditionGroups(rule?.conditions?.where)
        && !hasConditionGroups(rule?.conditions?.having)
      ));
      if (missingWhere) {
        messageError(t('{label}缺少where过滤条件（规则where必填）', { label: missingWhere.name || missingWhere.rule_name }));
        return;
      }
      emits('nextStep', 3, params);
    } catch {
      // 验证失败，停留在当前步骤
    }
  };

  const handleCancel = () => {
    router.push({ name: strategyRoutes.list });
  };

  const handleSaveDraft = () => {
    emits('saveDraft', buildStepParams());
  };

  const handleDocumentClick = (event: MouseEvent) => {
    const target = event.target as HTMLElement | null;
    if (target?.closest('.bksec-var-panel, .reference-variable-btn, .bksec-var-popover')) {
      return;
    }
    ruleItems.value.forEach((_, i) => {
      if (!ruleItems.value[i].variableInputActive) return;
      commitRiskTitleEdit(i);
    });
  };

  onActivated(() => {
    syncEditRuleItems();
    syncDraftRuleItems();
    window.addEventListener('click', handleDocumentClick);
  });

  onDeactivated(() => {
    commitAllRiskTitleEdits();
    window.removeEventListener('click', handleDocumentClick);
  });

  onUnmounted(() => {
    window.removeEventListener('click', handleDocumentClick);
  });
</script>
<style lang="postcss" scoped>
.create-strategy-page {
  .create-strategy-main {
    padding-top: 4px;
    margin-bottom: 24px;
  }

  /* 外层白色大卡片 */
  .risk-rules-card {
    margin-bottom: var(--audit-space-16);
    background: var(--audit-neutral-bg-04);
    border-radius: var(--audit-radius-container);
    box-shadow: var(--audit-shadow-card);

    .risk-rules-card-header {
      padding: 12px var(--audit-space-24) var(--audit-space-16);
      border-bottom: 1px solid var(--audit-neutral-border-02);
    }

    .risk-rules-card-title-row {
      display: flex;
      align-items: center;
      margin-bottom: 0;
      gap: 6px;

      .risk-rules-title {
        font-size: var(--audit-font-size-base);
        font-weight: var(--audit-font-weight-bold);
        line-height: var(--audit-line-height-base);
        color: var(--audit-neutral-text-01);
      }

      .risk-rules-tip-icon {
        font-size: 14px;
        color: #979ba5;
        cursor: pointer;
      }

      .risk-rules-tip-text {
        font-size: 12px;
        color: #979ba5;
      }
    }

    .risk-rules-actions {
      display: flex;
      align-items: center;
      padding: var(--audit-space-16) var(--audit-space-24) 0;
      margin-bottom: var(--audit-space-16);

      .add-rule-icon {
        margin-right: 4px;
        color: #3a84ff;
      }

      .collapse-toggle-icon {
        width: 12px;
        height: 12px;
        margin-right: 4px;
        vertical-align: middle;
      }

      :deep(.bk-button:first-child) {
        color: #3a84ff;
        border-color: #3a84ff;
      }
    }

    .rule-list {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 0;
      padding: 0 24px 24px;
    }
  }

  .rule-item-ghost {
    opacity: 0.5;
    background: #f0f5ff;
  }

  .rule-item-card {
    align-self: flex-start;
    box-sizing: border-box;
    width: 1264px;
    max-width: 100%;
    margin-bottom: var(--audit-space-16);
    overflow: hidden;
    background: var(--audit-neutral-bg-04);
    border: 1px solid var(--audit-neutral-border-02);
    border-radius: var(--audit-radius-control);

    &:last-child {
      margin-bottom: 0;
    }

    .rule-item-header {
      display: flex;
      align-items: center;
      height: 40px;
      padding: 0 var(--audit-space-16) 0 var(--audit-space-8);
      cursor: pointer;
      background: var(--audit-neutral-bg-01);
      border-radius: var(--audit-radius-control) var(--audit-radius-control) 0 0;
      gap: var(--audit-space-8);

      .rule-drag-handle {
        font-size: 14px;
        color: #c4c6cc;
        cursor: grab;
        flex-shrink: 0;

        &:active {
          cursor: grabbing;
        }
      }

      .rule-collapse-icon {
        font-size: 12px;
        color: var(--audit-neutral-text-02);
        cursor: pointer;
        transition: transform 0.2s ease;
        flex-shrink: 0;

        &.is-collapsed {
          transform: rotate(-90deg);
        }
      }

      .rule-name-wrap {
        display: flex;
        flex: 1;
        gap: 8px;
        align-items: center;
        min-width: 0;
      }

      .rule-name {
        min-width: 0;
        overflow: hidden;
        font-size: var(--audit-font-size-sm);
        font-weight: var(--audit-font-weight-bold);
        line-height: var(--audit-line-height-sm);
        color: var(--audit-neutral-text-02);
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .rule-name-input {
        flex: 1;
        min-width: 0;
        height: 28px;
        padding: 0 8px;
        font-size: 14px;
        color: #313238;
        background: #fff;
        border: 1px solid #3a84ff;
        border-radius: 2px;
        outline: none;
      }

      .rule-name-edit-icon {
        font-size: 14px;
        color: #979ba5;
        cursor: pointer;
        flex-shrink: 0;

        &:hover {
          color: #3a84ff;
        }
      }

      .rule-header-actions {
        display: flex;
        align-items: center;
        gap: var(--audit-space-16);
        margin-left: auto;
        flex-shrink: 0;

        .rule-action-icon {
          font-size: 16px;
          color: var(--audit-neutral-text-02);
          cursor: pointer;

          &:hover {
            color: var(--audit-brand-02);
          }

          &.rule-action-delete:hover {
            color: var(--audit-danger-02);
          }
        }
      }
    }

    .rule-item-content {
      display: flex;
      flex-direction: column;
      gap: var(--audit-space-24);
      padding: var(--audit-space-16);
      background: var(--audit-neutral-bg-02);
      overflow: visible;

      .rule-section {
        width: 100%;
        margin-bottom: 0;

        &.is-field-narrow {
          width: 608px;
          max-width: 100%;
        }

        .rule-section-label {
          margin-bottom: 6px;
          font-size: var(--audit-font-size-sm);
          line-height: var(--audit-line-height-sm);
          color: var(--audit-neutral-text-02);

          &.is-required::before {
            display: inline-block;
            width: 8px;
            color: var(--audit-danger-02);
            text-align: center;
            content: '*';
          }

          .rule-section-label-tip {
            border-bottom: 1px dashed var(--audit-neutral-text-03);

            &:not(.is-plain) {
              cursor: pointer;
            }
          }
        }

        .rule-section-body {
          position: relative;
          overflow: visible;

          &.rule-section-body--condition {
            overflow: visible;
            padding: 0;
          }

          .rule-condition-form {
            overflow: visible;
          }
        }
      }

      .rule-section-two-col {
        display: flex;
        gap: var(--audit-space-16);
        align-items: flex-start;
        width: 1232px;
        max-width: 100%;

        .rule-section-col {
          flex: 1 1 608px;
          width: 608px;
          max-width: 608px;
          min-width: 0;
        }

        :deep(.rule-text-count.bk-textarea) {
          width: 100%;
          height: 60px;
          min-height: 60px;
          max-height: 60px;
          overflow: auto;
          resize: none;
        }

        :deep(.rule-text-count .bk-input-word-limit),
        :deep(.rule-text-count .input-maxlength) {
          font-size: var(--audit-font-size-mini);
          line-height: var(--audit-line-height-mini);
        }
      }

      .risk-level-group {
        display: flex;
        gap: var(--audit-space-8);

        .risk-level-btn {
          box-sizing: border-box;
          width: 48px;
          height: 26px;
          padding: 0;
          font-size: var(--audit-font-size-sm);
          line-height: 24px;
          color: var(--audit-neutral-text-02);
          cursor: pointer;
          background: var(--audit-neutral-bg-04);
          border: 1px solid var(--audit-neutral-text-04);
          border-radius: var(--audit-radius-control);
          outline: none;

          &.level-high.is-active {
            color: var(--audit-neutral-bg-04);
            background: var(--audit-danger-02);
            border-color: var(--audit-danger-02);
          }

          &.level-middle.is-active {
            color: var(--audit-neutral-bg-04);
            background: var(--audit-warn-02);
            border-color: var(--audit-warn-02);
          }

          &.level-low.is-active {
            color: var(--audit-neutral-bg-04);
            background: var(--audit-neutral-text-03);
            border-color: var(--audit-neutral-text-03);
          }
        }
      }

      :deep(.add-rule-item) {
        display: flex;
        width: 100%;
        height: 32px;
        padding: 0 var(--audit-space-12);
        font-size: var(--audit-font-size-sm);
        line-height: var(--audit-line-height-sm);
        color: var(--audit-brand-02);
        cursor: pointer;
        background: var(--audit-neutral-bg-03);
        border: 1px dashed var(--audit-neutral-text-04);
        border-radius: 0;
        box-sizing: border-box;
        align-items: center;
        gap: var(--audit-space-4);
      }

      :deep(.add-rule-icon) {
        margin: 0;
        font-size: 16px;
      }

      /* 风险单标题输入 */
      .variable-input-content {
        position: relative;
        display: flex;
        align-items: center;
        width: 100%;
        min-width: 0;
        min-height: 32px;
        padding: 0 8px;
        font-size: 12px;
        color: var(--audit-neutral-text-02);
        cursor: pointer;
        background: #fff;
        border: 1px solid #c4c6cc;
        border-right: none;
        border-radius: 2px 0 0 2px;
        flex: 1;
        box-sizing: border-box;

        &.active {
          cursor: text;
          border-color: #3a84ff;
          border-right: none;

          .variable-input-list {
            width: 100%;
            flex: 1;
          }

          .list-item-input {
            width: 100%;
            min-width: 0;
            flex: 1;
          }
        }

        .variable-input-list {
          display: flex;
          width: 100%;
          max-width: 100%;
          flex-wrap: wrap;
          align-items: center;
          list-style: none;
          padding: 0;
          margin: 0;

          li {
            display: flex;
            align-items: center;
          }

          .is-variable {
            padding: 2px 4px;
            margin: 0 1px;
            background-color: #f2f3f6;
            border-radius: 2px;
          }

          .list-item-input {
            flex: 1;

            .title-input {
              width: 100%;
              min-width: 0;
              padding: 0;
              border: none;
              outline: none;
              font-size: 12px;
              line-height: 30px;
              color: var(--audit-neutral-text-02);
              background: transparent;
            }
          }
        }

        .variable-input-placeholder {
          position: absolute;
          top: 50%;
          left: 8px;
          color: #c4c6cc;
          white-space: nowrap;
          pointer-events: none;
          transform: translateY(-50%);
        }
      }

      /* 引用变量按钮与输入框并排 */
      .rule-section-body:has(.variable-input-content) {
        display: flex;
        align-items: stretch;
        position: relative;

        :deep(.bk-popover) {
          flex-shrink: 0;
        }

        .reference-variable-btn {
          display: inline-flex;
          height: 32px;
          padding: 0 6px;
          font-size: var(--audit-font-size-sm);
          line-height: var(--audit-line-height-sm);
          color: var(--audit-brand-02);
          cursor: pointer;
          background: var(--audit-neutral-bg-04);
          border: 1px solid var(--audit-neutral-text-04);
          border-radius: 0 var(--audit-radius-control) var(--audit-radius-control) 0;
          align-items: center;
          gap: var(--audit-space-4);
          flex-shrink: 0;

          &.is-open {
            border-top-color: var(--audit-brand-02);
            border-right-color: var(--audit-brand-02);
            border-bottom-color: var(--audit-brand-02);
          }
        }

        .reference-variable-icon {
          font-size: var(--audit-font-size-lg);
          color: var(--audit-brand-02);
        }
      }
    }

    &.is-collapsed .rule-item-header {
      border-radius: var(--audit-radius-control);
    }
  }

  .rule-list-empty {
    padding: 40px;
    font-size: 14px;
    color: #979ba5;
    text-align: center;
    background: #fff;
    border-radius: 2px;
    box-shadow: 0 1px 2px 0 #00000029;
  }
}
</style>
<style lang="postcss">
.bksec-var-popover.bk-pop2-content,
.bksec-var-popover .bk-pop2-content {
  padding: var(--audit-space-4) 0;
}
</style>
