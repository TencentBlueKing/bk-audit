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
          <div
            v-for="(rule, index) in assignRules"
            :key="rule.id"
            class="assign-rule-item"
            :class="{ 'is-collapsed': rule.collapsed }">
            <div class="assign-rule-item-header">
              <audit-icon
                class="collapse-icon"
                :class="{ 'is-collapsed': rule.collapsed }"
                type="angle-line-down"
                @click="() => toggleCollapse(index)" />
              <span class="rule-name">{{ rule.name }}</span>
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
                <div class="form-label is-required">{{ t('命中条件') }}</div>
                <assign-condition-rows
                  v-model="rule.conditions"
                  :field-options="fieldOptions" />
              </div>
              <assign-rule-fields
                v-model="rule"
                :current-username="currentUsername"
                :scene-options="sceneOptions" />
            </div>
          </div>

          <!-- 默认分派规则 -->
          <div
            class="assign-rule-item default-rule"
            :class="{ 'is-collapsed': defaultRule.collapsed }">
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
                :current-username="currentUsername"
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

  import AccountManageService from '@service/account-manage';
  import RiskManageService from '@service/risk-manage';
  import SceneManageService from '@service/scene-manage';

  import AccountModel from '@model/account/account';
  import StrategyModel from '@model/strategy/strategy';

  import AssignConditionRows from './components/assign-condition-rows.vue';
  import AssignRuleFields from './components/assign-rule-fields.vue';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';

  interface ConditionItem {
    field: string;
    operator: string;
    value: string;
  }

  interface AssignRuleItem {
    id: number;
    name: string;
    collapsed: boolean;
    conditions: ConditionItem[];
    scene_id: string | number | '';
    processors: string[];
    notice_users: string[];
    assign_mode: 'confirm' | 'direct';
    confirmers: string[];
  }

  interface IFormData {
    assign_rules: AssignRuleItem[];
    default_assign_rule: Omit<AssignRuleItem, 'id' | 'name' | 'conditions'>;
    processor_groups: Array<any>;
    notice_groups: Array<any>;
  }

  interface Emits {
    (e: 'previousStep', step: number, params: IFormData): void;
    (e: 'nextStep', step: number, params: IFormData): void;
    (e: 'submitData'): void;
  }
  interface Props {
    editData: StrategyModel;
    formData?: Record<string, any>;
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const router = useRouter();
  const route = useRoute();
  const { t } = useI18n();
  const { messageError } = useMessage();

  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';

  let ruleIdSeq = 1;

  const createCondition = (): ConditionItem => ({
    field: '',
    operator: 'eq',
    value: '',
  });

  const createRule = (overrides: Partial<AssignRuleItem> = {}): AssignRuleItem => {
    const id = ruleIdSeq++;
    return {
      id,
      name: overrides.name ?? `分派规则${id}`,
      collapsed: false,
      conditions: [createCondition()],
      scene_id: '',
      processors: [],
      notice_users: [],
      assign_mode: 'confirm',
      confirmers: [],
      ...overrides,
    };
  };

  const createDefaultRule = () => ({
    collapsed: false,
    scene_id: '' as string | number | '',
    processors: [] as string[],
    notice_users: [] as string[],
    assign_mode: 'confirm' as 'confirm' | 'direct',
    confirmers: [] as string[],
  });

  const assignRules = ref<AssignRuleItem[]>([createRule({ name: '分派规则1' })]);
  const defaultRule = ref(createDefaultRule());

  const {
    data: userInfo,
  } = useRequest(AccountManageService.fetchUserInfo, {
    defaultValue: new AccountModel(),
    manual: true,
  });

  const currentUsername = computed(() => userInfo.value?.username || '');

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

  const {
    data: riskFieldList,
  } = useRequest(RiskManageService.fetchFields, {
    defaultValue: [],
    manual: true,
  });

  const fieldOptions = computed(() => (riskFieldList.value || []).map((item: any) => ({
    id: item.id,
    name: item.name,
  })));

  const getSmartActionOffsetTarget = () => document.querySelector('.create-strategy-page');

  const toggleCollapse = (index: number) => {
    assignRules.value[index].collapsed = !assignRules.value[index].collapsed;
  };

  const handleAddRule = () => {
    const rule = createRule({ name: `分派规则${assignRules.value.length + 1}` });
    assignRules.value.push(rule);
    nextTick(() => {
      document.querySelector('.assign-rule-item:last-of-type')
        ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  };

  const handleCloneRule = (index: number) => {
    const source = assignRules.value[index];
    const cloned = createRule({
      name: `${source.name}_复制`,
      conditions: source.conditions.map(item => ({ ...item })),
      scene_id: source.scene_id,
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
      conditions: rule.conditions.map(item => ({ ...item })),
      processors: [...rule.processors],
      notice_users: [...rule.notice_users],
      confirmers: [...rule.confirmers],
    })),
    default_assign_rule: {
      collapsed: defaultRule.value.collapsed,
      scene_id: defaultRule.value.scene_id,
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
      scene_id: string | number | '';
      processors: string[];
      assign_mode: string;
      confirmers: string[];
    }, label: string) => {
      if (!rule.scene_id && rule.scene_id !== 0) {
        messageError(t('{label}：分派至场景空间不能为空', { label }));
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
      const hasValidCondition = rule.conditions.some(item => item.field && item.operator);
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
    router.push({ name: 'strategyList' });
  };

  const submit = () => {
    if (!validateRules()) return;
    emits('nextStep', 5, buildStepParams());
    emits('submitData');
  };

  const applyEchoData = (data: Record<string, any>) => {
    if (data.assign_rules?.length) {
      ruleIdSeq = 1;
      assignRules.value = data.assign_rules.map((item: any, index: number) => createRule({
        name: item.name || `分派规则${index + 1}`,
        conditions: item.conditions?.length
          ? item.conditions.map((c: ConditionItem) => ({ ...c }))
          : [createCondition()],
        scene_id: item.scene_id ?? '',
        processors: item.processors ?? [],
        notice_users: item.notice_users ?? [],
        assign_mode: item.assign_mode || 'confirm',
        confirmers: item.confirmers ?? [],
      }));
    }
    if (data.default_assign_rule) {
      defaultRule.value = {
        ...createDefaultRule(),
        ...data.default_assign_rule,
        processors: data.default_assign_rule.processors ?? [],
        notice_users: data.default_assign_rule.notice_users ?? [],
        confirmers: data.default_assign_rule.confirmers ?? [],
      };
    }
  };

  watch(
    () => props.formData,
    (data) => {
      if (!data) return;
      if (data.assign_rules || data.default_assign_rule) {
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
      if (anyData.assign_rules || anyData.default_assign_rule) {
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

  .assign-rule-item {
    margin-bottom: 8px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px;

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
        font-size: 14px;
        font-weight: 600;
        color: #313238;
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
