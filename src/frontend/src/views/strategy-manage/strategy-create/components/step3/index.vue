<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<template>
  <smart-action
    class="create-strategy-page assign-rules-page"
    :offset-target="getSmartActionOffsetTarget">
    <div class="create-strategy-main">
      <div class="assign-rules-card">
        <div class="assign-rules-header">
          <div class="assign-rules-title-row">
            <span class="assign-rules-title">{{ t('风险分派规则') }}</span>
          </div>
          <p class="assign-rules-tip">
            {{ t('分派规则按从上到下的顺序匹配，首条命中后停止；未命中任何分派规则时，将执行默认分派规则。') }}
          </p>
          <bk-button
            class="add-assign-rule-btn"
            @click="handleAddRule">
            <audit-icon
              class="add-icon"
              type="add" />
            {{ t('添加分派规则') }}
          </bk-button>
        </div>

        <div class="assign-rule-list">
          <vuedraggable
            class="assign-rule-draggable"
            ghost-class="assign-rule-item-ghost"
            handle=".rule-drag-handle"
            item-key="id"
            :list="assignRules">
            <template #item="{ element: rule, index }">
              <div
                class="assign-rule-item"
                :class="{ 'is-collapsed': rule.collapsed }">
                <div class="assign-rule-item-header">
                  <span
                    class="rule-drag-handle"
                    title="拖拽排序">
                    <audit-icon type="move" />
                  </span>
                  <audit-icon
                    class="collapse-icon"
                    :class="{ 'is-collapsed': rule.collapsed }"
                    type="angle-line-down"
                    @click="() => toggleCollapse(index)" />
                  <template v-if="rule.editingName">
                    <input
                      v-model="rule.name"
                      class="rule-name-input"
                      type="text"
                      @blur="() => stopEditName(index)"
                      @keydown.enter="() => stopEditName(index)">
                  </template>
                  <template v-else>
                    <span class="rule-name">{{ rule.name }}</span>
                    <audit-icon
                      class="rule-name-edit-icon"
                      type="edit-fill"
                      @click="() => startEditName(index)" />
                  </template>
                  <div class="header-actions">
                    <audit-icon
                      v-bk-tooltips="t('克隆')"
                      class="action-icon"
                      type="copy"
                      @click="() => handleCloneRule(index)" />
                    <audit-icon
                      v-bk-tooltips="t('删除')"
                      class="action-icon action-delete"
                      type="delete"
                      @click="() => handleDeleteRule(index)" />
                  </div>
                </div>

                <div
                  v-show="!rule.collapsed"
                  class="assign-rule-item-content">
                  <div class="form-section">
                    <div class="form-label is-required">
                      {{ t('命中条件') }}
                    </div>
                    <assign-condition-rows
                      v-model="rule.conditions"
                      :field-options="fieldOptions" />
                  </div>
                  <assign-rule-fields
                    :model-value="rule"
                    :scene-options="sceneOptions"
                    @update:model-value="(val) => { assignRules[index] = { ...assignRules[index], ...val }; }" />
                </div>
              </div>
            </template>
          </vuedraggable>

          <!-- 默认分派规则 -->
          <div
            class="assign-rule-item default-rule"
            :class="{ 'is-collapsed': defaultRule.collapsed, 'has-assign-rules': assignRules.length }">
            <div class="assign-rule-item-header">
              <audit-icon
                class="collapse-icon"
                :class="{ 'is-collapsed': defaultRule.collapsed }"
                type="angle-line-down"
                @click="defaultRule.collapsed = !defaultRule.collapsed" />
              <span class="rule-name">{{ t('默认分派规则') }}</span>
            </div>
            <div
              v-show="!defaultRule.collapsed"
              class="assign-rule-item-content">
              <assign-rule-fields
                v-model="defaultRule"
                :scene-options="sceneOptions" />
            </div>
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
        @click="submit">
        {{ t('提交') }}
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
  import { computed, nextTick, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';
  import Vuedraggable from 'vuedraggable';

  import SceneManageService from '@service/scene-manage';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';
  import StrategyModel from '@model/strategy/strategy';

  import AssignConditionRows from './components/assign-condition-rows.vue';
  import AssignRuleFields from './components/assign-rule-fields.vue';

  import {
    getStrategyRouteNames,
    isStrategyCloneRoute,
    isStrategyEditRoute,
  } from '../../../utils/strategy-routes';
  import useRequest from '@/hooks/use-request';
  import {
    type AssignConditionForm,
    buildStrategyEventFieldOptions,
    createDefaultAssignConditionForm,
    dispatchToAssignConditionForm,
    hasValidAssignCondition,
  } from '../../utils/strategy-protocol';

  import useMessage from '@/hooks/use-message';

  interface AssignRuleItem {
    id: number;
    name: string;
    collapsed: boolean;
    editingName: boolean;
    conditions: AssignConditionForm;
    scene_ids: Array<string | number>;
    processors: Array<string | number>;
    notice_users: Array<string | number>;
    assign_mode: 'confirm' | 'direct';
    confirmers: Array<string | number>;
  }

  interface IFormData {
    assign_rules: AssignRuleItem[];
    default_assign_rule: Omit<AssignRuleItem, 'id' | 'name' | 'conditions' | 'editingName'>;
    processor_groups: Array<any>;
    notice_groups: Array<any>;
  }

  interface Emits {
    (e: 'previousStep', step: number, params: IFormData): void;
    (e: 'nextStep', step: number, params: IFormData): void;
    (e: 'saveDraft', params: IFormData): void;
    (e: 'submitData'): void;
  }
  interface Props {
    editData: StrategyModel;
    formData?: Record<string, any>;
    select?: Array<DatabaseTableFieldModel>;
    strategyType?: string;
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

  let ruleIdSeq = 1;

  const createConditionForm = (): AssignConditionForm => createDefaultAssignConditionForm();

  const cloneConditionForm = (form: AssignConditionForm): AssignConditionForm => ({
    connector: form.connector,
    groups: form.groups.map(group => ({
      connector: group.connector,
      conditions: group.conditions.map(row => ({ ...row })),
    })),
  });

  const createRule = (overrides: Partial<AssignRuleItem> = {}): AssignRuleItem => {
    const id = ruleIdSeq;
    ruleIdSeq += 1;
    return {
      id,
      name: overrides.name ?? `规则${id}`,
      collapsed: false,
      editingName: false,
      conditions: createConditionForm(),
      scene_ids: [],
      processors: [],
      notice_users: [],
      assign_mode: 'confirm',
      confirmers: [],
      ...overrides,
    };
  };

  const createDefaultRule = () => ({
    collapsed: false,
    scene_ids: [] as Array<string | number>,
    processors: [] as Array<string | number>,
    notice_users: [] as Array<string | number>,
    assign_mode: 'confirm' as 'confirm' | 'direct',
    confirmers: [] as Array<string | number>,
  });

  const normalizeSceneIds = (item: Record<string, any> = {}): Array<string | number> => {
    let ids: Array<string | number> = [];
    if (Array.isArray(item.scene_ids)) {
      ids = item.scene_ids.filter((id: string | number | '' | null | undefined) => id !== '' && id !== null && id !== undefined);
    } else if (Array.isArray(item.scene_id)) {
      ids = item.scene_id.filter((id: string | number | '' | null | undefined) => id !== '' && id !== null && id !== undefined);
    } else if (item.scene_id !== undefined && item.scene_id !== null && item.scene_id !== '') {
      ids = [item.scene_id];
    } else if (item.scene_space?.id) {
      ids = [item.scene_space.id];
    }
    return ids.length ? [ids[0]] : [];
  };

  const assignRules = ref<AssignRuleItem[]>([]);
  const defaultRule = ref(createDefaultRule());

  const fieldOptions = computed(() => buildStrategyEventFieldOptions({
    event_basic_field_configs: props.formData?.event_basic_field_configs,
    event_data_field_configs: props.formData?.event_data_field_configs,
    event_evidence_field_configs: props.formData?.event_evidence_field_configs,
    strategy_type: props.strategyType,
  }));

  const {
    data: sceneList,
  } = useRequest(SceneManageService.fetchSceneAll, {
    defaultValue: [],
    defaultParams: { status: 'enabled' },
    manual: true,
  });

  const sceneOptions = computed(() => (sceneList.value || []).map((item: any) => ({
    id: item.scene_id,
    name: item.name,
  })));

  const getSmartActionOffsetTarget = () => document.querySelector('.create-strategy-page');

  const toggleCollapse = (index: number) => {
    assignRules.value[index].collapsed = !assignRules.value[index].collapsed;
  };

  const startEditName = (index: number) => {
    assignRules.value[index].editingName = true;
    nextTick(() => {
      const container = document.querySelector('.assign-rule-draggable');
      const inputs = container?.querySelectorAll<HTMLInputElement>('.rule-name-input');
      inputs?.[index]?.focus();
    });
  };

  const stopEditName = (index: number) => {
    assignRules.value[index].editingName = false;
    if (!assignRules.value[index].name.trim()) {
      assignRules.value[index].name = `规则${index + 1}`;
    }
  };

  const handleAddRule = () => {
    const rule = createRule({ name: `规则${assignRules.value.length + 1}` });
    assignRules.value.push(rule);
    nextTick(() => {
      document.querySelector('.assign-rule-draggable .assign-rule-item:last-of-type')
        ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  };

  const handleCloneRule = (index: number) => {
    const source = assignRules.value[index];
    const cloned = createRule({
      name: `${source.name}_复制`,
      conditions: cloneConditionForm(source.conditions),
      scene_ids: [...source.scene_ids],
      processors: [...source.processors],
      notice_users: [...source.notice_users],
      assign_mode: source.assign_mode,
      confirmers: [...source.confirmers],
    });
    assignRules.value.splice(index + 1, 0, cloned);
  };

  const handleDeleteRule = (index: number) => {
    assignRules.value.splice(index, 1);
  };

  const buildStepParams = (): IFormData => ({
    assign_rules: assignRules.value.map(rule => ({
      ...rule,
      conditions: cloneConditionForm(rule.conditions),
      scene_ids: [...rule.scene_ids],
      processors: [...rule.processors],
      notice_users: [...rule.notice_users],
      confirmers: [...rule.confirmers],
    })),
    default_assign_rule: {
      collapsed: defaultRule.value.collapsed,
      scene_ids: [...defaultRule.value.scene_ids],
      processors: [...defaultRule.value.processors],
      notice_users: [...defaultRule.value.notice_users],
      assign_mode: defaultRule.value.assign_mode,
      confirmers: [...defaultRule.value.confirmers],
    },
    // 兼容旧接口字段
    processor_groups: props.formData?.processor_groups ?? [],
    notice_groups: props.formData?.notice_groups ?? [],
  });

  const validateRules = () => {
    const validateOne = (rule: {
      scene_ids: Array<string | number>;
      processors: Array<string | number>;
      assign_mode: string;
      confirmers: Array<string | number>;
    }, label: string) => {
      if (!rule.scene_ids?.length) {
        messageError(t('{label}：分派场景空间不能为空', { label }));
        return false;
      }
      if (!rule.processors?.length) {
        messageError(t('{label}：风险单处理人不能为空', { label }));
        return false;
      }
      if (rule.assign_mode === 'confirm' && !rule.confirmers?.length) {
        messageError(t('{label}：确认人不能为空', { label }));
        return false;
      }
      return true;
    };

    for (const rule of assignRules.value) {
      const hasValidCondition = hasValidAssignCondition(rule.conditions);
      if (!hasValidCondition) {
        messageError(t('{label}：命中条件不能为空', { label: rule.name }));
        return false;
      }
      if (!validateOne(rule, rule.name)) return false;
    }
    return validateOne(defaultRule.value, t('默认分派规则'));
  };

  const handlePrevious = () => {
    emits('previousStep', 4, buildStepParams());
  };

  const handleCancel = () => {
    router.push({ name: strategyRoutes.list });
  };

  const submit = () => {
    if (!validateRules()) return;
    emits('nextStep', 5, buildStepParams());
    emits('submitData');
  };

  const handleSaveDraft = () => {
    emits('saveDraft', buildStepParams());
  };

  const applyEchoData = (data: Record<string, any>) => {
    const assignSource = data.assign_rules?.length
      ? data.assign_rules
      : (data.dispatch_rules || []).filter((item: any) => {
        const { conditions } = item;
        return Array.isArray(conditions)
          ? conditions.some((c: any) => c.field)
          : !!conditions?.conditions?.length;
      });
    if (assignSource?.length) {
      ruleIdSeq = 1;
      assignRules.value = assignSource.map((item: any, index: number) => {
        const conditionForm = dispatchToAssignConditionForm(item.conditions);
        return createRule({
          name: item.rule_name || item.name || `分派规则${index + 1}`,
          conditions: conditionForm,
          scene_ids: normalizeSceneIds({
            ...item,
            scene_ids: item.scene_ids ?? (item.target_scene_id !== undefined ? [item.target_scene_id] : []),
          }),
          processors: item.processors ?? item.processor ?? [],
          notice_users: item.notice_users ?? item.follower ?? [],
          assign_mode: item.assign_mode || (item.dispatch_mode === 'direct' ? 'direct' : 'confirm'),
          confirmers: item.confirmers ?? item.confirmer ?? [],
        });
      });
    }
    const defaultSource = (data.default_assign_rule && Object.keys(data.default_assign_rule).length)
      ? data.default_assign_rule
      : (data.dispatch_rules || []).find((item: any) => {
        const { conditions } = item;
        if (Array.isArray(conditions)) {
          return !conditions.some((c: any) => c.field);
        }
        return !conditions?.conditions?.length;
      });
    if (defaultSource) {
      defaultRule.value = {
        ...createDefaultRule(),
        ...defaultSource,
        scene_ids: normalizeSceneIds({
          ...defaultSource,
          scene_ids: defaultSource.scene_ids
            ?? (defaultSource.target_scene_id !== undefined ? [defaultSource.target_scene_id] : []),
        }),
        processors: defaultSource.processors ?? defaultSource.processor ?? [],
        notice_users: defaultSource.notice_users ?? defaultSource.follower ?? [],
        confirmers: defaultSource.confirmers ?? defaultSource.confirmer ?? [],
        assign_mode: defaultSource.assign_mode || (defaultSource.dispatch_mode === 'direct' ? 'direct' : 'confirm'),
      };
    }
  };

  watch(
    () => props.formData,
    (data) => {
      if (!data) return;
      if (data.assign_rules || data.default_assign_rule || data.dispatch_rules) {
        applyEchoData(data);
      }
    },
    { immediate: true },
  );

  watch(
    () => props.editData,
    (data) => {
      if (!(isEditMode || isCloneMode) || !data) return;
      const anyData = data as any;
      if (anyData.assign_rules || anyData.default_assign_rule || anyData.dispatch_rules) {
        applyEchoData(anyData);
      }
    },
    { immediate: isEditMode || isCloneMode },
  );
</script>
<style lang="postcss" scoped>
.assign-rules-page {
  .create-strategy-main {
    padding-top: 4px;
    margin-bottom: 24px;
  }

  .assign-rules-card {
    background: #fff;
    border-radius: 2px;
    box-shadow: 0 1px 2px 0 #00000029;
  }

  .assign-rules-header {
    padding: 16px 24px 0;
  }

  .assign-rules-title {
    font-size: 14px;
    font-weight: 600;
    color: #313238;
  }

  .assign-rules-tip {
    margin: 8px 0 16px;
    font-size: 12px;
    line-height: 20px;
    color: #979ba5;
  }

  .add-assign-rule-btn {
    margin-bottom: 16px;
    color: #3a84ff;
    border-color: #3a84ff;

    .add-icon {
      margin-right: 4px;
      color: #3a84ff;
    }
  }

  .assign-rule-list {
    padding: 0 24px 24px;
  }

  .assign-rule-draggable {
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .assign-rule-item-ghost {
    opacity: 0.5;
    background: #f0f5ff;
  }

  .assign-rule-item {
    margin-bottom: 8px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px;

    &.default-rule.has-assign-rules {
      margin-top: 8px;
    }

    &:last-child {
      margin-bottom: 0;
    }

    .assign-rule-item-header {
      display: flex;
      align-items: center;
      height: 48px;
      padding: 0 16px;
      background: #f5f6fa;
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

      .collapse-icon {
        font-size: 14px;
        color: #63656e;
        cursor: pointer;
        transition: transform 0.2s ease;

        &.is-collapsed {
          transform: rotate(-90deg);
        }
      }

      .rule-name {
        flex: 1;
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

      .header-actions {
        display: flex;
        gap: 12px;
        margin-left: auto;

        .action-icon {
          font-size: 16px;
          color: #63656e;
          cursor: pointer;

          &:hover {
            color: #3a84ff;
          }

          &.action-delete:hover {
            color: #ea3636;
          }
        }
      }
    }

    &.is-collapsed .assign-rule-item-header {
      border-bottom: none;
    }

    .assign-rule-item-content {
      padding: 20px 24px 24px;
      background: #fafbfd;
    }

    .form-section {
      margin-bottom: 20px;
    }

    .form-label {
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
  }
}
</style>
