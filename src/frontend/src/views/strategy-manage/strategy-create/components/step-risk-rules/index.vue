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
              type="info-fill" />
            <span class="risk-rules-tip-text">
              {{ t('当一条数据源数据同时命中多条规则时，将采用自上而下的优先级匹配，仅最先匹配到的规则生效。') }}
            </span>
          </div>
          <!-- 操作栏 -->
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
                  type="angle-line-down" />

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
                    v-bk-tooltips="t('克隆')"
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
                class="rule-item-content"
                style="background: #fafbfd;">
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
                <div class="rule-section">
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
                            @click.stop
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
                      :component-event-delay="300"
                      :is-show="rule.showVariablePanel"
                      :offset="8"
                      placement="bottom-end"
                      theme="light"
                      trigger="manual"
                      width="520">
                      <bk-button
                        class="reference-variable-btn"
                        size="small"
                        @click.stop="(e) => handleReferenceVariableClick(e, index)">
                        <audit-icon
                          style="margin-right: 4px;"
                          type="insert" />
                        {{ t('引用变量') }}
                      </bk-button>
                      <template #content>
                        <variable-table
                          :select="selectFields"
                          :strategy-id="editData.strategy_id"
                          @is-copy="() => handleVariableCopy(index)" />
                      </template>
                    </bk-popover>
                  </div>
                </div>

                <!-- 风险等级 -->
                <div class="rule-section">
                  <div class="rule-section-label is-required">
                    {{ t('风险等级') }}
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

                <!-- 风险危害 + 处理指引（两列） -->
                <div class="rule-section rule-section-two-col">
                  <div class="rule-section-col">
                    <div class="rule-section-label">
                      {{ t('风险危害') }}
                    </div>
                    <div class="rule-section-body">
                      <bk-input
                        v-model="rule.risk_hazard"
                        class="rule-resize-textarea"
                        :maxlength="100"
                        :placeholder="t('请输入')"
                        resize
                        :rows="3"
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
                        class="rule-resize-textarea"
                        :maxlength="100"
                        :placeholder="t('请输入')"
                        resize
                        :rows="3"
                        show-word-limit
                        type="textarea" />
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
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';
  import Vuedraggable from 'vuedraggable';
  import _ from 'lodash';

  import IamManageService from '@service/iam-manage';
  import NoticeManageService from '@service/notice-group';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';
  import StrategyModel from '@model/strategy/strategy';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';
  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  import collapseIcon from '@images/collapse.svg';
  import expandIcon from '@images/expand.svg';

  import Customize from '../step1/components/customize/index.vue';
  import ReferenceModel from '../step1/components/reference-model/index.vue';
  import VariableTable from '../step2/components/variable-table.vue';
  import NoticeGroupSelect from '../step3/components/notice-group-select.vue';

  import {
    getStrategyRouteNames,
    isPlatformStrategyRoute,
    isStrategyCloneRoute,
    isStrategyEditRoute,
  } from '../../../utils/strategy-routes';
  import { excludeHavingFromWhere } from '../../utils/strategy-protocol';
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

  const formRef = ref();
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

  const setComRef = (el: any, index: number) => {
    comRefs.value[index] = el;
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
    const fields = com?.getFields?.({ forValidate: true })
      ?? { configs: source.formData?.configs ?? {} };
    const configs = _.cloneDeep(fields.configs ?? source.formData?.configs ?? {});
    if (!configs.where && source.conditions?.where) {
      configs.where = _.cloneDeep(source.conditions.where);
    }
    if (!configs.having && source.conditions?.having) {
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
    titleInputRefs.value.splice(index + 1, 0, null);
  };

  const handleDeleteRule = (index: number) => {
    if (ruleItems.value.length <= 1) {
      return Promise.resolve();
    }
    ruleItems.value.splice(index, 1);
    comRefs.value.splice(index, 1);
    titleInputRefs.value.splice(index, 1);
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
    titleInputRefs.value = reorderRefArray(titleInputRefs.value, oldIndex, newIndex);
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

  const closeOtherRiskTitleEditors = (index: number) => {
    ruleItems.value.forEach((_, i) => {
      if (i === index) return;
      const current = ruleItems.value[i];
      if (current.variableInputActive || current.showVariablePanel) {
        if (!current.isVariableCopy) {
          commitRiskTitleEdit(i);
        }
      }
      ruleItems.value[i].isVariableCopy = false;
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
      rule.clickLiIndex = -1;
    });
  };

  /** 仅点击「引用变量」时打开/关闭弹窗 */
  const handleReferenceVariableClick = (e: Event, index: number) => {
    e.stopPropagation();
    const rule = ruleItems.value[index];
    closeOtherRiskTitleEditors(index);
    if (!rule.variableInputActive) {
      activateRiskTitleEdit(index);
    }
    rule.showVariablePanel = !rule.showVariablePanel;
  };

  const handleClickTitleLi = (ruleIndex: number, liIndex: number) => {
    ruleItems.value[ruleIndex].clickLiIndex = liIndex;
  };

  const getClipboardContent = async (index: number) => {
    const rule = ruleItems.value[index];
    try {
      const text = await navigator.clipboard.readText();
      if (rule.riskTitleInputValue) {
        rule.risk_title += rule.riskTitleInputValue;
        rule.riskTitleInputValue = '';
      } else {
        rule.risk_title += text;
      }
    } catch (err) {
      console.error('Failed to read clipboard contents: ', err);
    }
  };

  const handleTitleKeyDown = (e: KeyboardEvent, index: number) => {
    const rule = ruleItems.value[index];
    if (e.code === 'Enter') {
      e.preventDefault();
      rule.showVariablePanel = false;
      rule.isVariableCopy = false;
      rule.variableInputActive = false;
      titleInputRefs.value[index]?.blur();
      getClipboardContent(index);
      return;
    }
    if (rule.showVariablePanel && rule.riskTitleInputValue) return;
    if (e.code === 'Backspace' && getDisplayRiskTitle(rule.risk_title).length) {
      const display = getDisplayRiskTitle(rule.risk_title);
      display.pop();
      rule.risk_title = display.map(item => item.value).join('');
    }
  };

  const handleVariableCopy = (index: number) => {
    ruleItems.value[index].isVariableCopy = true;
  };

  const updateRuleFormData = (data: Record<string, any>, index: number) => {
    const prev = ruleItems.value[index];
    const nextConfigs = {
      ...(prev.formData?.configs || {}),
      ...(data.configs || {}),
    };
    // 子组件初始化会回传空 where，不能覆盖已同步的命中条件
    const prevWhere = prev.conditions?.where;
    const prevHaving = prev.conditions?.having;
    if (!hasConditionGroups(nextConfigs.where) && hasConditionGroups(prevWhere)) {
      nextConfigs.where = _.cloneDeep(prevWhere);
    }
    if (!hasConditionGroups(nextConfigs.having) && hasConditionGroups(prevHaving)) {
      nextConfigs.having = _.cloneDeep(prevHaving);
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
    return merged;
  };

  const buildStepParams = () => {
    const baseFormData = { ...props.formData };
    const rules = ruleItems.value.map((rule, index) => {
      const com = comRefs.value[index];
      const fields = com?.getFields?.({ forValidate: false }) ?? { configs: rule.formData?.configs ?? {} };
      const mergedConfigs = mergeRuleConfigs(fields.configs);
      return {
        ...(rule.rule_id ? { rule_id: rule.rule_id } : {}),
        name: rule.name,
        rule_name: rule.name,
        risk_title: rule.risk_title,
        risk_level: rule.risk_level,
        risk_hazard: rule.risk_hazard,
        risk_guidance: rule.risk_guidance,
        processor: rule.processor ?? [],
        follower: rule.follower ?? [],
        conditions: {
          where: mergedConfigs.where ?? null,
          having: mergedConfigs.having ?? null,
        },
        configs: mergedConfigs,
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
    return {
      ...baseFormData,
      risk_title: firstRule.risk_title ?? baseFormData.risk_title ?? '',
      risk_level: firstRule.risk_level ?? baseFormData.risk_level ?? 'HIGH',
      risk_hazard: firstRule.risk_hazard ?? baseFormData.risk_hazard ?? '',
      risk_guidance: firstRule.risk_guidance ?? baseFormData.risk_guidance ?? '',
      configs: topConfigs,
      rules,
    };
  };

  const hasConditionGroups = (where?: { conditions?: unknown[] } | null) => (
    Boolean(where?.conditions?.length)
  );

  const pickConditionWhere = (...candidates: Array<{ conditions?: unknown[] } | null | undefined>) => (
    candidates.find(item => hasConditionGroups(item))
  );

  const getRuleEditData = (index: number) => {
    const base = getMergedSourceData();
    const localRule = ruleItems.value[index];
    const formRule = props.formData?.rules?.[index] ?? {};
    // 注意：customize 初始化会回写空 where（conditions: []），不能优先生效，否则会盖住真实命中条件
    const where = pickConditionWhere(
      localRule?.conditions?.where,
      formRule.conditions?.where,
      formRule.configs?.where,
      localRule?.formData?.configs?.where,
      index === 0 ? base.configs?.where : undefined,
    );
    const having = pickConditionWhere(
      localRule?.conditions?.having,
      formRule.conditions?.having,
      formRule.configs?.having,
      localRule?.formData?.configs?.having,
      index === 0 ? base.configs?.having : undefined,
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
          processor: r.processor ?? [],
          follower: r.follower ?? [],
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
      await Promise.all(ruleItems.value.map((_, index) => {
        const com = comRefs.value[index];
        return com?.getValue?.() ?? Promise.resolve();
      }));
      emits('nextStep', 3, buildStepParams());
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

  const handleDocumentClick = () => {
    ruleItems.value.forEach((_, i) => {
      const current = ruleItems.value[i];
      if (!current.showVariablePanel && !current.variableInputActive) return;
      if (current.isVariableCopy) {
        ruleItems.value[i].isVariableCopy = false;
        return;
      }
      commitRiskTitleEdit(i);
    });
  };

  onActivated(() => {
    syncEditRuleItems();
    syncDraftRuleItems();
    window.addEventListener('click', handleDocumentClick);
  });

  onDeactivated(() => {
    ruleItems.value.forEach((_, i) => {
      ruleItems.value[i].showVariablePanel = false;
      ruleItems.value[i].isVariableCopy = false;
      ruleItems.value[i].variableInputActive = false;
    });
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
    background: #fff;
    border-radius: 2px;
    box-shadow: 0 1px 2px 0 #00000029;
    margin-bottom: 16px;

    .risk-rules-card-header {
      padding: 16px 24px 0;
    }

    .risk-rules-card-title-row {
      display: flex;
      align-items: center;
      margin-bottom: 16px;
      gap: 6px;

      .risk-rules-title {
        font-size: 14px;
        font-weight: 600;
        color: #313238;
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
      margin-bottom: 16px;

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
      gap: 0;
      padding: 0 24px 24px;
    }
  }

  .rule-item-ghost {
    opacity: 0.5;
    background: #f0f5ff;
  }

  .rule-item-card {
    margin-bottom: 8px;
    background: #fff !important;
    border-radius: 2px;
    border: 1px solid #dcdee5;

    &:last-child {
      margin-bottom: 0;
    }

    .rule-item-header {
      display: flex;
      align-items: center;
      height: 48px;
      padding: 0 16px;
      cursor: pointer;
      background: #f5f6fa;
      border-radius: 2px 2px 0 0;
      border-bottom: 1px solid #dcdee5;
      gap: 8px;

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
        font-size: 14px;
        color: #63656e;
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
        font-size: 14px;
        font-weight: 600;
        color: #313238;
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
        gap: 12px;
        margin-left: auto;
        flex-shrink: 0;

        .rule-action-icon {
          font-size: 16px;
          color: #63656e;
          cursor: pointer;

          &:hover {
            color: #3a84ff;
          }

          &.rule-action-delete:hover {
            color: #ea3636;
          }
        }
      }
    }

    .rule-item-content {
      padding: 20px 24px 24px;
      background: #fafbfd !important;
      overflow: visible;

      .rule-section {
        margin-bottom: 20px;

        &:last-child {
          margin-bottom: 0;
        }

        .rule-section-label {
          margin-bottom: 8px;
          font-size: 12px;
          color: #63656e;

          &.is-required::before {
            display: inline-block;
            width: 8px;
            color: #ea3636;
            text-align: center;
            content: '*';
          }

          .rule-section-label-tip {
            cursor: pointer;
            border-bottom: 1px dashed #979ba5;
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
        gap: 12px;
        align-items: flex-start;

        .rule-section-col {
          flex: 1;
          min-width: 0;
        }

        /* 文档：resize=true 时可拖拽调高；覆盖可能被吃掉的样式 */
        :deep(.rule-resize-textarea.bk-textarea) {
          width: 100%;
          min-height: 72px;
          max-height: 360px;
          overflow: auto !important;
          resize: vertical !important;
        }
      }

      /* 风险等级 */
      .risk-level-group {
        display: flex;
        gap: 0;

        .risk-level-btn {
          height: 32px;
          padding: 0 16px;
          font-size: 12px;
          color: #63656e;
          cursor: pointer;
          background: #fff;
          border: 1px solid #c4c6cc;
          outline: none;

          &:not(:first-child) {
            margin-left: -1px;
          }

          &:first-child {
            border-radius: 2px 0 0 2px;
          }

          &:last-child {
            border-radius: 0 2px 2px 0;
          }

          &.is-active {
            z-index: 1;
          }

          &.level-high.is-active {
            color: #fff;
            background: #ea3636;
            border-color: #ea3636;
          }

          &.level-middle.is-active {
            color: #fff;
            background: #ff9c01;
            border-color: #ff9c01;
          }

          &.level-low.is-active {
            color: #fff;
            background: #979ba5;
            border-color: #979ba5;
          }
        }
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
        color: #63656e;
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
              color: #313238;
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
          height: auto;
          min-height: 32px;
          border-radius: 0 2px 2px 0;
          flex-shrink: 0;
        }
      }
    }

    &.is-collapsed .rule-item-header {
      border-bottom: none;
      border-radius: 2px;
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
