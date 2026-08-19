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
              type="attention" />
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
                class="collapse-toggle-icon"
                :src="allCollapsed ? expandIcon : collapseIcon"
                alt="">
              {{ allCollapsed ? t('一键展开') : t('一键收起') }}
            </bk-button>
          </div>
        </div>

        <!-- 规则列表 -->
        <div
          ref="ruleListRef"
          class="rule-list">
        <div
          v-for="(rule, index) in ruleItems"
          :key="rule.id"
          class="rule-item-card"
          :class="{ 'is-collapsed': rule.collapsed }">
          <!-- 规则卡片头部 -->
          <div class="rule-item-header">
            <span
              class="rule-drag-handle"
              title="拖拽排序">
              <audit-icon type="move" />
            </span>
            <audit-icon
              class="rule-collapse-icon"
              :class="{ 'is-collapsed': rule.collapsed }"
              type="angle-line-down"
              @click="() => toggleCollapse(index)" />

            <!-- 规则名称（可编辑） -->
            <template v-if="rule.editingName">
              <input
                ref="nameInputRefs"
                v-model="rule.name"
                class="rule-name-input"
                type="text"
                @blur="() => stopEditName(index)"
                @keydown.enter="() => stopEditName(index)" />
            </template>
            <template v-else>
              <span class="rule-name">{{ rule.name }}</span>
              <audit-icon
                class="rule-name-edit-icon"
                type="edit-fill"
                @click="() => startEditName(index)" />
            </template>

            <!-- 头部右侧操作 -->
            <div class="rule-header-actions">
              <audit-icon
                v-bk-tooltips="t('克隆')"
                class="rule-action-icon"
                type="copy"
                @click="() => handleCloneRule(index)" />
              <audit-icon
                v-bk-tooltips="t('删除')"
                class="rule-action-icon rule-action-delete"
                type="delete"
                @click="() => handleDeleteRule(index)" />
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
                {{ t('命中条件') }}
              </div>
              <div class="rule-section-body">
                <audit-form
                  class="rule-condition-form"
                  form-type="vertical"
                  :model="rule.formData">
                  <component
                    :is="strategyWayComMap[stepFormData.strategy_type]"
                    :ref="(el: any) => setComRef(el, index)"
                    :edit-data="editData"
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
                  @click.stop="(e) => handleVariableInputClick(e, index)">
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
                        v-model.trim="rule.riskTitleInputValue"
                        class="title-input"
                        type="text"
                        @keydown="(e) => handleTitleKeyDown(e, index)" />
                    </li>
                  </ul>
                  <p
                    v-if="!rule.variableInputActive && !rule.risk_title"
                    class="variable-input-placeholder">
                    {{ t('请输入') }}
                  </p>
                </div>
                <bk-button
                  class="reference-variable-btn"
                  size="small"
                  @click="(e: MouseEvent) => toggleVariablePanel(e, index)">
                  <audit-icon
                    style="margin-right: 4px;"
                    type="insert" />
                  {{ t('引用变量') }}
                </bk-button>
                <!-- 变量选择面板 -->
                <div
                  v-if="rule.showVariablePanel"
                  class="variable-panel"
                  @click.stop>
                  <div class="variable-panel-title">{{ t('变量列表') }}</div>
                  <div
                    v-for="field in (parentFormData.configs?.select || [])"
                    :key="field.field_name"
                    class="variable-item"
                    @click="() => insertVariable(index, field.field_name)">
                    <span class="variable-item-name">{{ getVariableTpl(field.field_name) }}</span>
                    <span class="variable-item-label">{{ field.description || field.field_name }}</span>
                  </div>
                  <div
                    v-if="!(parentFormData.configs?.select?.length)"
                    class="variable-panel-empty">
                    {{ t('暂无可用变量，请先配置数据源和预期结果') }}
                  </div>
                </div>
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
                <div class="rule-section-label">{{ t('风险危害') }}</div>
                <div class="rule-section-body">
                  <bk-input
                    v-model="rule.risk_hazard"
                    :maxlength="100"
                    :placeholder="t('请输入')"
                    :rows="3"
                    show-word-limit
                    type="textarea" />
                </div>
              </div>
              <div class="rule-section-col">
                <div class="rule-section-label">{{ t('处理指引') }}</div>
                <div class="rule-section-body">
                  <bk-input
                    v-model="rule.risk_guidance"
                    :maxlength="100"
                    :placeholder="t('请输入')"
                    :rows="3"
                    show-word-limit
                    type="textarea" />
                </div>
              </div>
            </div>
          </div>
        </div>

          <!-- 空状态 -->
          <div
            v-if="ruleItems.length === 0"
            class="rule-list-empty">
            <p>{{ t('暂无规则，点击「添加规则」新增') }}</p>
          </div>
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
    nextTick,
    onBeforeUnmount,
    onMounted,
    provide,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import StrategyModel from '@model/strategy/strategy';

  import collapseIcon from '@images/collapse.svg';
  import expandIcon from '@images/expand.svg';

  import Customize from '../step1/components/customize/index.vue';
  import ReferenceModel from '../step1/components/reference-model/index.vue';

  interface RuleItem {
    id: number;
    name: string;
    collapsed: boolean;
    editingName: boolean;
    variableInputActive: boolean;
    showVariablePanel: boolean;
    riskTitleInputValue: string;
    risk_title: string;
    risk_level: string;
    risk_hazard: string;
    risk_guidance: string;
    formData: Record<string, any>;
  }

  interface Props {
    editData: StrategyModel,
    formData: Record<string, any>,
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
  const { t } = useI18n();

  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';

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

  let ruleIdSeq = 1;

  const createRule = (overrides: Partial<RuleItem> = {}): RuleItem => ({
    id: ruleIdSeq++,
    name: `规则${ruleIdSeq - 1}`,
    collapsed: false,
    editingName: false,
    variableInputActive: false,
    showVariablePanel: false,
    riskTitleInputValue: '',
    risk_title: '',
    risk_level: 'HIGH',
    risk_hazard: '',
    risk_guidance: '',
    formData: {},
    ...overrides,
  });

  const ruleItems = ref<RuleItem[]>([createRule()]);

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
    const arr = riskTitle.match(/\{\{[^{}]*}}|./g);
    if (!arr) return [];
    return arr.reduce<Array<{ value: string; isVariable: boolean }>>((acc, item) => {
      if (item.startsWith('{{') && item.endsWith('}}')) {
        return acc.concat(Array.from(item).map(char => ({ value: char, isVariable: true })));
      }
      return acc.concat({ value: item, isVariable: false });
    }, []);
  };

  const getSmartActionOffsetTarget = () => document.querySelector('.create-strategy-page');

  const toggleCollapse = (index: number) => {
    ruleItems.value[index].collapsed = !ruleItems.value[index].collapsed;
  };

  const handleToggleAllCollapse = () => {
    const shouldCollapse = !allCollapsed.value;
    ruleItems.value.forEach(r => { r.collapsed = shouldCollapse; });
  };

  const handleAddRule = () => {
    const newRule = createRule({ name: `规则${ruleIdSeq}` });
    ruleItems.value.push(newRule);
    nextTick(() => {
      ruleListRef.value?.lastElementChild?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  };

  const handleCloneRule = (index: number) => {
    const source = ruleItems.value[index];
    const cloned = createRule({
      name: `${source.name}_复制`,
      risk_title: source.risk_title,
      risk_level: source.risk_level,
      risk_hazard: source.risk_hazard,
      risk_guidance: source.risk_guidance,
    });
    ruleItems.value.splice(index + 1, 0, cloned);
  };

  const handleDeleteRule = (index: number) => {
    if (ruleItems.value.length === 1) {
      // 保持至少一条规则
      return;
    }
    ruleItems.value.splice(index, 1);
    comRefs.value.splice(index, 1);
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

  const handleVariableInputClick = (e: MouseEvent, index: number) => {
    const rule = ruleItems.value[index];
    if (!rule.variableInputActive) {
      rule.variableInputActive = true;
      nextTick(() => {
        titleInputRefs.value[index]?.focus();
      });
    }
    rule.showVariablePanel = false;
  };

  const handleClickTitleLi = (ruleIndex: number, liIndex: number) => {
    const rule = ruleItems.value[ruleIndex];
    const display = getDisplayRiskTitle(rule.risk_title);
    // 找到点击位置，将前面的文本片段合并
    rule.risk_title = display.slice(0, liIndex).map(i => i.value).join('');
    rule.riskTitleInputValue = '';
    rule.variableInputActive = true;
    nextTick(() => {
      titleInputRefs.value[ruleIndex]?.focus();
    });
  };

  const handleTitleKeyDown = (e: KeyboardEvent, index: number) => {
    const rule = ruleItems.value[index];
    if (e.key === 'Enter' || e.key === 'Escape') {
      if (rule.riskTitleInputValue) {
        rule.risk_title += rule.riskTitleInputValue;
        rule.riskTitleInputValue = '';
      }
      rule.variableInputActive = false;
    }
  };

  const toggleVariablePanel = (e: MouseEvent, index: number) => {
    e.stopPropagation();
    const rule = ruleItems.value[index];
    // 关闭其他规则的变量面板
    ruleItems.value.forEach((r, i) => {
      if (i !== index) r.showVariablePanel = false;
    });
    rule.showVariablePanel = !rule.showVariablePanel;
    if (rule.variableInputActive) {
      if (rule.riskTitleInputValue) {
        rule.risk_title += rule.riskTitleInputValue;
        rule.riskTitleInputValue = '';
      }
      rule.variableInputActive = false;
    }
  };

  const LBRACE = '{{';
  const RBRACE = '}}';
  const getVariableTpl = (fieldName: string) => `${LBRACE} ${fieldName} ${RBRACE}`;

  const insertVariable = (index: number, fieldName: string) => {
    const rule = ruleItems.value[index];
    rule.risk_title += getVariableTpl(fieldName);
    rule.showVariablePanel = false;
  };

  const updateRuleFormData = (data: Record<string, any>, index: number) => {
    ruleItems.value[index].formData = { ...ruleItems.value[index].formData, ...data };
  };

  const buildStepParams = () => {
    const baseFormData = { ...props.formData };
    const rules = ruleItems.value.map((rule, index) => {
      const com = comRefs.value[index];
      const fields = com?.getFields?.({ forValidate: false }) ?? { configs: rule.formData?.configs ?? {} };
      return {
        risk_title: rule.risk_title,
        risk_level: rule.risk_level,
        risk_hazard: rule.risk_hazard,
        risk_guidance: rule.risk_guidance,
        configs: {
          ...(parentConfigs.value ?? {}),
          ...(fields.configs ?? {}),
        },
      };
    });

    // 兼容现有数据结构：取第一条规则的数据合并到 formData
    const firstRule = rules[0] ?? {};
    return {
      ...baseFormData,
      risk_title: firstRule.risk_title ?? baseFormData.risk_title ?? '',
      risk_level: firstRule.risk_level ?? baseFormData.risk_level ?? 'HIGH',
      risk_hazard: firstRule.risk_hazard ?? baseFormData.risk_hazard ?? '',
      risk_guidance: firstRule.risk_guidance ?? baseFormData.risk_guidance ?? '',
      configs: firstRule.configs ?? baseFormData.configs ?? {},
      rules,
    };
  };

  watch(
    () => props.formData,
    (data) => {
      if (!data) return;
      stepFormData.value.strategy_type = data.strategy_type || 'rule';
      stepFormData.value.strategy_name = data.strategy_name ?? '';
      stepFormData.value.status = data.status ?? '';
      stepFormData.value.risk_level = data.risk_level || 'MIDDLE';

      // 回填规则数据
      if (data.rules?.length) {
        ruleItems.value = data.rules.map((r: any, i: number) => createRule({
          name: r.name || `规则${i + 1}`,
          risk_title: r.risk_title || '',
          risk_level: r.risk_level || 'HIGH',
          risk_hazard: r.risk_hazard || '',
          risk_guidance: r.risk_guidance || '',
        }));
      } else if (data.risk_title || data.risk_level) {
        // 兼容旧数据：单规则回填
        ruleItems.value = [createRule({
          risk_title: data.risk_title || '',
          risk_level: data.risk_level || 'HIGH',
          risk_hazard: data.risk_hazard || '',
          risk_guidance: data.risk_guidance || '',
        })];
      }
    },
    { immediate: true, deep: true },
  );

  watch(
    () => props.editData,
    (data) => {
      if ((isEditMode || isCloneMode) && data?.strategy_id) {
        stepFormData.value.strategy_type = data.strategy_type || 'rule';
      }
    },
    { immediate: true },
  );

  const handlePrevious = () => {
    emits('previousStep', 1, buildStepParams());
  };

  const handleNext = async () => {
    if (ruleItems.value.length === 0) {
      return;
    }
    // 验证所有规则的命中条件
    try {
      await Promise.all(
        ruleItems.value.map((_, index) => {
          const com = comRefs.value[index];
          return com?.getValue?.() ?? Promise.resolve();
        }),
      );
      emits('nextStep', 3, buildStepParams());
    } catch {
      // 验证失败，停留在当前步骤
    }
  };

  const handleSaveDraft = () => {
    emits('saveDraft', buildStepParams());
  };

  const handleCancel = () => {
    router.push({ name: 'strategyList' });
  };

  // 关闭所有变量面板（点击外部时）
  const handleDocumentClick = () => {
    ruleItems.value.forEach(r => {
      if (r.variableInputActive && r.riskTitleInputValue) {
        r.risk_title += r.riskTitleInputValue;
        r.riskTitleInputValue = '';
      }
      r.variableInputActive = false;
      r.showVariablePanel = false;
    });
  };

  // 挂载时绑定文档点击事件
  onMounted(() => {
    document.addEventListener('click', handleDocumentClick);
  });
  onBeforeUnmount(() => {
    document.removeEventListener('click', handleDocumentClick);
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

      .rule-name {
        font-size: 14px;
        font-weight: 600;
        color: #313238;
        flex: 1;
        min-width: 0;
        overflow: hidden;
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
        }

        .rule-section-body {
          position: relative;
          overflow: visible;

          .rule-condition-form {
            position: static;
            overflow: visible;

            /* 隐藏 form 本身可能产生的红色 border/shadow 溢出 */
            :deep(.bk-form) {
              position: static;
            }

            /* 命中条件行铺满宽度 */
            :deep(.strategy-customize-rules) {
              width: 100%;
              overflow: visible;
            }

            :deep(.strategy-customize) {
              overflow: visible;
            }

            /* 命中条件每组行背景色（和 rules/index.vue 保持一致） */
            :deep(.strategy-customize-rules .rule-item) {
              background: #f5f7fa;
              border: 1px solid #dcdee5;
              border-radius: 2px;
            }
          }
        }
      }

      .rule-section-two-col {
        display: flex;
        gap: 12px;

        .rule-section-col {
          flex: 1;
          min-width: 0;
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
        display: flex;
        align-items: center;
        min-height: 32px;
        padding: 4px 8px;
        font-size: 12px;
        color: #63656e;
        cursor: text;
        background: #fff;
        border: 1px solid #c4c6cc;
        border-right: none;
        border-radius: 2px 0 0 2px;
        flex: 1;
        flex-wrap: wrap;
        gap: 2px;

        &.active {
          border-color: #3a84ff;
          border-right: none;
        }

        .variable-input-list {
          display: flex;
          flex: 1;
          flex-wrap: wrap;
          gap: 2px;
          list-style: none;
          padding: 0;
          margin: 0;

          .is-variable {
            color: #3a84ff;
          }

          .list-item-input {
            flex: 1;
            min-width: 60px;

            .title-input {
              width: 100%;
              border: none;
              outline: none;
              font-size: 12px;
              color: #313238;
              background: transparent;
            }
          }
        }

        .variable-input-placeholder {
          color: #c4c6cc;
          pointer-events: none;
        }
      }

      /* 引用变量按钮与输入框并排 */
      .rule-section-body:has(.variable-input-content) {
        display: flex;
        align-items: stretch;
        position: relative;

        .reference-variable-btn {
          height: auto;
          min-height: 32px;
          border-radius: 0 2px 2px 0;
          flex-shrink: 0;
        }
      }

      .variable-panel {
        position: absolute;
        top: calc(100% + 4px);
        left: 0;
        z-index: 2000;
        width: 500px;
        max-height: 320px;
        overflow-y: auto;
        background: #fff;
        border: 1px solid #dcdee5;
        border-radius: 2px;
        box-shadow: 0 4px 12px 0 #0000001a;

        .variable-panel-title {
          padding: 12px 16px 8px;
          font-size: 12px;
          font-weight: 600;
          color: #313238;
          border-bottom: 1px solid #f0f1f5;
        }

        .variable-item {
          display: flex;
          align-items: center;
          padding: 8px 16px;
          cursor: pointer;
          gap: 16px;

          &:hover {
            background: #f5f6fa;
          }

          .variable-item-name {
            font-size: 12px;
            color: #3a84ff;
            min-width: 160px;
          }

          .variable-item-label {
            font-size: 12px;
            color: #63656e;
          }
        }

        .variable-panel-empty {
          padding: 16px;
          font-size: 12px;
          color: #979ba5;
          text-align: center;
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
